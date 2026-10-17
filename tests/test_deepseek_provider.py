import asyncio

from maica.maica_utils import G
from maica.mtools.api_keys import TpAPIKeys
from maica.mtools.providers import serp_provider_35
from maica.mtools.providers import base as provider_base


def test_deepseek_provider_is_registered_at_priority_35() -> None:
    assert (35, ["DEEPSEEK_SEARCH_KEY"], serp_provider_35.asearch) in provider_base._providers_raw


def test_deepseek_provider_sends_search_request_and_maps_results(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {
                        "title": "Example",
                        "url": "https://example.com/result",
                        "summary": "A result summary",
                        "snippet": "A shorter summary",
                        "site_name": "Example News",
                    },
                    {
                        "title": "Fallback",
                        "url": "https://example.com/fallback",
                        "snippet": "A fallback snippet",
                    },
                ]
            }

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def post(self, url, **kwargs):
            calls.append(("post", url, kwargs))
            return FakeResponse()

    monkeypatch.setattr(serp_provider_35.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(TpAPIKeys, "DEEPSEEK_SEARCH_KEY", "test-key", raising=False)
    monkeypatch.setattr(G.A, "PROXY_ADDR", "http://proxy.example:8080")

    result = asyncio.run(serp_provider_35.asearch("test query", "en"))

    assert calls == [
        ("client", {"proxy": "http://proxy.example:8080"}),
        (
            "post",
            "https://api.deepseek.com/v1/tools/search",
            {
                "headers": {
                    "Authorization": "Bearer test-key",
                    "Content-Type": "application/json",
                },
                "json": {
                    "query": "test query",
                    "count": 10,
                    "need_content": False,
                },
                "timeout": 30,
            },
        ),
    ]
    assert result.model_dump() == {
        "results": [
            {
                "title": "Example",
                "description": "A result summary",
                "rank": 1,
                "link": "https://example.com/result",
                "source": "Example News",
            },
            {
                "title": "Fallback",
                "description": "A fallback snippet",
                "rank": 2,
                "link": "https://example.com/fallback",
                "source": None,
            },
        ]
    }
