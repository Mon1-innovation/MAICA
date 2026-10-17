"""DeepSeek Search API SERP provider."""

import asyncio
from typing import Any

import httpx
from pydantic import model_validator

from maica.maica_utils import G, TargetLangType
from maica.mtools.api_keys import TpAPIKeys
from .base import SerpResults, register_provider


prio = 35
requires = ["DEEPSEEK_SEARCH_KEY"]

_SEARCH_URL = "https://api.deepseek.com/v1/tools/search"
_RESULT_COUNT = 10


class DeepSeekResults(SerpResults):
    @model_validator(mode="before")
    @classmethod
    def auto_transform(cls, data: Any):
        if not isinstance(data, dict):
            return data

        results = []
        for rank, item in enumerate(data.get("results") or [], start=1):
            if not isinstance(item, dict):
                continue

            description = next(
                (
                    value
                    for field in ("summary", "snippet", "content")
                    if isinstance(value := item.get(field), str) and value.strip()
                ),
                "",
            )
            results.append(
                {
                    "title": item.get("title") or "",
                    "description": description,
                    "rank": rank,
                    "link": item.get("url"),
                    "source": item.get("site_name"),
                }
            )

        return {"results": results}


async def asearch(query: str, target_lang: TargetLangType = "zh") -> SerpResults:
    headers = {
        "Authorization": f"Bearer {TpAPIKeys.DEEPSEEK_SEARCH_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "count": _RESULT_COUNT,
        "need_content": False,
    }

    async with httpx.AsyncClient(proxy=G.A.PROXY_ADDR or None) as client:
        response = await client.post(
            _SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return DeepSeekResults.model_validate(response.json())


register_provider(prio, requires, asearch)


if __name__ == "__main__":
    async def main():
        from maica import init

        init()
        print(await asearch("pizza"))

    asyncio.run(main())
