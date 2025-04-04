import asyncio
import httpx
import functools
from loadenv import load_env

async def wrap_run_in_exc(loop, func, *args, **kwargs):
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    return result

async def get_json(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
    try:
        for tries in range(0, 3):
            try:
                client = httpx.AsyncClient(proxy=load_env("PROXY_ADDR"))
                res = (await client.get(url, headers=headers)).json()
                break
            except:
                if tries < 2:
                    print('Http temporary failure')
                    await asyncio.sleep(100)
                else:
                    raise Exception('Http connection failure')
    except:
        raise Exception('Http connection failure')
    finally:
        await client.aclose()
    return res