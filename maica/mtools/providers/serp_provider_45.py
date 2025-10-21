"""
This is third party (https://app.scrapeless.com/) implementation.
Works okay, decent price, I know nothing else.
"""

import asyncio
import httpx
import json

from typing import *
from maica.maica_utils import *
from maica.mtools.api_keys import TpAPIKeys

requires = ['SCRAPELESS_SERP']
async def asearch(query, target_lang: Literal['zh', 'en']='zh'):
    host = "api.scrapeless.com"
    url = f"https://{host}/api/v1/scraper/request"
    token = TpAPIKeys.SCRAPELESS_SERP

    headers = {
        "x-api-token": token,
        "Content-Type": "application/json"
    }
    json_payload = json.dumps({
        "actor": "scraper.google.search",
        "input": {
            "q": query,
            "gl": "cn" if target_lang == 'zh' else 'us',
            "hl": "zh" if target_lang == 'zh' else 'en',
            "google_domain": "google.com",
            "num": 20,
        },
        "waiting": True
    })

    async with httpx.AsyncClient(proxy=G.A.PROXY_ADDR) as client:
        response = await client.post(url, headers=headers, data=json_payload, timeout=30)
        response_json = response.json()

    results_formatted = [{"title": it['title'], "text": it['snippet']} for it in response_json['organic_results'] if 'snippet' in it]
    return results_formatted

if __name__ == "__main__":
    async def main():
        from maica import init
        init()
        await asearch("今天的新闻")

    asyncio.run(main())
    