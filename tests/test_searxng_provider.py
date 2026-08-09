import asyncio

from maica.maica_utils import G
from maica.mtools.api_keys import TpAPIKeys
from maica.mtools.providers import serp_provider_95
from maica.mtools.providers import base as provider_base


def test_searxng_provider_is_registered_at_priority_95() -> None:
    assert (95, ["SEARXNG_ADDR"], serp_provider_95.asearch) in provider_base._providers_raw


def test_searxng_provider_maps_results_without_proxy_by_default(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {
                        "title": "Example",
                        "content": "Result summary",
                        "url": "https://example.com/result",
                        "engines": ["google", "bing"],
                    }
                ]
            }

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            return FakeResponse()

    monkeypatch.setattr(serp_provider_95.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(TpAPIKeys, "SEARXNG_ADDR", "https://search.example/", raising=False)
    monkeypatch.delattr(TpAPIKeys, "SEARXNG_USE_PROXY", raising=False)
    monkeypatch.setattr(G.A, "PROXY_ADDR", "socks5://proxy.example:1080")

    result = asyncio.run(serp_provider_95.asearch("test query", "en"))

    assert calls == [
        ("client", {"proxy": None}),
        (
            "get",
            "https://search.example/search",
            {
                "params": {"q": "test query", "format": "json", "language": "en-US"},
                "timeout": 30,
            },
        ),
    ]
    assert result.model_dump() == {
        "results": [
            {
                "title": "Example",
                "description": "Result summary",
                "rank": 1,
                "link": "https://example.com/result",
                "source": "google, bing",
            }
        ]
    }


def test_searxng_provider_uses_configured_proxy(monkeypatch) -> None:
    proxies = []

    class FakeClient:
        def __init__(self, *, proxy):
            proxies.append(proxy)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def get(self, *_args, **_kwargs):
            class FakeResponse:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"results": []}

            return FakeResponse()

    monkeypatch.setattr(serp_provider_95.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(TpAPIKeys, "SEARXNG_ADDR", "https://search.example", raising=False)
    monkeypatch.setattr(TpAPIKeys, "SEARXNG_USE_PROXY", True, raising=False)
    monkeypatch.setattr(G.A, "PROXY_ADDR", "http://proxy.example:8080")

    asyncio.run(serp_provider_95.asearch("test query"))

    assert proxies == ["http://proxy.example:8080"]
