"""
This is third party (https://serper.dev/) implementation.
Works okay, decent price, I know nothing else.
"""

import asyncio
import httpx
import json

from typing import *
from maica.maica_utils import *
from maica.mtools.api_keys import TpAPIKeys

requires = ['SERPER_SERP']
async def asearch(query, target_lang: Literal['zh', 'en']='zh'):
    host = "google.serper.dev"
    url = f"https://{host}/search"
    token = TpAPIKeys.SERPER_SERP

    headers = {
        "X-API-KEY": token,
        "Content-Type": "application/json"
    }
    json_payload = json.dumps({
        "q": query,
        "gl": 'cn' if target_lang == 'zh' else 'us',
        'hl': 'zh-cn' if target_lang == 'zh' else 'en',
    })

    async with httpx.AsyncClient(proxy=G.A.PROXY_ADDR) as client:
        response = await client.post(url, headers=headers, data=json_payload, timeout=30)
        response_json = response.json()

    results_formatted = [{"title": it['title'], "text": it['snippet']} for it in response_json['organic'] if 'snippet' in it]
    return results_formatted

if __name__ == "__main__":
    async def main():
        from maica import init
        init()
        print(await asearch("今天的新闻"))

    asyncio.run(main())
    