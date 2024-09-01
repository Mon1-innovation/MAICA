import asyncio
import time
import aiomysql
import functools
import nest_asyncio
from loadenv import load_env

class consql:
    nest_asyncio.apply()
    authpool = None
    maicapool = None
    def __init__(
        self,
        host = load_env('DB_ADDR'), 
        user = load_env('DB_USER'),
        password = load_env('DB_PASSWORD'),
        authdb = load_env('AUTHENTICATOR_DB'),
        maicadb = load_env('MAICA_DB')
    ):
        self.host, self.user, self.password, self.authdb, self.maicadb = host, user, password, authdb, maicadb
        self.kwargs = {}
        self.loop = asyncio.new_event_loop()
        asyncio.run(self._init_pools())

    def __del__(self):
        self.loop.run_until_complete(self._close_pools())

    async def _init_pools(self) -> None:
        global authpool, maicapool
        future = asyncio.gather(aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.authdb),aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.maicadb))
        await future
        [authpool, maicapool] = future.result()

    async def _close_pools(self) -> None:
        global authpool, maicapool
        authpool.close()
        maicapool.close()
        await authpool.wait_closed()
        await maicapool.wait_closed()

    async def send_query(self, expression, pool='maicapool', fetchall=False):
        global authpool, maicapool
        pool = authpool if pool == 'authpool' else maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(expression)
                print(cur.description)
                results = await cur.fetchone() if not fetchall else await cur.fetchall()
                print(results)

a = consql()
asyncio.run(a.send_query(expression=("SELECT 42;"), fetchall=True))
#asyncio.run(a._close_pools())
