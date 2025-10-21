import asyncio
import json

from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
from .mcp_middleware import prep_bin, _serp_bin
from maica.maica_utils import *

def pkg_init_mcp_serp():
    global SERP_BIN
    SERP_BIN = _serp_bin()
    prep_bin(SERP_BIN)

async def asearch(query, target_lang='zh'):
    """
    Async google searcher with (somewhat) MCP protocol.
    Uses an external precompiled NodeJS project to scrape, refer to https://github.com/edgeinfinity1/mi-search-mcp
    """
    locale = 'zh-CN' if target_lang == 'zh' else 'en-US'

    serp_initiation_args = {
        "command": SERP_BIN,
        "args": [],
        "env": {k: G.A.PROXY_ADDR for k in ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']},
    }
    serp_initiation_args["env"].update({
        "DISPLAY": (load_env("DISPLAY") or '') if G.A.ENABLE_X11 == '1' else ''
    })

    serp_initiation = StdioServerParameters(**serp_initiation_args)

    async with stdio_client(serp_initiation) as (stdio, write):
        async with ClientSession(stdio, write) as session:
            await session.initialize()

            # tools = await session.list_tools():
            response = await session.call_tool('search', {'queries': [query], "limit": 10, "locale": locale, "debug": False})
            response_json = json.loads(response.content[0].text)
            return [{"title": it['title'], "text": it['snippet']} for it in response_json['searches'][0]['results']]

if __name__ == '__main__':
    from maica import init
    init()
    pkg_init_mcp_serp()
    print(asyncio.run(asearch("测试")))