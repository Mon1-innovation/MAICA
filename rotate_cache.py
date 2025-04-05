import nest_asyncio
nest_asyncio.apply()
import asyncio
import aiomysql
import time
from maica_utils import *

class rotation_instance():

    def __init__(
        self,
        host = load_env('DB_ADDR'), 
        user = load_env('DB_USER'),
        password = load_env('DB_PASSWORD'),
        authdb = load_env('AUTHENTICATOR_DB'),
        maicadb = load_env('MAICA_DB'),
        login = load_env('LOGIN_VERIFICATION'),
        test = False
    ):
        self.host, self.user, self.password, self.authdb, self.maicadb, self.login, self.test = host, user, password, authdb, maicadb, login, test
        asyncio.run(self.create_pool())
        asyncio.run(self.rotate_caches())
    
    async def create_pool(self):
        self.loop = asyncio.get_event_loop()
        self.maicapool = await aiomysql.create_pool(host=self.host, user=self.user, password=self.password, loop=self.loop, db=self.maicadb, autocommit=True)
    
    async def send_modify(self, expression, values=None):
        pool = self.maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if not values:
                    await cur.execute(expression)
                else:
                    await cur.execute(expression, values)
                await conn.commit()
                lrid = cur.lastrowid
        return lrid
    
    async def send_query(self, expression, values=None, fetchall=False):
        pool = self.maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if not values:
                    await cur.execute(expression)
                else:
                    await cur.execute(expression, values)
                results = await cur.fetchone() if not fetchall else await cur.fetchall()
        return results

    async def rotate_caches(self, keep_time=load_env('ROTATE_MSCACHE')):
        timestamp = time.time()
        sql_expression1 = "SELECT spire_id, timestamp FROM ms_cache"
        sql_expression2 = "DELETE FROM ms_cache WHERE spire_id = %s"
        result = await self.send_query(sql_expression1, None, True)
        for row in result:
            if float(row[1]) + float(keep_time) * 3600 <= timestamp:
                await self.send_modify(sql_expression2, (row[0]))

if __name__ == '__main__':
    r = rotation_instance()
