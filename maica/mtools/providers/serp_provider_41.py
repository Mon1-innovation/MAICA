"""
This is third party (https://brightdata.com/) implementation.
Works okay, decent price, I know nothing else.
"""

import asyncio
import httpx
import json
import urllib.parse

from typing import *
from maica.maica_utils import *
from maica.mtools.api_keys import TpAPIKeys

requires = ['BRIGHTDATA_ZONE', 'BRIGHTDATA_KEY']
async def asearch(query, target_lang: Literal['zh', 'en']='zh'):
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
    json_payload = json.dumps({
        "zone": zone,
        "url": f"https://www.google.com/search?q={urllib.parse.quote(query)}&gl={gl}&hl={hl}&brd_json=1",
        "format": "raw",
    })

    async with httpx.AsyncClient(proxy=load_env('MAICA_PROXY_ADDR')) as client:
        response = await client.post(url, headers=headers, data=json_payload, timeout=30)
        response_json = response.json()

    print(json.dumps(response_json, indent=2))

    results_formatted = [{"title": it['title'], "text": it['description']} for it in response_json['organic'] if 'description' in it]
    return results_formatted

if __name__ == "__main__":
    async def main():
        from maica import init
        init()
        res = await asearch("今天的新闻")
        print(res)
        print(len(res))

    asyncio.run(main())
    