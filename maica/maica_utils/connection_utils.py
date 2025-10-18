"""Import layer 3"""
import aiomysql
import aiosqlite
import asyncio
import traceback
import json
import openai
from tenacity import *
from typing import *
from typing_extensions import deprecated
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from maica.maica_utils import *
from .setting_utils import *
from .container_early import *
from .locater import *

RETRYABLE_EXCEPTIONS = (
    aiomysql.OperationalError,
    aiomysql.InterfaceError,
    ConnectionError,
    TimeoutError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
)

def conn_retryer_factory(
    max_attempts: int=3,
    min_wait: float=1,
    max_wait: float=10,
    retry_exceptions=RETRYABLE_EXCEPTIONS,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mostly for instance methods."""
    def decorator(func):
        async def log_retry(retry_state):
            self = retry_state.args[0] if retry_state else None
            rsc = getattr(self, 'rsc', None); name = getattr(self, 'name', 'anon_conn')
            websocket = rsc.websocket if rsc else None; traceray_id = rsc.traceray_id if rsc else ''
            await messenger(websocket=websocket, status=f'{name}_temp_failure', info=f'{name} temporary failure, retrying...', code='304', traceray_id=traceray_id, type=MsgType.WARN)

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_exceptions),
            before_sleep=log_retry,
            reraise=True,
        )
        async def wrapper(self, *args, **kwargs):
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator

def pkg_init_connection_utils():
    global DB_ADDR, DB_USER, DB_PASSWORD, AUTH_DB, MAICA_DB, MCORE_ADDR, MCORE_KEY
    global MCORE_CHOICE, MFOCUS_ADDR, MFOCUS_KEY, MFOCUS_CHOICE, MVISTA_ADDR, MVISTA_KEY
    global MVISTA_CHOICE, MNERVE_ADDR, MNERVE_KEY, MNERVE_CHOICE, THINK_POSTFIX
    global NOTHINK_POSTFIX, ConnUtils

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

    MVISTA_ADDR = load_env('MAICA_MVISTA_ADDR')
    MVISTA_KEY = load_env('MAICA_MVISTA_KEY')
    MVISTA_CHOICE = load_env('MAICA_MVISTA_CHOICE')

    MNERVE_ADDR = load_env('MAICA_MNERVE_ADDR')
    MNERVE_KEY = load_env('MAICA_MNERVE_KEY')
    MNERVE_CHOICE = load_env('MAICA_MNERVE_CHOICE')

    THINK_POSTFIX = load_env('MAICA_MFOCUS_THINK')
    NOTHINK_POSTFIX = load_env('MAICA_MFOCUS_NOTHINK')

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

def test_logger(func):
    async def wrapper(self, expression, values, *args, **kwargs):
        print(f'Query: {expression}\nValues: {values}')
        result = await func(self, expression, values, *args, **kwargs)
        print(f'Result: {result}')
        return result
    return wrapper

def apply_postfix(messages, thinking: Literal[True, False, None]=None):
    last_msg: dict = messages[-1]
    if last_msg.get('role') == 'user':
        if isinstance(last_msg.get('content'), str):
            match thinking:
                case True:
                    last_msg['content'] += THINK_POSTFIX
                case False:
                    last_msg['content'] += NOTHINK_POSTFIX
        elif isinstance(last_msg.get('content'), list):
            d: dict
            for d in last_msg['content']:
                if d.get('type') == 'text' and isinstance(d.get('text'), str):
                    match thinking:
                        case True:
                            d['text'] += THINK_POSTFIX
                        case False:
                            d['text'] += NOTHINK_POSTFIX
                    break
        else:
            raise MaicaInputError('Context schedule not recognizable')
    return messages

class DbPoolCoroutine(AsyncCreator):
    """Maintain a database connection pool so you don't have to."""

    db_type = 'mysql'

    def __init__(self, db, host, user, password, ro=False):
        self.db, self.host, self.user, self.password, self.ro = db, host, user, password, ro
        self.name = self.db
        self.pool: aiomysql.Pool = None

    @Decos.catch_exceptions
    async def _ainit(self):
        """Initialize MySQL connection pool."""
        self.pool = await aiomysql.create_pool(host=self.host, user=self.user, password=self.password, db=self.db)

    @Decos.catch_exceptions
    async def keep_alive(self):
        """Check and maintain MySQL connection."""
        try:
            async with self.pool.acquire():
                pass
            return
        except Exception:
            await messenger(info=f"Recreating {self.name} pool since cannot acquire", type=MsgType.WARN)
            try: self.pool.close()
            except Exception:...
            await self._ainit()

    # @test_logger
    @Decos.catch_exceptions
    @conn_retryer_factory()
    async def query_get(self, expression, values=None, fetchall=False, inherit_conn: Optional[aiomysql.Connection]=None) -> list:
        """Execute SELECT query on MySQL database."""
        async def _query_get(cur, expression, values, fetchall) -> list:
            if not values:
                await cur.execute(expression)
            else:
                await cur.execute(expression, values)
            results = await cur.fetchone() if not fetchall else await cur.fetchall()
            return results

        results = None
        await self.keep_alive()

        if not inherit_conn:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    results = await _query_get(cur, expression, values, fetchall)
                    
                    # aiomysql caches results in some cases if you don't commit
                    # Really weird to me
                    await conn.commit()
        else:
            async with inherit_conn.cursor() as cur:
                results = await _query_get(cur, expression, values, fetchall)
                # We leave the transactional manager handling commitments

        return results

    # @test_logger
    @Decos.catch_exceptions
    @conn_retryer_factory()
    async def query_modify(self, expression, values=None, fetchall=False, inherit_conn: Optional[aiomysql.Connection]=None) -> int:
        """Execute INSERT/UPDATE/DELETE query on MySQL database."""
        if self.ro:
            raise MaicaDbError(f'DB marked as ro, no modification permitted', '511', 'db_modification_denied')
        
        async def _query_modify(cur, expression, values, fetchall) -> Optional[int]:
            if not values:
                await cur.execute(expression)
            else:
                await cur.execute(expression, values)
            lrid = cur.lastrowid
            return lrid

        lrid = None
        await self.keep_alive()

        if not inherit_conn:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    lrid = await _query_modify(cur, expression, values, fetchall)
                    await conn.commit()
        else:
            async with inherit_conn.cursor() as cur:
                lrid = await _query_modify(cur, expression, values, fetchall)
                # We leave the transactional manager handling commitments

        return lrid
    
    async def close(self):
        """Close before closing coroutine to avoid errors."""
        self.pool.close()
        await self.pool.wait_closed()

    def summon_sub(self, rsc: Optional[RealtimeSocketsContainer]=None):
        """Summons a per-user instance."""
        return SubDbPoolCoroutine(self, rsc)

class SubDbPoolCoroutine(DbPoolCoroutine):
    """Per-user DbPoolCoroutine."""
    def __init__(self, parent: DbPoolCoroutine, rsc: Optional[RealtimeSocketsContainer]=None):
        """Must summon from a parent object."""
        for k, v in vars(parent).items():
            setattr(self, k, v)

        self.parent = parent; self.rsc = rsc

    async def _ainit(self):
        """Do not use async_create."""
        raise NotImplementedError
    
    async def keep_alive(self):
        await self.parent.keep_alive()

    async def close(self):...

class SqliteDbPoolCoroutine(DbPoolCoroutine):
    """
    SQLite-specific database pool coroutine.
    Notice: since SQLite only allow rollback for TRANSACTION which differs
    from MySQL, we're not implementing transaction management for SQLite for
    now. 
    """

    db_type = 'sqlite'

    def __init__(self, db, host=None, user=None, password=None, ro=False):
        self.db_path = db
        self.name = self.db_path
        self.ro = ro
        self.pool: aiosqlite.Connection = None

    @Decos.catch_exceptions
    async def _ainit(self):
        """
        Initialize SQLite connection pool.
        Notice: there is actually no 'pool' concept in SQLite, but
        we're considering connections as pools to keep symmetry with
        the corresponding MySQL functions.
        """
        self.pool = aiosqlite.connect(self.db_path)
        await self.pool.__aenter__()
        if self.ro:
            await self.pool.execute("PRAGMA query_only = ON")

    @Decos.catch_exceptions
    async def keep_alive(self):
        """Check and maintain SQLite connection."""
        try:
            await self.pool.execute("SELECT 1")
        except Exception:
            await messenger(info=f"Recreating {self.db} pool since cannot acquire", type=MsgType.WARN)
            try: await self.pool.close()
            except Exception:...
            await self._ainit()

    # @test_logger
    @Decos.catch_exceptions
    @Decos.escape_sqlite_expression
    @conn_retryer_factory()
    async def query_get(self, expression, values=None, fetchall=False) -> list:
        """Execute SELECT query on SQLite database."""
        results = None
        await self.keep_alive()

        if not values:
            cursor = await self.pool.execute(expression)
        else:
            cursor = await self.pool.execute(expression, values)
        results = await cursor.fetchone() if not fetchall else await cursor.fetchall()
        await self.pool.commit()

        return results

    # @test_logger
    @Decos.catch_exceptions
    @Decos.escape_sqlite_expression
    @conn_retryer_factory()
    async def query_modify(self, expression, values=None, fetchall=False) -> int:
        """Execute INSERT/UPDATE/DELETE query on SQLite database."""
        if self.ro:
            raise MaicaDbError(f'DB marked as ro, no modification permitted', '511', 'sqlite_modification_denied')
        lrid = None

        await self.keep_alive()
        if not values:
            cursor = await self.pool.execute(expression)
        else:
            cursor = await self.pool.execute(expression, values)
        await self.pool.commit()
        lrid = cursor.lastrowid
        await cursor.close()

        return lrid

    async def close(self):
        """Close SQLite connection."""
        if self.pool:
            await self.pool.close()

    def summon_sub(self, rsc: Optional[RealtimeSocketsContainer]=None):
        """Summons a per-user instance."""
        return SubSqliteDbPoolCoroutine(self, rsc)

class SubSqliteDbPoolCoroutine(SqliteDbPoolCoroutine):
    """Per-user SqliteDbPoolCoroutine."""
    def __init__(self, parent: SqliteDbPoolCoroutine, rsc: Optional[RealtimeSocketsContainer]=None):
        """Must summon from a parent object."""
        for k, v in vars(parent).items():
            setattr(self, k, v)

        self.parent = parent; self.rsc = rsc

    async def _ainit(self):
        """Do not use async_create."""
        raise NotImplementedError
    
    async def keep_alive(self):
        await self.parent.keep_alive()

    async def close(self):...

class AiConnCoroutine(AsyncCreator):
    """Maintain an AI connection so you don't have to."""
    def __init__(self, api_key, base_url, name='ai_conn', model: Union[int, str]=0):
        self.test = False
        self.api_key, self.base_url, self.name, self.model = api_key, base_url, name, model
        self.gen_kwargs = {}

    @Decos.catch_exceptions
    async def _ainit(self):
        if not self.base_url:
            self.test = True
            return
        else:
            self._open_socket()
            await self._select_model()

    def _open_socket(self):
        self.socket = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def _select_model(self):
        model_list = await self.socket.models.list()
        models = model_list.data
        if isinstance(self.model, int):
            self.model_actual = models[0].id
        else:
            self.model_actual = self.model

    def default_params(self, **kwargs):
        """These params will always be applied to generations. Overwritten."""
        self.gen_kwargs = kwargs

    @Decos.catch_exceptions
    async def keep_alive(self):
        if self.socket.is_closed():
            self._open_socket()
            await self._select_model()
            
    @Decos.catch_exceptions
    @conn_retryer_factory()
    async def make_completion(self, **kwargs) -> ChatCompletion:
        kwargs.update(
            {
                "model": self.model_actual
            }
        )

        await self.keep_alive()
        task_stream_resp = asyncio.create_task(self.socket.chat.completions.create(**self.gen_kwargs, **kwargs))
        await task_stream_resp
        return task_stream_resp.result()
    
    async def close(self):
        if self.socket:
            await self.socket.close()

    def summon_sub(self, rsc: Optional[RealtimeSocketsContainer]=None):
        """Summons a per-user instance."""
        return SubAiConnCoroutine(self, rsc)
    
class SubAiConnCoroutine(AiConnCoroutine):
    """Per-user AiConnCoroutine."""
    def __init__(self, parent: AiConnCoroutine, rsc: Optional[RealtimeSocketsContainer]=None):
        """Must summon from a parent object."""
        for k, v in vars(parent).items():
            setattr(self, k, v)

        self.parent = parent; self.rsc = rsc

    async def _ainit(self):
        """Do not use async_create."""
        raise NotImplementedError
    
    def _open_socket(self):
        self.parent._open_socket()

    async def close(self):...

class ConnUtils():
    """Just a wrapping for functions."""
    async def auth_pool(ro=True) -> DbPoolCoroutine:
        """Dummy."""
    async def maica_pool(ro=False) -> DbPoolCoroutine:
        """Dummy."""
    async def basic_pool(ro=False) -> DbPoolCoroutine:
        """Dummy."""

    async def mcore_conn():
        conn = await AiConnCoroutine.async_create(
            api_key=MCORE_KEY,
            base_url=MCORE_ADDR,
            name='mcore_conn',
            model=MCORE_CHOICE if MCORE_CHOICE else 0,
        )
        conn.default_params(**json.loads(load_env('MAICA_MCORE_EXTRA')))
        return conn

    async def mfocus_conn():
        conn = await AiConnCoroutine.async_create(
            api_key=MFOCUS_KEY,
            base_url=MFOCUS_ADDR,
            name='mfocus_conn',
            model=MFOCUS_CHOICE if MFOCUS_CHOICE else 0,
        )
        conn.default_params(**json.loads(load_env('MAICA_MFOCUS_EXTRA')))
        return conn
    
    async def mvista_conn():
        """Disable if no addr provided."""
        if MVISTA_ADDR:
            conn = await AiConnCoroutine.async_create(
                api_key=MVISTA_KEY,
                base_url=MVISTA_ADDR,
                name='mvista_conn',
                model=MVISTA_CHOICE if MVISTA_CHOICE else 0,
            )
            conn.default_params(**json.loads(load_env('MAICA_MVISTA_EXTRA')))
            return conn
        else:
            return None

    async def mnerve_conn():
        """Disable if no addr provided."""
        if MNERVE_ADDR:
            conn = await AiConnCoroutine.async_create(
                api_key=MNERVE_KEY,
                base_url=MNERVE_ADDR,
                name='mnerve_conn',
                model=MNERVE_CHOICE if MNERVE_CHOICE else 0,
            )
            conn.default_params(**json.loads(load_env('MAICA_MNERVE_EXTRA')))
            return conn
        else:
            return None

async def validate_input(input: Union[str, dict, list], limit: int=4096, rsc: Optional[RealtimeSocketsContainer]=None, must: Optional[list]=None, warn: Optional[list]=None) -> Union[dict, list]:
    """
    Mostly for ws.
    """
    must = must if must else []
    warn = warn if warn else []
    if not input:
        raise MaicaInputWarning('Input is empty', '410', 'maica_input_empty')
    
    if isinstance(input, str):
        if len(input) > limit:
            raise MaicaInputWarning('Input length exceeded', '413', 'maica_input_length_exceeded')
        try:
            input_json = json.loads(input)
        except Exception as e:
            raise MaicaInputWarning('Request body not JSON', '400', 'maica_input_not_json') from e
    elif isinstance(input, dict | list):
        if len(str(input)) > limit:
            raise MaicaInputWarning('Input length exceeded', '413', 'maica_input_length_exceeded')
        input_json = input
    else:
        raise MaicaInputError('Input must be string or JSON-like', '400', 'maica_input_validation_denied')

    if must:
        for mustkey in must:
            if input_json.get(mustkey) is None:
                raise MaicaInputWarning(f'Request contains no necessary {mustkey}', '405', 'maica_input_necessity_missing')
    if warn:
        for warnkey in warn:
            if input_json.get(warnkey) is None:
                if rsc:
                    await messenger(rsc.websocket, 'maica_future_warning', f'Requests containing no {warnkey} will likely be deprecated in the future', '302', type=MsgType.WARN)
    
    return input_json
