"""
This is third party (https://brightdata.com/) implementation.
Works okay, decent price, I know nothing else.
"""

import asyncio
import httpx
import json
import urllib.parse

from typing import *
from pydantic import model_validator
from maica.maica_utils import *
from maica.mtools.api_keys import TpAPIKeys
from .base import register_provider, SerpResults

prio = 41
requires = ['BRIGHTDATA_ZONE', 'BRIGHTDATA_KEY']

class BdSerpResults(SerpResults):
    @model_validator(mode="before")
    @classmethod
    def auto_transform(cls, data: Any):
        if isinstance(data, dict):
            new_data = {}
            new_data["results"] = data.get("organic")
            data = new_data
        return data

async def asearch(query, target_lang: Literal['zh', 'en', 'auto']='zh'):
    host = "api.brightdata.com"
    url = f"https://{host}/request"
    zone = TpAPIKeys.BRIGHTDATA_ZONE
    key = TpAPIKeys.BRIGHTDATA_KEY
    gl = 'CN' if target_lang == 'zh' else 'US'
    hl = 'zh-CN' if target_lang == 'zh' else 'en'

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "zone": zone,
        "url": f"https://www.google.com/search?q={urllib.parse.quote(query)}&gl={gl}&hl={hl}&brd_json=1",
        "format": "raw",
    }
    json_payload = json.dumps(payload)

    async with httpx.AsyncClient(proxy=G.A.PROXY_ADDR or None) as client:
        response = await client.post(url, headers=headers, data=json_payload, timeout=30)
        response.raise_for_status()
        response_json = response.json()

    # print(json.dumps(response_json, ensure_ascii=False, indent=2))

    res_m = BdSerpResults.model_validate(response_json)

    return res_m

register_provider(prio, requires, asearch)

if __name__ == "__main__":
    async def main():
        from maica import init
        init()
        res = await asearch("pizza")
        print(res)

    asyncio.run(main())
