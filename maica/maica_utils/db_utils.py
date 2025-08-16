import aiomysql
import asyncio
from .maica_utils import *

class db_pool_wrapping():

    def __init__(self, host, db, user, password):
        self.host, self.db, self.user, self.password = host, db, user, password
        self.loop = asyncio.get_event_loop()
        asyncio.run(self._ainit())

    async def _ainit(self):
        self.pool: aiomysql.Pool = await aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.authdb,loop=self.loop,autocommit=True)

    async def keep_alive(self):
        try:
            async with self.pool.acquire():
                pass
        except:
            await common_context_handler(None, f'{self.db}_reconn', f"Recreated {self.db} pool since cannot acquire", '301', type='warn')
            try:
                self.pool.close()
                await self._ainit()
            except:
                error = MaicaDbError(f'Failure when trying reconnecting to {self.db}', '502')
                await common_context_handler(None, f'{self.db}_reconn_failure', traceray_id='db_handling', type='error')

    async def query_get(self, expression, values=None, fetchall=False) -> list:
        results = None
        for tries in range(0, 3):
            try:
                self.keep_alive()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        if not values:
                            await cur.execute(expression)
                        else:
                            await cur.execute(expression, values)
                        results = await cur.fetchone() if not fetchall else await cur.fetchall()
                break
            except:
                if tries < 2:
                    await common_context_handler(info=f'DB temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    error = MaicaDbError(f'DB connection failure after {str(tries + 1)} times')
                    await common_context_handler(None, 'db_connection_failed', traceray_id='db_handling', error=error)
        return results

    async def query_modify(self, expression, values=None, fetchall=False) -> list:
        lrid = None
        for tries in range(0, 3):
            try:
                self.keep_alive()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        if not values:
                            await cur.execute(expression)
                        else:
                            await cur.execute(expression, values)
                        await conn.commit()
                        lrid = cur.lastrowid
                break
            except:
                if tries < 2:
                    await common_context_handler(info=f'DB temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    error = MaicaDbError(f'DB connection failure after {str(tries + 1)} times')
                    await common_context_handler(None, 'db_connection_failed', traceray_id='db_handling', error=error)
        return lrid
