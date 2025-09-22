import aiomysql
import aiosqlite
import asyncio
import traceback
import json
from typing import *
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from maica.maica_utils import *
from .setting_utils import *
from .locater import *
"""Import layer 3"""

def pkg_init_connection_utils():
    global DB_ADDR, DB_USER, DB_PASSWORD, AUTH_DB, MAICA_DB, MCORE_ADDR, MCORE_KEY, MCORE_CHOICE, MFOCUS_ADDR, MFOCUS_KEY, MFOCUS_CHOICE, ConnUtils
    DB_ADDR = load_env('MAICA_DB_ADDR')
    DB_USER = load_env('MAICA_DB_USER')
    DB_PASSWORD = load_env('MAICA_DB_PASSWORD')
    AUTH_DB = load_env('MAICA_AUTH_DB')
    MAICA_DB = load_env('MAICA_DATA_DB')
    MCORE_ADDR = load_env('MAICA_MCORE_ADDR')
    MCORE_KEY = load_env('MAICA_MCORE_KEY')
    MCORE_CHOICE = load_env('MAICA_MCORE_CHOICE')
    MFOCUS_ADDR = load_env('MAICA_MFOCUS_ADDR')
    MFOCUS_KEY = load_env('MAICA_MFOCUS_KEY')
    MFOCUS_CHOICE = load_env('MAICA_MFOCUS_CHOICE')

    if DB_ADDR != "sqlite":
        """We suppose we're using MySQL."""
        async def auth_pool(ro=True):
            return await DbPoolCoroutine.async_create(
                host=DB_ADDR,
                db=AUTH_DB,
                user=DB_USER,
                password=DB_PASSWORD,
                ro=ro,
            )

        async def maica_pool(ro=False):
            return await DbPoolCoroutine.async_create(
                host=DB_ADDR,
                db=MAICA_DB,
                user=DB_USER,
                password=DB_PASSWORD,
                ro=ro,
            )
        
        async def basic_pool(ro=False):
            return await DbPoolCoroutine.async_create(
                host=DB_ADDR,
                db=None,
                user=DB_USER,
                password=DB_PASSWORD,
                ro=ro,
            )
    else:
        """We suppose we're using SQLite."""
        async def auth_pool(ro=True):
            return await SqliteDbPoolCoroutine.async_create(
                db=get_inner_path(AUTH_DB)
            )
        
        async def maica_pool(ro=False):
            return await SqliteDbPoolCoroutine.async_create(
                db=get_inner_path(MAICA_DB)
            )
        
        async def basic_pool(ro=False):
            """
            There's no host concept in SQLite, so no basic pool.
            """
            return None
    setattr(ConnUtils, 'auth_pool', auth_pool)
    setattr(ConnUtils, 'maica_pool', maica_pool)
    setattr(ConnUtils, 'basic_pool', basic_pool)

RETRY_TIMES = 3

def test_logger(func):
    async def wrapper(self, expression, values, *args, **kwargs):
        print(f'Query: {expression}\nValues: {values}')
        result = await func(self, expression, values, *args, **kwargs)
        print(f'Result: {result}')
        return result
    return wrapper

class DbPoolCoroutine(AsyncCreator):
    """Maintain a database connection pool so you don't have to."""
    def __init__(self, db, host, user, password, ro=False):
        self.db, self.host, self.user, self.password, self.ro = db, host, user, password, ro

    async def _ainit(self):
        self.pool: aiomysql.Pool = await aiomysql.create_pool(host=self.host, user=self.user, password=self.password, db=self.db)

    async def keep_alive(self):
        try:
            async with self.pool.acquire():
                pass
            return
        except Exception:
            await messenger(info=f"Recreating {self.db} pool since cannot acquire", type=MsgType.WARN)
            try:
                self.pool.close()
                await self._ainit()
            except Exception:
                raise MaicaDbError(f'Failure when trying reconnecting to {self.db}', '502', 'db_connection_failed')

    # @test_logger
    async def query_get(self, expression, values=None, fetchall=False) -> list:
        results = None
        for tries in range(RETRY_TIMES):
            try:
                await self.keep_alive()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        if not values:
                            await cur.execute(expression)
                        else:
                            await cur.execute(expression, values)
                        results = await cur.fetchone() if not fetchall else await cur.fetchall()
                break
            except Exception as e:
                if tries < RETRY_TIMES - 1:
                    await messenger(info=f'DB temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    raise MaicaDbError(f'DB get query failure after {str(tries + 1)} times: {str(e)}', '502', 'db_get_failed')
        return results

    # @test_logger
    async def query_modify(self, expression, values=None, fetchall=False) -> int:
        if self.ro:
            raise MaicaDbError(f'DB marked as ro, no modify permitted', '511', 'db_modification_denied')
        lrid = None
        for tries in range(RETRY_TIMES):
            try:
                await self.keep_alive()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        if not values:
                            await cur.execute(expression)
                        else:
                            await cur.execute(expression, values)
                        await conn.commit()
                        lrid = cur.lastrowid
                break
            except Exception as e:
                if tries < RETRY_TIMES - 1:
                    await messenger(info=f'DB temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    raise MaicaDbError(f'DB modify query failure after {str(tries + 1)} times: {str(e)}', '502', 'db_modify_failed')
        return lrid
    
    async def close(self):
        """These connection pools shouldn't be closed manually in runtime. We implement it anyway."""
        self.pool.close()
        await self.pool.wait_closed()

class SqliteDbPoolCoroutine(DbPoolCoroutine):
    """SQLite-specific database pool coroutine."""

    def __init__(self, db, host=None, user=None, password=None, ro=False):
        self.db_path = db
        self.ro = ro
        self.pool = None

    async def _ainit(self):
        """Initialize SQLite connection pool."""
        try:
            self.pool = aiosqlite.connect(self.db_path)
            await self.pool.__aenter__()
            if self.ro:
                await self.pool.execute("PRAGMA query_only = ON")
        except Exception as e:
            raise MaicaDbError(f'Failed to initialize SQLite connection: {str(e)}', '502', 'sqlite_init_failed')

    async def keep_alive(self):
        """Check and maintain SQLite connection."""
        try:
            await self.pool.execute("SELECT 1")
        except Exception:
            await messenger(info=f"Recreating {self.db} pool since cannot acquire", type=MsgType.WARN)
            try:
                if self.pool:
                    await self.pool.close()
                await self._ainit()
            except Exception:
                raise MaicaDbError(f'Failure when trying reconnecting to {self.db}', '502', 'db_connection_failed')

    @Decos.escape_sqlite_expression
    # @test_logger
    async def query_get(self, expression, values=None, fetchall=False) -> list:
        """Execute SELECT query on SQLite database."""
        results = None
        for tries in range(RETRY_TIMES):
            try:
                await self.keep_alive()
                if not values:
                    cursor = await self.pool.execute(expression)
                else:
                    cursor = await self.pool.execute(expression, values)
                results = await cursor.fetchone() if not fetchall else await cursor.fetchall()
                await cursor.close()
                break
            except Exception as e:
                if tries < RETRY_TIMES - 1:
                    await messenger(info=f'SQLite temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    raise MaicaDbError(f'SQLite get query failure after {str(tries + 1)} times: {str(e)}', '502', 'sqlite_get_failed')
        return results

    @Decos.escape_sqlite_expression
    # @test_logger
    async def query_modify(self, expression, values=None, fetchall=False) -> int:
        """Execute INSERT/UPDATE/DELETE query on SQLite database."""
        if self.ro:
            raise MaicaDbError(f'DB marked as ro, no modify permitted', '511', 'sqlite_modification_denied')
        lrid = None
        for tries in range(RETRY_TIMES):
            try:
                await self.keep_alive()
                if not values:
                    cursor = await self.pool.execute(expression)
                else:
                    cursor = await self.pool.execute(expression, values)
                await self.pool.commit()
                lrid = cursor.lastrowid
                await cursor.close()
                break
            except Exception as e:
                if tries < RETRY_TIMES - 1:
                    await messenger(info=f'SQLite temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    raise MaicaDbError(f'SQLite modify query failure after {str(tries + 1)} times: {str(e)}', '502', 'sqlite_modify_failed')
        return lrid

    async def close(self):
        """Close SQLite connection."""
        if self.pool:
            await self.pool.close()

class AiConnCoroutine(AsyncCreator):
    """Maintain an AI connection so you don't have to."""
    def __init__(self, api_key, base_url, name='mcore_cli', model: Union[int, str]=0):
        self.test = False
        self.api_key, self.base_url, self.name, self.model = api_key, base_url, name, model
        self.websocket = None
        self.traceray_id = ''
        self.gen_kwargs = {}

    async def _ainit(self):
        if not self.base_url:
            self.test = True
            return
        else:
            try:
                self._open_socket()
                await self.keep_alive()
            except Exception:
                self.test = True
                return

    def _open_socket(self):
        self.socket = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def init_rsc(self, rsc: FscPlain.RealtimeSocketsContainer):
        """AiConn can actually work without rsc, so we make it individual."""
        self.websocket, self.traceray_id = rsc.websocket, rsc.traceray_id

    def default_params(self, **kwargs):
        """These params will always be applied to generations. Overwritting."""
        self.gen_kwargs = kwargs

    async def keep_alive(self):
        try:
            model_list = await self.socket.models.list()
            models = model_list.data
            if isinstance(self.model, int):
                self.model_actual = models[0].id
            else:
                self.model_actual = self.model
        except Exception:
            await messenger(None, f'{self.name}_reconn', f"Recreating {self.name} client since cannot conn", '301', type=MsgType.WARN)
            try:
                try:
                    await self.socket.close()
                except Exception:
                    pass
                self._open_socket()
            except Exception:
                raise MaicaResponseError(f'Failure when trying reconnecting to {self.name}', '502', f'{self.name}_connection_failed')
            
    async def make_completion(self, **kwargs) -> ChatCompletion:
        kwargs.update(
            {
                "model": self.model_actual
            }
        )
        for tries in range(RETRY_TIMES):
            try:
                await self.keep_alive()
                task_stream_resp = asyncio.create_task(self.socket.chat.completions.create(**self.gen_kwargs, **kwargs))
                await task_stream_resp
                return task_stream_resp.result()
            except Exception as e:
                if tries < RETRY_TIMES - 1:
                    await messenger(info=f'Model temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    raise MaicaResponseError(f'{self.name} AI query failure after {str(tries + 1)} times: {str(e)}', '502', f'{self.name}_query_failed')

class ConnUtils():
    """Just a wrapping for functions."""
    async def auth_pool(ro=True):
        """Dummy."""
    async def maica_pool(ro=False):
        """Dummy."""
    async def basic_pool(ro=False):
        """Dummy."""
    async def mcore_conn():
        conn = await AiConnCoroutine.async_create(
            api_key=MCORE_KEY,
            base_url=MCORE_ADDR,
            name='mcore_cli',
            model=MCORE_CHOICE if MCORE_CHOICE else 0,
        )
        conn.default_params(**json.loads(load_env('MAICA_MCORE_EXTRA')))
        return conn

    async def mfocus_conn():
        conn = await AiConnCoroutine.async_create(
            api_key=MFOCUS_KEY,
            base_url=MFOCUS_ADDR,
            name='mfocus_cli',
            model=MFOCUS_CHOICE if MFOCUS_CHOICE else 0,
        )
        conn.default_params(**json.loads(load_env('MAICA_MFOCUS_EXTRA')))
        return conn

async def validate_input(input: Union[str, dict, list], limit: int=4096, rsc: Optional[FscPlain.RealtimeSocketsContainer]=None, must: list=[], warn: list=[]) -> Union[dict, list]:
    """
    Mostly for ws.
    """
    if not input:
        raise MaicaInputWarning('Input is empty', '410', 'maica_input_validation_denied')
    
    if isinstance(input, str):
        if len(input) > limit:
            raise MaicaInputWarning('Input length exceeded', '413', 'maica_input_validation_denied')
        try:
            input_json = json.loads(input)
        except Exception:
            raise MaicaInputWarning('Request body not JSON', '400', 'maica_input_validation_denied')
    elif isinstance(input, dict | list):
        if len(str(input)) > limit:
            raise MaicaInputWarning('Input length exceeded', '413', 'maica_input_validation_denied')
        input_json = input
    else:
        raise MaicaInputError('Input must be string or JSON-like', '400', 'maica_input_validation_denied')

    if must:
        for mustkey in must:
            if input_json.get(mustkey) is None:
                raise MaicaInputWarning(f'Request contains no necessary {mustkey}', '405', 'maica_input_validation_denied')
    if warn:
        for warnkey in warn:
            if input_json.get(warnkey) is None:
                if rsc:
                    await messenger(rsc.websocket, 'maica_future_warning', f'Requests containing no {warnkey} will likely be deprecated in the future', '302', type=MsgType.WARN)
    
    return input_json
