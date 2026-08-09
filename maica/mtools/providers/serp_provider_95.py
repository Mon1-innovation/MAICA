"""SearXNG JSON API SERP provider."""

import asyncio
from typing import Any

import httpx
from pydantic import model_validator

from maica.maica_utils import G, TargetLangType
from maica.mtools.api_keys import TpAPIKeys
from .base import SerpResults, register_provider


prio = 95
requires = ["SEARXNG_ADDR"]


class SearXNGResults(SerpResults):
    @model_validator(mode="before")
    @classmethod
    def auto_transform(cls, data: Any):
        if not isinstance(data, dict):
            return data

        results = []
        for rank, item in enumerate(data.get("results") or [], start=1):
            if not isinstance(item, dict):
                continue

            engines = item.get("engines")
            source = ", ".join(engines) if isinstance(engines, list) else item.get("engine")
            results.append(
                {
                    "title": item.get("title"),
                    "description": item.get("content") or "",
                    "rank": rank,
                    "link": item.get("url"),
                    "source": source,
                }
            )

        return {"results": results}


def _use_proxy() -> bool:
    configured = getattr(TpAPIKeys, "SEARXNG_USE_PROXY", False)
    if isinstance(configured, str):
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return bool(configured)


async def asearch(query: str, target_lang: TargetLangType = "zh") -> SerpResults:
    locale = "zh-CN" if target_lang == "zh" else "en-US"
    url = f"{TpAPIKeys.SEARXNG_ADDR.rstrip('/')}/search"
    proxy = (G.A.PROXY_ADDR or None) if _use_proxy() else None

    async with httpx.AsyncClient(proxy=proxy) as client:
        response = await client.get(
            url,
            params={"q": query, "format": "json", "language": locale},
            timeout=30,
        )
        response.raise_for_status()
        return SearXNGResults.model_validate(response.json())


register_provider(prio, requires, asearch)


if __name__ == "__main__":
    async def main():
        from maica import init

        init()
        print(await asearch("pizza"))

    asyncio.run(main())
