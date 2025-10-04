import asyncio

from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
from .mcp_middleware import prep_bin, _serp_bin
from maica.maica_utils import *

def pkg_init_mcp_serp():
    global PROXY_ADDR, ENABLE_X11, SERP_BIN
    PROXY_ADDR = load_env('MAICA_PROXY_ADDR')
    ENABLE_X11 = load_env('MAICA_ENABLE_X11')
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
        "env": {k: PROXY_ADDR for k in ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']},
    }
    serp_initiation_args["env"].update({
        "DISPLAY": (load_env("DISPLAY") or '') if ENABLE_X11 == '1' else ''
    })

    serp_initiation = StdioServerParameters(**serp_initiation_args)

    async with stdio_client(serp_initiation) as (stdio, write):
        async with ClientSession(stdio, write) as session:
            await session.initialize()

            # tools = await session.list_tools():
            response = await session.call_tool('search', {'queries': [query], "limit": 10, "locale": locale, "debug": False})
            return response.content[0].text

if __name__ == '__main__':
    from maica import init
    init()
    pkg_init_mcp_serp()
    print(asyncio.run(asearch("测试")))