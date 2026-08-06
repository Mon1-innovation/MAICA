import asyncio
import socket
import threading
from io import BytesIO

from PIL import Image

from maica.maica_http import app, jfy_res
from maica.maica_utils import G, MaicaInputWarning, WsQueryConfig
from maica.mtools.mvista.img_proc import ImgByUuid


def test_json_response_preserves_falsy_content() -> None:
    async def scenario() -> None:
        async with app.app_context():
            for value in (False, 0, [], {}, None):
                response = jfy_res(value)
                payload = await response.get_json()
                assert "content" in payload
                assert payload["content"] == value

    asyncio.run(scenario())


def test_image_detection_and_conversion_are_cross_platform() -> None:
    source = BytesIO()
    Image.new("RGBA", (32, 24), (255, 0, 0, 128)).save(source, format="PNG")
    image = ImgByUuid(source.getvalue())
    assert image.format == "image/jpeg"
    assert image.get_bio().read(2) == b"\xff\xd8"


def test_invalid_image_is_rejected() -> None:
    try:
        ImgByUuid(b"not an image")
    except MaicaInputWarning:
        pass
    else:
        raise AssertionError("invalid bytes were accepted as an image")


def test_vision_urls_reject_non_http_schemes_and_honor_allowlist() -> None:
    async def scenario() -> None:
        G.A.KEEP_MVISTA = "3"
        G.A.MVISTA_TRUSTED = "images.example.com"
        base = {"type": "query", "query": "describe", "chat_session": 0}

        accepted = WsQueryConfig.model_validate(
            base | {"vision": ["https://images.example.com/picture.jpg"]}
        )
        assert accepted.vision.root == ["https://images.example.com/picture.jpg"]
        await accepted.validate_vision_hosts()

        for url in ("file:///etc/passwd", "https://internal.example/picture.jpg"):
            try:
                config = WsQueryConfig.model_validate(base | {"vision": [url]})
                await config.validate_vision_hosts()
            except Exception:
                pass
            else:
                raise AssertionError(f"unsafe vision URL was accepted: {url}")

        G.A.MVISTA_TRUSTED = ""

    asyncio.run(scenario())


def test_vision_host_rules_support_deny_cidr_dns_and_default_deny(monkeypatch) -> None:
    async def scenario() -> None:
        old_keep = G.A.KEEP_MVISTA
        old_rules = G.A.MVISTA_TRUSTED
        G.A.KEEP_MVISTA = "3"
        base = {"type": "query", "query": "describe", "chat_session": 0}

        def resolve(host, *_args, **_kwargs):
            address = "10.1.2.3" if host == "internal.example" else "203.0.113.8"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

        monkeypatch.setattr(socket, "getaddrinfo", resolve)
        try:
            G.A.MVISTA_TRUSTED = "images.example,!10.0.0.0/8"
            config = WsQueryConfig.model_validate(
                base | {"vision": ["https://images.example/picture.jpg"]}
            )
            await config.validate_vision_hosts()
            config = WsQueryConfig.model_validate(
                base | {"vision": ["https://public.example/picture.jpg"]}
            )
            await config.validate_vision_hosts()

            for url in (
                "https://10.2.3.4/picture.jpg",
                "https://internal.example/picture.jpg",
            ):
                try:
                    config = WsQueryConfig.model_validate(base | {"vision": [url]})
                    await config.validate_vision_hosts()
                except Exception:
                    pass
                else:
                    raise AssertionError(f"denied vision URL was accepted: {url}")

            G.A.MVISTA_TRUSTED = "images.example,!*"
            try:
                config = WsQueryConfig.model_validate(
                    base | {"vision": ["https://public.example/picture.jpg"]}
                )
                await config.validate_vision_hosts()
            except Exception:
                pass
            else:
                raise AssertionError("!* accepted an unmarked host")
        finally:
            G.A.KEEP_MVISTA = old_keep
            G.A.MVISTA_TRUSTED = old_rules

    asyncio.run(scenario())


def test_vision_dns_resolution_does_not_block_event_loop(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocking_resolve(host, *_args, **_kwargs):
        started.set()
        release.wait(timeout=2)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.8", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", blocking_resolve)

    async def scenario() -> None:
        old_keep = G.A.KEEP_MVISTA
        old_rules = G.A.MVISTA_TRUSTED
        G.A.KEEP_MVISTA = "3"
        G.A.MVISTA_TRUSTED = "!10.0.0.0/8"
        try:
            config = WsQueryConfig.model_validate({
                "type": "query",
                "query": "describe",
                "chat_session": 0,
                "vision": ["https://public.example/picture.jpg"],
            })
            task = asyncio.create_task(config.validate_vision_hosts())
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.001)
            assert started.is_set()
            heartbeat = asyncio.Event()
            asyncio.get_running_loop().call_soon(heartbeat.set)
            await asyncio.wait_for(heartbeat.wait(), timeout=0.1)
            assert not task.done()
            release.set()
            await task
        finally:
            release.set()
            G.A.KEEP_MVISTA = old_keep
            G.A.MVISTA_TRUSTED = old_rules

    asyncio.run(scenario())
