"""
This is the local MCP tool implementation.
Works well for minor deployment, but relatively slow & some performance consume & might hit captchas.
"""
import asyncio

from typing import *
from pydantic import model_validator
from .base import register_provider, SerpResults

prio = 97
requires = []

class McpSerpResults(SerpResults):
    @model_validator(mode="before")
    @classmethod
    def auto_transform(cls, data: Any):
        if isinstance(data, dict):
            new_data = {}
            new_data["results"] = data.get("searches")[0].get("results")
            for d in new_data["results"]:
                d["description"] = d.get("snippet")
            data = new_data
        return data

from maica.mtools.mcp import _asearch

async def asearch(query, target_lang: Literal['zh', 'en', 'auto']='zh'):
    """Wrapping."""
    res = await _asearch(query, target_lang)
    res_m = McpSerpResults.model_validate_json(res)
    return res_m

register_provider(prio, requires, asearch)

if __name__ == "__main__":
    async def main():
        from maica import init
        init()
        res = await asearch("pizza")
        print(res)

    asyncio.run(main())
    