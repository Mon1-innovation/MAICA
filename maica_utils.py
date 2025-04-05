import asyncio
import httpx
import functools
import hashlib
import os
from dotenv import load_dotenv as __load_dotenv

def load_env(key):
    __load_dotenv()
    result = os.getenv(key)
    if not result:
        raise ValueError("Environment variables are missing.")
    return result

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
                    print('HTTP temporary failure')
                    await asyncio.sleep(0.5)
                else:
                    raise Exception('Http connection failure')
    except:
        raise Exception('Http connection failure')
    finally:
        await client.aclose()
    return res

async def hash_sha256(str):
    def hash_sync(str):
        return hashlib.new('sha256', str).hexdigest()
    return await wrap_run_in_exc(None, hash_sync, str)

