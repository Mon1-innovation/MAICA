import asyncio
from pathlib import Path

import pytest

from maica import maica_starter, maica_ws
from maica.maica_utils import G
from maica.maica_utils.users_utils import auth_token_reference


def test_auth_token_reference_is_stable_without_exposing_credentials() -> None:
    token = "encrypted-token-containing-secret-password"
    reference = auth_token_reference(token)

    assert reference == auth_token_reference(token)
    assert reference.startswith("sha256:")
    assert token not in reference
    assert "secret-password" not in reference


def test_websocket_server_cancellation_stops_active_handlers(monkeypatch) -> None:
    class FakeServer:
        def __init__(self, handler) -> None:
            self.handler = handler
            self.handler_task = None
            self.closed = False

        async def serve_forever(self) -> None:
            self.handler_task = asyncio.create_task(self.handler(object()))
            await asyncio.Event().wait()

        def close(self, close_connections=True) -> None:
            assert close_connections is True
            self.closed = True

        async def wait_closed(self) -> None:
            if self.handler_task:
                await asyncio.gather(self.handler_task, return_exceptions=True)

    async def scenario() -> None:
        old_host, old_port = G.A.WS_HOST, G.A.WS_PORT
        G.A.WS_HOST, G.A.WS_PORT = "127.0.0.1", "5000"
        handler_started = asyncio.Event()
        handler_cancelled = asyncio.Event()
        server_holder = {}

        async def hanging_handler(_websocket, root_csc):
            assert root_csc is not None
            handler_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                handler_cancelled.set()

        async def fake_serve(handler, *_args, **_kwargs):
            server = FakeServer(handler)
            server_holder["server"] = server
            return server

        monkeypatch.setattr(maica_ws, "main_logic", hanging_handler)
        monkeypatch.setattr(maica_ws.websockets, "serve", fake_serve)

        try:
            task = asyncio.create_task(maica_ws.prepare_thread())
            await asyncio.wait_for(handler_started.wait(), timeout=1)
            server = server_holder["server"]

            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=1)

            assert server.closed
            assert handler_cancelled.is_set()
            assert server.handler_task.done()
        finally:
            G.A.WS_HOST, G.A.WS_PORT = old_host, old_port

    asyncio.run(scenario())


def test_sigterm_path_cancels_service_group(monkeypatch) -> None:
    async def scenario() -> None:
        service_started = asyncio.Event()
        service_cancelled = asyncio.Event()
        signal_callback = None

        async def hanging_start_all(_target):
            service_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                service_cancelled.set()

        loop = asyncio.get_running_loop()

        def capture_signal_handler(_signal, callback):
            nonlocal signal_callback
            signal_callback = callback

        monkeypatch.setattr(maica_starter, "start_all", hanging_start_all)
        monkeypatch.setattr(loop, "add_signal_handler", capture_signal_handler)
        monkeypatch.setattr(loop, "remove_signal_handler", lambda _signal: True)

        task = asyncio.create_task(maica_starter._start_with_sigterm("chat"))
        await asyncio.wait_for(service_started.wait(), timeout=1)
        assert signal_callback is not None

        signal_callback()
        await asyncio.wait_for(task, timeout=1)
        assert service_cancelled.is_set()

    asyncio.run(scenario())


def test_release_workflow_skips_an_existing_pypi_version() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "maica.yml").read_text(encoding="utf-8")

    assert "Check whether this version already exists on PyPI" in workflow
    assert "if: needs.release-status.outputs.pypi-exists == 'false'" in workflow
    assert "skip-existing: true" in workflow
