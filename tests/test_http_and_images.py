import asyncio
import socket
import threading
from io import BytesIO

from PIL import Image
from quart import Quart, request
from quart.testing import make_test_body_with_headers
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge

from maica.maica_http import (
    _DEFAULT_CONTENT_LENGTH,
    _MVISTA_CONTENT_LENGTH,
    AdjustableBody,
    MaicaRequest,
    app,
    jfy_res,
    set_request_content_length,
)
from maica.maica_utils import G, MaicaInputWarning, WsQueryConfig
from maica.mtools.mvista.img_proc import ImgByUuid
from maica.mtools.mvista import img_proc


def test_json_response_preserves_falsy_content() -> None:
    async def scenario() -> None:
        async with app.app_context():
            for value in (False, 0, [], {}, None):
                response = jfy_res(value)
                payload = await response.get_json()
                assert "content" in payload
                assert payload["content"] == value

    asyncio.run(scenario())


def test_image_detection_conversion_and_save_are_cross_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(img_proc, "_base_path", str(tmp_path))
    source = BytesIO()
    Image.new("RGBA", (32, 24), (255, 0, 0, 128)).save(source, format="PNG")
    image = ImgByUuid(source.getvalue())
    assert image.format == "image/jpeg"
    assert image.get_bio().read(2) == b"\xff\xd8"
    image.save()
    assert (tmp_path / image.file_name).read_bytes().startswith(b"\xff\xd8")


def test_vista_request_body_uses_its_32_mib_limit() -> None:
    async def scenario() -> None:
        test_app = Quart(__name__)
        test_app.request_class = MaicaRequest
        test_app.config["MAX_CONTENT_LENGTH"] = _MVISTA_CONTENT_LENGTH
        test_app.before_request(set_request_content_length)

        async def parse_upload():
            form = await request.form
            files = await request.files
            return {
                "token": form["access_token"],
                "size": len(files["content"].read()),
            }

        test_app.add_url_rule(
            "/vista",
            endpoint="upload_vista",
            methods=["POST"],
            view_func=parse_upload,
        )
        test_app.add_url_rule(
            "/other",
            endpoint="other_upload",
            methods=["POST"],
            view_func=parse_upload,
        )

        image_data = b"x" * (1024 * 1024 + 1)
        image_file = FileStorage(
            stream=BytesIO(image_data),
            filename="image.jpg",
            content_type="image/jpeg",
        )
        body, headers = make_test_body_with_headers(
            form={"access_token": "token"},
            files={"content": image_file},
            app=test_app,
        )
        client = test_app.test_client()

        response = await client.post("/vista", data=body, headers=headers)
        assert response.status_code == 200
        assert await response.get_json() == {"token": "token", "size": len(image_data)}

        response = await client.post("/other", data=body, headers=headers)
        assert response.status_code == 413

    asyncio.run(scenario())


def test_adjustable_body_enforces_retroactive_and_hard_limits() -> None:
    async def scenario() -> None:
        buffered_body = AdjustableBody(None, _MVISTA_CONTENT_LENGTH)
        buffered_body.set_result(b"x" * (_DEFAULT_CONTENT_LENGTH + 1))
        buffered_body.set_max_content_length(_DEFAULT_CONTENT_LENGTH)

        declared_body = AdjustableBody(
            _MVISTA_CONTENT_LENGTH + 1,
            _MVISTA_CONTENT_LENGTH,
        )

        for body in (buffered_body, declared_body):
            try:
                await body
            except RequestEntityTooLarge:
                pass
            else:
                raise AssertionError("the request body limit was not enforced")

    asyncio.run(scenario())


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
