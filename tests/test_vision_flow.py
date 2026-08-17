import asyncio
from types import SimpleNamespace

import pytest

from maica.maica_utils import (
    AiConnectionManager,
    G,
    MaicaInputWarning,
    MaicaSession,
    MaicaSessionItem,
    MaicaSettings,
    WsQueryConfig,
)
from maica.maica_ws import WsCoroutine
from maica.mfocus.mfocus_llm import MfPipeliner
from maica.mtools.mvista.explain_image import query_vlm


IMAGE_URL = "https://images.example/picture.jpg"


def _configure_native_vision(monkeypatch) -> None:
    monkeypatch.setattr(G.A, "MCORE_ADDR", "https://models.example/v1")
    monkeypatch.setattr(G.A, "MVISTA_ADDR", "https://models.example/v1")
    monkeypatch.setattr(G.A, "MCORE_CHOICE", "vision-model")
    monkeypatch.setattr(G.A, "MVISTA_CHOICE", "vision-model")
    monkeypatch.setattr(G.A, "KEEP_MVISTA", "3")


def _make_worker():
    fsc = SimpleNamespace(
        maica_settings=MaicaSettings(),
        mvista_conn=None,
    )
    return WsCoroutine(fsc), fsc


def _expected_user_input(text: str) -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "input_text", "text": text},
            {
                "type": "input_image",
                "image_url": IMAGE_URL,
                "detail": "auto",
            },
        ],
    }


def test_native_vision_binds_to_current_user_for_managed_session(monkeypatch) -> None:
    _configure_native_vision(monkeypatch)
    worker, _ = _make_worker()
    config = WsQueryConfig.model_validate({
        "type": "query",
        "chat_session": 0,
        "query": "describe",
        "vision": [IMAGE_URL],
    })
    session = MaicaSession(0)

    user_query, str_query = worker._prepare_user_query(session, config)

    assert user_query is session[-1]
    assert str_query == "describe"
    assert user_query.context.image_urls == [IMAGE_URL]
    assert session.utilize()[-1] == _expected_user_input("describe")


def test_native_vision_binds_after_session_minus_one_load(monkeypatch) -> None:
    _configure_native_vision(monkeypatch)
    worker, _ = _make_worker()
    config = WsQueryConfig.model_validate({
        "type": "query",
        "chat_session": -1,
        "query": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "describe"},
        ],
        "vision": IMAGE_URL,
    })
    session = MaicaSession(-1)

    user_query, _ = worker._prepare_user_query(session, config)

    assert user_query is session[-1]
    assert user_query.context.image_urls == [IMAGE_URL]
    assert session.utilize()[-1] == _expected_user_input("describe")


@pytest.mark.parametrize(
    "query",
    [
        [
            {
                "role": "user",
                "content": "describe",
                "context": {"image_urls": [IMAGE_URL]},
            }
        ],
        [
            {
                "role": "misc",
                "preserved": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": IMAGE_URL,
                            "detail": "auto",
                        }
                    ],
                },
            }
        ],
        [
            {
                "role": "misc",
                "preserved": {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": IMAGE_URL},
                        }
                    ],
                },
            }
        ],
    ],
)
def test_session_minus_one_rejects_embedded_vision(query) -> None:
    with pytest.raises(
        MaicaInputWarning,
        match="top-level vision field",
    ):
        WsQueryConfig.model_validate({
            "type": "query",
            "chat_session": -1,
            "query": query,
        })


def test_disabled_dedicated_mvista_is_not_offered_to_mfocus(monkeypatch) -> None:
    monkeypatch.setattr(G.A, "MCORE_ADDR", "https://core.example/v1")
    monkeypatch.setattr(G.A, "MVISTA_ADDR", "")
    monkeypatch.setattr(G.A, "MCORE_CHOICE", "core-model")
    monkeypatch.setattr(G.A, "MVISTA_CHOICE", "")

    settings = MaicaSettings()
    settings.temp.mvista.mv_imgs = [IMAGE_URL]
    fsc = SimpleNamespace(maica_settings=settings, mvista_conn=None)
    pipeliner = object.__new__(MfPipeliner)
    pipeliner.fsc = fsc

    assert pipeliner._mfocus_impl_mvista is False
    fsc.mvista_conn = object()
    assert pipeliner._mfocus_impl_mvista is True


def test_dedicated_mvista_uses_responses_image_input(monkeypatch) -> None:
    class FakeConnection:
        request = None

        async def make_completion(self, **kwargs):
            self.request = kwargs
            return SimpleNamespace(output_text='{"reply":"observed"}')

    monkeypatch.setattr(G.A, "MCORE_ADDR", "https://core.example/v1")
    monkeypatch.setattr(G.A, "MVISTA_ADDR", "https://vision.example/v1")
    monkeypatch.setattr(G.A, "MCORE_CHOICE", "core-model")
    monkeypatch.setattr(G.A, "MVISTA_CHOICE", "vision-model")
    monkeypatch.setattr(G.A, "KEEP_MVISTA", "3")

    connection = FakeConnection()
    settings = MaicaSettings()
    settings.basic.target_lang = "en"
    fsc = SimpleNamespace(
        maica_settings=settings,
        mvista_conn=connection,
    )

    result = asyncio.run(query_vlm(fsc, "describe", [IMAGE_URL]))

    assert result == "observed"
    assert connection.request["input"][-1] == _expected_user_input("describe")


def test_native_vision_reaches_responses_client_payload(monkeypatch) -> None:
    class FakeResponses:
        request = None

        async def create(self, **kwargs):
            self.request = kwargs
            return SimpleNamespace()

    responses = FakeResponses()
    monkeypatch.setattr(G.A, "OPENAI_TIMEOUT", "0")
    connection = AiConnectionManager(
        api_key="key",
        base_url="https://models.example/v1",
        model="vision-model",
    )
    connection.model_actual = "vision-model"
    connection.client = SimpleNamespace(responses=responses)
    completion_input = [
        {"role": "system", "content": "system prompt"},
        _expected_user_input("describe"),
    ]

    asyncio.run(connection.make_completion(input=completion_input))

    assert responses.request["instructions"] == "system prompt"
    assert responses.request["input"] == [_expected_user_input("describe")]
    assert responses.request["model"] == "vision-model"


def test_native_vision_without_images_keeps_plain_text(monkeypatch) -> None:
    _configure_native_vision(monkeypatch)
    item = MaicaSessionItem("user", "hello")

    assert item.utilize() == {"role": "user", "content": "hello"}
