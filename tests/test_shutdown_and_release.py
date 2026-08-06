import asyncio
from pathlib import Path

import pytest
from dotenv import dotenv_values

from maica import maica_starter, maica_ws
from maica.maica_utils import G, MaicaPermissionWarning
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

        async def hanging_start_all(_target, shutdown_trigger=None):
            assert shutdown_trigger is not None
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


def test_service_group_cancellation_reaches_every_service() -> None:
    async def scenario() -> None:
        started = [asyncio.Event() for _ in range(3)]
        cancelled = [asyncio.Event() for _ in range(3)]

        async def service(index: int) -> None:
            started[index].set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled[index].set()

        services = [asyncio.create_task(service(index)) for index in range(3)]
        group = asyncio.create_task(maica_starter._wait_for_first(services))
        try:
            await asyncio.wait_for(
                asyncio.gather(*(event.wait() for event in started)),
                timeout=1,
            )
            group.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(group, timeout=1)

            assert all(event.is_set() for event in cancelled)
            assert all(task.done() for task in services)
        finally:
            for task in services:
                task.cancel()
            await asyncio.gather(*services, return_exceptions=True)

    asyncio.run(scenario())


def test_http_uses_external_shutdown_trigger(monkeypatch) -> None:
    async def scenario() -> None:
        shutdown_requested = asyncio.Event()
        shutdown_trigger = shutdown_requested.wait
        serve_started = asyncio.Event()
        received_trigger = None
        old_host, old_port = G.A.HTTP_HOST, G.A.HTTP_PORT
        G.A.HTTP_HOST, G.A.HTTP_PORT = "127.0.0.1", "5001"

        class FakeWatcher:
            async def wrapped_main_watcher(self):
                await asyncio.Event().wait()

            async def close(self):
                return None

        async def fake_watcher_create(*_args, **_kwargs):
            return FakeWatcher()

        async def fake_serve(_app, _config, *, shutdown_trigger=None):
            nonlocal received_trigger
            received_trigger = shutdown_trigger
            serve_started.set()
            await shutdown_trigger()

        monkeypatch.setattr(
            maica_starter.maica_http.NvWatcher,
            "async_create",
            fake_watcher_create,
        )
        monkeypatch.setattr(maica_starter.maica_http, "serve", fake_serve)

        try:
            task = asyncio.create_task(
                maica_starter.maica_http.prepare_thread(
                    shutdown_trigger=shutdown_trigger,
                )
            )
            await asyncio.wait_for(serve_started.wait(), timeout=1)

            assert received_trigger is shutdown_trigger
            shutdown_requested.set()
            await asyncio.wait_for(task, timeout=1)
        finally:
            G.A.HTTP_HOST, G.A.HTTP_PORT = old_host, old_port

    asyncio.run(scenario())


def test_websocket_authentication_has_a_configurable_timeout() -> None:
    async def scenario() -> None:
        old_timeout = G.A.AUTH_TIMEOUT
        G.A.AUTH_TIMEOUT = "0.01"

        class HangingAuth:
            async def check_permit(self):
                await asyncio.Event().wait()

        try:
            with pytest.raises(MaicaPermissionWarning, match="timed out") as exc_info:
                await maica_ws._wait_for_permit(HangingAuth())
            assert exc_info.value.error_code == 408
        finally:
            G.A.AUTH_TIMEOUT = old_timeout

    asyncio.run(scenario())


def test_partial_root_connection_failure_closes_successes(monkeypatch) -> None:
    class Connection:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    async def scenario() -> None:
        connection = Connection()

        async def succeeds():
            return connection

        async def fails():
            raise RuntimeError("connection failed")

        monkeypatch.setattr(maica_starter.ConnUtils, "test_success", succeeds, raising=False)
        monkeypatch.setattr(maica_starter.ConnUtils, "test_failure", fails, raising=False)

        with pytest.raises(RuntimeError, match="connection failed"):
            await maica_starter._create_root_connections(
                ["test_success", "test_failure"]
            )
        assert connection.closed

    asyncio.run(scenario())


def test_config_validation_is_offline_and_reports_invalid_values(monkeypatch) -> None:
    values = {
        key: value
        for key, value in dotenv_values(
            Path(__file__).parents[1] / "maica" / "env_basis"
        ).items()
        if value is not None
    }
    values.update({
        "MAICA_IS_REAL_ENV": "1",
        "MAICA_DB_ADDR": "sqlite",
        "MAICA_AUTH_DB": "auth.db",
        "MAICA_DATA_DB": "data.db",
        "MAICA_MCORE_ADDR": "http://model.invalid/v1",
        "MAICA_MFOCUS_ADDR": "http://model.invalid/v1",
    })
    monkeypatch.setattr(maica_starter, "load_env", values.get)

    maica_starter.validate_config()
    values["MAICA_HTTP_PORT"] = "70000"
    with pytest.raises(RuntimeError, match="MAICA_HTTP_PORT"):
        maica_starter.validate_config()


def test_validate_only_startup_skips_database_initialization(monkeypatch) -> None:
    old_validate_only = maica_starter.validate_only
    called = []

    def fake_check_params():
        maica_starter.validate_only = True

    def fail_database_init():
        raise AssertionError("database initialization ran")

    monkeypatch.setattr(maica_starter, "check_params", fake_check_params)
    monkeypatch.setattr(maica_starter, "validate_config", lambda: called.append("validated"))
    monkeypatch.setattr(maica_starter, "check_data_init", fail_database_init)
    try:
        maica_starter.full_start()
        assert called == ["validated"]
    finally:
        maica_starter.validate_only = old_validate_only


def test_release_workflow_skips_an_existing_pypi_version() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "maica.yml").read_text(encoding="utf-8")

    assert "Check whether this version already exists on PyPI" in workflow
    assert "if: needs.release-status.outputs.pypi-exists == 'false'" in workflow
    assert "skip-existing: true" in workflow
