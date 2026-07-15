import asyncio
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
    G.A.KEEP_MVISTA = "3"
    G.A.VISION_HOST_ALLOWLIST = "images.example.com"
    base = {"type": "query", "query": "describe", "chat_session": 0}

    accepted = WsQueryConfig.model_validate(
        base | {"vision": ["https://images.example.com/picture.jpg"]}
    )
    assert accepted.vision.root == ["https://images.example.com/picture.jpg"]

    for url in ("file:///etc/passwd", "https://internal.example/picture.jpg"):
        try:
            WsQueryConfig.model_validate(base | {"vision": [url]})
        except Exception:
            pass
        else:
            raise AssertionError(f"unsafe vision URL was accepted: {url}")

    G.A.VISION_HOST_ALLOWLIST = ""
