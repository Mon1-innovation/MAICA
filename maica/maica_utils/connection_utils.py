"""Import layer 3"""
import aiomysql
import aiosqlite
import pymilvus
import asyncio
import traceback
import json

from typing import *
from typing_extensions import deprecated
from openai import AsyncOpenAI, AsyncStream
from openai.types.responses import Response, ResponseStreamEvent
from openai.types.create_embedding_response import CreateEmbeddingResponse
from .gvars import *
from .maica_utils import *
from .setting_utils import *
from .fsc_early import *
from .locater import *

def pkg_init_connection_utils():
    global ConnUtils

    if G.A.DB_ADDR != "sqlite":
        """We suppose we're using MySQL."""
        async def auth_pool(ro=True):
            return await DbPoolManager.async_create(
                host=G.A.DB_ADDR,
                db=G.A.AUTH_DB,
                user=G.A.DB_USER,
                password=G.A.DB_PASSWORD,
                ro=ro,
            )

        async def maica_pool(ro=False):
            return await DbPoolManager.async_create(
                host=G.A.DB_ADDR,
                db=G.A.DATA_DB,
                user=G.A.DB_USER,
                password=G.A.DB_PASSWORD,
                ro=ro,
            )
        
        async def basic_pool(ro=False):
            return await DbPoolManager.async_create(
                host=G.A.DB_ADDR,
                db=None,
                user=G.A.DB_USER,
                password=G.A.DB_PASSWORD,
                ro=ro,
            )
    else:
        """We suppose we're using SQLite."""
        async def auth_pool(ro=True):
            return await SqliteDbPoolManager.async_create(
                db=get_inner_path(G.A.AUTH_DB)
            )
        
        async def maica_pool(ro=False):
            return await SqliteDbPoolManager.async_create(
                db=get_inner_path(G.A.DATA_DB)
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

@deprecated("Use extra_body in env instead")
def apply_postfix(messages, thinking: Literal[True, False, None]=None):
    last_msg: dict = messages[-1]
    if last_msg.get('role') == 'user':
        if isinstance(last_msg.get('content'), str):
            match thinking:
                case True:
                    last_msg['content'] += G.A.MFOCUS_THINK
                case False:
                    last_msg['content'] += G.A.MFOCUS_NOTHINK
        elif isinstance(last_msg.get('content'), list):
            d: dict
            for d in last_msg['content']:
                if d.get('type') == 'text' and isinstance(d.get('text'), str):
                    match thinking:
                        case True:
                            d['text'] += G.A.MFOCUS_THINK
                        case False:
                            d['text'] += G.A.MFOCUS_NOTHINK
                    break
        else:
            raise MaicaInputError('Context schedule not recognizable')
    return messages

class DbPoolManager(AsyncCreator):
    """Maintain a database connection pool so you don't have to."""

    db_type: Literal['mysql', 'sqlite'] = 'mysql'

    def __init__(self, db, host, user, password, ro=False):
        self.db, self.host, self.user, self.password, self.ro = db, host, user, password, ro
        self.name = self.db
        self.pool: aiomysql.Pool = None
        self.pool_container: list[aiomysql.Pool] = []
        """We use this thing to sync sub-instances' pools with mother instance."""
        self.lock = asyncio.Lock()
        """Pool affecting actions are performed with lock acquired."""

    @Decos.catch_exceptions
    async def _ainit(self):
        """Initialize MySQL connection pool."""
        if not self.lock.locked():
            async with self.lock:
                await self.close()
                self.pool = await aiomysql.create_pool(host=self.host, user=self.user, password=self.password, db=self.db)
                self.pool_container.append(self.pool)
        else:
            async with self.lock:
                return

    @Decos.catch_exceptions
    async def keep_alive(self):
        """Check and maintain MySQL connection."""
        try:
            async with self.pool.acquire():
                pass
            return
        except Exception as e:
            sync_messenger(info=f"Recreating {self.name} pool since cannot acquire", type=MsgType.WARN)
            await self._ainit()

    @overload
    async def query_get(self, expression: str, values: Optional[tuple]=None, fetchall: bool=False, inherit_conn: Optional[aiomysql.Connection]=None) -> tuple:
        """Execute SELECT query on MySQL database."""

    # @test_logger
    @Decos.catch_exceptions
    @Decos.ro_expression
    @Decos.conn_retryer_factory()
    async def query_get(self, expression, values=None, fetchall=False, inherit_conn: Optional[aiomysql.Connection]=None) -> tuple:
        async def _query_get(cur, expression, values, fetchall) -> tuple:
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
    @Decos.wo_expression
    @Decos.conn_retryer_factory()
    async def query_modify(self, expression: str, values: Optional[tuple]=None, fetchall=False, inherit_conn: Optional[aiomysql.Connection]=None) -> tuple[Annotated[int, Desc('rows')], Annotated[int, Desc('lrid')]]:
        """Execute INSERT/UPDATE/DELETE query on MySQL database."""
        if self.ro:
            raise MaicaDbError(f'DB marked as ro, no modification permitted', '511', 'db_modification_denied')
        
        async def _query_modify(cur, expression, values, fetchall) -> tuple[int, int]:
            if not values:
                rows = await cur.execute(expression)
            else:
                rows = await cur.execute(expression, values)
            lrid = cur.lastrowid
            return rows, lrid

        await self.keep_alive()

        if not inherit_conn:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    res = await _query_modify(cur, expression, values, fetchall)
                    await conn.commit()
        else:
            async with inherit_conn.cursor() as cur:
                res = await _query_modify(cur, expression, values, fetchall)
                # We leave the transactional manager handling commitments

        return res
    
    async def close(self):
        """Close before closing coroutine to avoid errors."""
        try:
            self.pool.close()
            await self.pool.wait_closed()
        except Exception:...
        finally:
            self.pool_container.clear()

    def summon_sub(self, rsc: Optional[RealtimeSocketsContainer]=None):
        """Summons a per-user instance."""
        return SubDbPoolManager(self, rsc)

class SubDbPoolManager(DbPoolManager):
    """Per-user DbPoolManager."""
    def __init__(self, parent: DbPoolManager, rsc: Optional[RealtimeSocketsContainer]=None):
        """Must summon from a parent object."""
        for k, v in vars(parent).items():
            setattr(self, k, v)

        self.parent = parent; self.rsc = rsc

    async def _ainit(self):
        """Do not use async_create."""
        raise NotImplementedError
    
    async def keep_alive(self):
        await self.parent.keep_alive()
        self.pool = self.pool_container[0]

    async def close(self):...

class SqliteDbPoolManager(DbPoolManager):
    """
    SQLite-specific database pool coroutine.
    Notice: since SQLite only allow rollback for TRANSACTION which differs
    from MySQL, we're not implementing transaction management for SQLite for
    now. 
    """

    db_type: Literal['mysql', 'sqlite'] = 'sqlite'

    def __init__(self, db, host=None, user=None, password=None, ro=False):
        self.db_path = db
        self.name = self.db_path
        self.ro = ro
        self.pool: aiosqlite.Connection = None
        """It ain't pool, we just calling it one."""
        self.pool_container: list[aiosqlite.Connection] = []
        self.lock = asyncio.Lock()

    @Decos.catch_exceptions
    async def _ainit(self):
        """
        Initialize SQLite connection pool.
        Notice: there is actually no 'pool' concept in SQLite, but
        we're considering connections as pools to keep symmetry with
        the corresponding MySQL functions.
        """
        if not self.lock.locked():
            async with self.lock:
                await self.close()
                self.pool = aiosqlite.connect(self.db_path)
                await self.pool.__aenter__()
                if self.ro:
                    await self.pool.execute("PRAGMA query_only = ON")
                self.pool_container.append(self.pool)
        else:
            async with self.lock:
                return

    @Decos.catch_exceptions
    async def keep_alive(self):
        """Check and maintain SQLite connection."""
        try:
            # You won't lose connection with a local db file, would you?

            # await self.pool.execute("SELECT 1")
            pass
        except Exception as e:
            sync_messenger(info=f"Recreating {self.db} pool since cannot acquire", type=MsgType.WARN)
            await self._ainit()

    @overload
    async def query_get(self, expression: str, values: Optional[tuple]=None, fetchall: bool=False) -> tuple:
        """Execute SELECT query on SQLite database."""

    # @test_logger
    @Decos.catch_exceptions
    @Decos.ro_expression
    @Decos.escape_sqlite_expression
    @Decos.conn_retryer_factory()
    async def query_get(self, expression, values=None, fetchall=False) -> tuple:
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
    @Decos.wo_expression
    @Decos.escape_sqlite_expression
    @Decos.conn_retryer_factory()
    async def query_modify(self, expression: str, values: Optional[tuple]=None, fetchall=False) -> tuple[int, int]:
        """Execute INSERT/UPDATE/DELETE query on SQLite database."""
        if self.ro:
            raise MaicaDbError(f'DB marked as ro, no modification permitted', '511', 'sqlite_modification_denied')

        await self.keep_alive()
        if not values:
            cursor = await self.pool.execute(expression)
        else:
            cursor = await self.pool.execute(expression, values)
        await self.pool.commit()
        rows = cursor.rowcount
        lrid = cursor.lastrowid
        await cursor.close()

        return rows, lrid

    async def close(self):
        """Close SQLite connection."""
        try:
            await self.pool.close()
        except Exception:...
        finally:
            self.pool_container.clear()

    def summon_sub(self, rsc: Optional[RealtimeSocketsContainer]=None):
        """Summons a per-user instance."""
        return SubSqliteDbPoolManager(self, rsc)

class SubSqliteDbPoolManager(SqliteDbPoolManager):
    """Per-user SqliteDbPoolManager."""
    def __init__(self, parent: SqliteDbPoolManager, rsc: Optional[RealtimeSocketsContainer]=None):
        """Must summon from a parent object."""
        for k, v in vars(parent).items():
            setattr(self, k, v)

        self.parent = parent; self.rsc = rsc

    async def _ainit(self):
        """Do not use async_create."""
        raise NotImplementedError
    
    async def keep_alive(self):
        await self.parent.keep_alive()
        self.pool = self.pool_container[0]

    async def close(self):...

class MilvusDbConnectionManager(AsyncCreator):
    """The vector db. We write it here since it's still db."""

    db_type = 'milvus'

    def __init__(self, db, host, user, password, ro=False):
        self.db = db
        """Or shall we call it collection"""
        self.host = host
        """File or url"""
        self.user, self.password = user, password
        """Won't be used if Milvus lite"""
        self.ro = ro
        self.name = self.db
        self.pool: pymilvus.AsyncMilvusClient = None
        """It ain't pool, we just calling it one."""
        self.pool_container: list[aiomysql.Pool] = []
        self.lock = asyncio.Lock()

    @Decos.catch_exceptions
    async def _ainit(self):
        """Initialize Milvus connection."""
        if not self.lock.locked():
            async with self.lock:
                await self.close()
                self.pool = pymilvus.AsyncMilvusClient(
                    uri=self.host,
                    user=self.user,
                    password=self.password,
                )
                try:
                    await self.pool.load_collection(collection_name=self.db)
                except Exception as e:
                    sync_messenger(info=f"{self.db} collection cannot be loaded: {str(e)}. Rerun _ainit afterwards", type=MsgType.WARN)
                self.pool_container.append(self.pool)
        else:
            async with self.lock:
                return

    @Decos.catch_exceptions
    async def keep_alive(self):
        """Check and maintain Milvus connection."""
        try:
            state = await self.pool.get_load_state(collection_name=self.db)
            assert str(state.get("state")) == "Loaded", "Collection not loaded"

        except Exception as e:
            sync_messenger(info=f"Recreating {self.db} pool since cannot acquire", type=MsgType.WARN)
            await self._ainit()

    def __getattr__(self, k):
        @Decos.catch_exceptions
        @Decos.conn_retryer_factory()
        async def _seq_exc(self, k, *args, **kwargs):
            await self.keep_alive()

            f = getattr(self.pool, k)
            next_coro = f(*args, **kwargs)

            if isinstance(next_coro, Awaitable):
                next_coro = await next_coro
            else:
                sync_messenger(info=f"Wrapping sync Milvus function {k} async...", type=MsgType.WARN)
                pass
            return next_coro
        
        f2 = functools.partial(_seq_exc, self, k)
        return f2
            
    async def close(self):
        """Close Milvus connection."""
        try:
            await self.pool.close()
        except Exception:...
        finally:
            self.pool_container.clear()

    def summon_sub(self, rsc: Optional[RealtimeSocketsContainer]=None):
        """Summons a per-user instance."""
        return SubMilvusDbConnectionManager(self, rsc)

class SubMilvusDbConnectionManager(MilvusDbConnectionManager):
    """Per-user MilvusDbConnectionManager."""
    def __init__(self, parent: MilvusDbConnectionManager, rsc: Optional[RealtimeSocketsContainer]=None):
        """Must summon from a parent object."""
        for k, v in vars(parent).items():
            setattr(self, k, v)

        self.parent = parent; self.rsc = rsc

    async def _ainit(self):
        """Do not use async_create."""
        raise NotImplementedError
    
    async def keep_alive(self):
        await self.parent.keep_alive()
        self.pool = self.pool_container[0]

    async def close(self):...

class AiConnectionManager(AsyncCreator):
    """Maintain an AI connection so you don't have to."""
    def __init__(self, api_key, base_url, name='ai_conn', model: Union[int, str]=0, caps: Optional[List[Literal["completion", "embedding"]]]=None):
        self.test = False
        self.api_key, self.base_url, self.name, self.model = api_key, base_url, name, model
        self.gen_kwargs = {}
        self.caps = caps or ["completion"]
        """Capabilities. I don't know if there're models can both generate and embed but to be safe."""
        self.sock_container: dict[str, Union[AsyncOpenAI, str, None]] = {
            "client": None,
            "choice": None
        }
        """We use this thing to sync sub-instances' socks with mother instance."""
        self.lock = asyncio.Lock()
        """Client affecting actions are performed with lock acquired."""

    @Decos.catch_exceptions
    async def _ainit(self):
        if not self.base_url:
            self.test = True
            return
        else:
            if not self.lock.locked():
                async with self.lock:
                    await self.close()
                    await self._connect()
            else:
                async with self.lock:
                    return

    async def _connect(self):
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.sock_container["client"] = self.client

        model_list = await self.client.models.list()
        models = model_list.data

        if isinstance(self.model, int):
            self.model_actual = models[0].id
        else:
            self.model_actual = self.model

        self.sock_container["choice"] = self.model_actual

    def default_params(self, **kwargs):
        """These params will always be applied to generations. Overwritten."""
        self.gen_kwargs = kwargs

    @Decos.catch_exceptions
    async def keep_alive(self):
        """Check and maintain OpenAI connection."""
        if self.client.is_closed():
            sync_messenger(info=f"Recreating {self.name} sock since is closed", type=MsgType.WARN)
            await self._ainit()

    @Decos.catch_exceptions
    @Decos.conn_retryer_factory()
    async def make_completion(self, swallow: Union[bool, str]=False, **kwargs) -> Response | AsyncStream[ResponseStreamEvent]:
        """
        Makes completion with arguments.
        Be cautious that this method is implemented by responses.create instead of completion.create since v1.3.
        swallow: In case some cheap providers are unstable. str as default response.
        """
        assert "completion" in self.caps, "Connected model is not capable of completion"

        kwargs.update(
            {
                "model": self.model_actual
            }
        )
        mixed_exbody = self.gen_kwargs.get('extra_body', {}) | kwargs.get('extra_body', {})
        mixed_kwargs = self.gen_kwargs | kwargs
        mixed_kwargs['extra_body'] = mixed_exbody

        await self.keep_alive()

        try:
            task_stream_resp = asyncio.create_task(self.client.responses.create(**mixed_kwargs))
            await asyncio.wait_for(task_stream_resp, timeout=int(G.A.OPENAI_TIMEOUT) if G.A.OPENAI_TIMEOUT != '0' else None)
            res = task_stream_resp.result()

        except openai.InternalServerError as oe:
            if not swallow:
                raise oe
            else:
                # Create a fake response
                fake_text = swallow if isinstance(swallow, str) else 'null'
                res = FakeChatCompletion(fake_text)
                sync_messenger(info=f"Swallowed OpenAI api exception: {str(oe)}, returning default: {fake_text}")

        return res
    
    @Decos.catch_exceptions
    @Decos.conn_retryer_factory()
    async def make_embedding(self, **kwargs) -> CreateEmbeddingResponse:
        """As above, just the embedding version."""
        assert "embedding" in self.caps, "Connected model is not capable of completion"

        kwargs.update(
            {
                "model": self.model_actual
            }
        )
        mixed_exbody = {**self.gen_kwargs.get('extra_body', {}), **kwargs.get('extra_body', {})}
        mixed_kwargs = {**self.gen_kwargs, **kwargs}
        mixed_kwargs['extra_body'] = mixed_exbody

        await self.keep_alive()

        task_resp = asyncio.create_task(self.client.embeddings.create(**mixed_kwargs))
        await asyncio.wait_for(task_resp, timeout=int(G.A.OPENAI_TIMEOUT) if G.A.OPENAI_TIMEOUT != '0' else None)
        res = task_resp.result()

        return res

    async def close(self):
        try:
            await self.client.close()
        except Exception:...
        finally:
            self.sock_container.clear()

    def summon_sub(self, rsc: Optional[RealtimeSocketsContainer]=None):
        """Summons a per-user instance."""
        return SubAiConnectionManager(self, rsc)
    
class SubAiConnectionManager(AiConnectionManager):
    """Per-user AiConnectionManager."""
    def __init__(self, parent: AiConnectionManager, rsc: Optional[RealtimeSocketsContainer]=None):
        """Must summon from a parent object."""
        for k, v in vars(parent).items():
            setattr(self, k, v)

        self.parent = parent; self.rsc = rsc

    async def _ainit(self):
        """Do not use async_create."""
        raise NotImplementedError
    
    async def keep_alive(self):
        await self.parent.keep_alive()
        self.client = self.parent.sock_container.get("client")
        self.model_actual = self.parent.sock_container.get("choice")

    async def close(self):...

class ConnUtils():
    """Just a wrapping for functions."""
    async def auth_pool(ro=True) -> DbPoolManager:
        """Dummy."""
    async def maica_pool(ro=False) -> DbPoolManager:
        """Dummy."""
    async def basic_pool(ro=False) -> DbPoolManager:
        """Dummy."""

    @staticmethod
    async def vector_pool() -> MilvusDbConnectionManager | pymilvus.AsyncMilvusClient:
        host = get_inner_path(G.A.MILVUS_ADDR) if ExplainUrl(G.A.MILVUS_ADDR).is_local else G.A.MILVUS_ADDR
        conn = await MilvusDbConnectionManager.async_create(
            db=G.A.MILVUS_COLL,
            host=host,
            user=G.A.MILVUS_USER,
            password=G.A.MILVUS_PASSWORD,
            ro=False
        )
        return conn

    @staticmethod
    async def mcore_conn():
        conn = await AiConnectionManager.async_create(
            api_key=G.A.MCORE_KEY,
            base_url=G.A.MCORE_ADDR,
            name='mcore_conn',
            model=G.A.MCORE_CHOICE or 0,
        )
        conn.default_params(**json.loads(G.A.MCORE_EXTRA))
        return conn

    @staticmethod
    async def mfocus_conn():
        conn = await AiConnectionManager.async_create(
            api_key=G.A.MFOCUS_KEY,
            base_url=G.A.MFOCUS_ADDR,
            name='mfocus_conn',
            model=G.A.MFOCUS_CHOICE or 0,
        )
        conn.default_params(**json.loads(G.A.MFOCUS_EXTRA))
        return conn

    @staticmethod
    async def mvista_conn():
        """Disable if no addr provided."""
        if G.A.MVISTA_ADDR:
            conn = await AiConnectionManager.async_create(
                api_key=G.A.MVISTA_KEY,
                base_url=G.A.MVISTA_ADDR,
                name='mvista_conn',
                model=G.A.MVISTA_CHOICE or 0,
            )
            conn.default_params(**json.loads(G.A.MVISTA_EXTRA))
            return conn
        else:
            return None

    @staticmethod
    async def mnerve_conn():
        """Disable if no addr provided."""
        if G.A.MNERVE_ADDR:
            conn = await AiConnectionManager.async_create(
                api_key=G.A.MNERVE_KEY,
                base_url=G.A.MNERVE_ADDR,
                name='mnerve_conn',
                model=G.A.MNERVE_CHOICE or 0,
            )
            conn.default_params(**json.loads(G.A.MNERVE_EXTRA))
            return conn
        else:
            return None

    @staticmethod
    async def embedding_conn():
        """Disable if no addr provided."""
        if G.A.EMBEDDING_ADDR:
            conn = await AiConnectionManager.async_create(
                api_key=G.A.EMBEDDING_KEY,
                base_url=G.A.EMBEDDING_ADDR,
                name='embedding_conn',
                model=G.A.EMBEDDING_CHOICE or 0,
                caps=["embedding"],
            )
            conn.default_params(**json.loads(G.A.EMBEDDING_EXTRA))
            return conn
        else:
            return None

async def validate_input(input: Union[str, dict, list], limit: int=0, rsc: Optional[RealtimeSocketsContainer]=None, must: Optional[list]=None, warn: Optional[list]=None) -> Union[dict, list]:
    """
    Mostly for ws.
    """
    must = must or []
    warn = warn or []
    if not input:
        raise MaicaInputWarning('Input is empty', '410', 'maica_input_empty')
    
    if isinstance(input, str):
        if limit and len(input) > limit:
            raise MaicaInputWarning('Input length exceeded', '413', 'maica_input_length_exceeded')
        try:
            input_json = json.loads(input)
        except Exception as e:
            raise MaicaInputWarning('Request body not JSON', '400', 'maica_input_not_json') from e
    elif isinstance(input, dict | list):
        if limit and len(str(input)) > limit:
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
