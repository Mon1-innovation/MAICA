"""Import layer 3"""
import aiomysql
import aiosqlite
import pymilvus
import asyncio
import functools
import openai
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
    pass

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
        self.pool_container: list[pymilvus.AsyncMilvusClient] = []
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
                    sync_messenger(info=f"{self.db} collection cannot be loaded: {str(e)}, could be in create stage", type=MsgType.WARN)

                self.pool_container.append(self.pool)
        else:
            async with self.lock:
                return

    @Decos.catch_exceptions
    async def keep_alive(self):
        """Check and maintain Milvus connection."""
        try:
            state = await self.pool.get_load_state(collection_name=self.db)
            if str(state.get("state")) != "Loaded":
                raise RuntimeError("Collection not loaded")

        except Exception:
            sync_messenger(info=f"Recreating {self.db} pool since cannot acquire", type=MsgType.WARN)
            await self._ainit()

    def __getattr__(self, k):
        @Decos.catch_exceptions
        @Decos.conn_retryer_factory()
        async def seq_exc(self, k, *args, **kwargs):
            await self.keep_alive()

            f = getattr(self.pool, k)
            next_coro = f(*args, **kwargs)

            if isinstance(next_coro, Awaitable):
                next_coro = await next_coro
            else:
                sync_messenger(info=f"Wrapping sync Milvus function {k} async...", type=MsgType.WARN)
                pass
            return next_coro
        
        f2 = functools.partial(seq_exc, self, k)
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

        self.parent = parent
        self.rsc = rsc

    async def _ainit(self):
        """Do not use async_create."""
        raise NotImplementedError
    
    async def keep_alive(self):
        await self.parent.keep_alive()
        self.pool = self.pool_container[0]

    async def close(self):...

class AiConnectionManager(AsyncCreator):
    """Maintain an AI connection so you don't have to."""
    def __init__(self, api_key, base_url, name='ai_conn', model: Union[int, str]=0, caps: Optional[List[Literal["completion", "embedding", "reranking"]]]=None):
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
            self.client = None
            self.model_actual = "DISABLED"
            self.sock_container["choice"] = self.model_actual
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
            if not models:
                raise MaicaResponseError(f"{self.name} returned an empty model list")
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
        if self.test or self.client is None:
            raise MaicaResponseError(f"{self.name} is not configured")
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
        if "completion" not in self.caps:
            raise MaicaResponseError("Connected model is not capable of completion")

        kwargs.update(
            {
                "model": self.model_actual
            }
        )
        mixed_exbody = self.gen_kwargs.get('extra_body', {}) | kwargs.get('extra_body', {})
        mixed_kwargs = self.gen_kwargs | kwargs
        mixed_kwargs['extra_body'] = mixed_exbody

        # The response patch
        # Idiot openai
        for lower_sampling_param in (
            "seed",
            "frequency_penalty",
            "presence_penalty",
        ):
            if lower_sampling_param in mixed_kwargs:
                mixed_kwargs['extra_body'][lower_sampling_param] = mixed_kwargs.pop(lower_sampling_param)
            
        # Alter names
        if "max_tokens" in mixed_kwargs:
            mixed_kwargs["max_output_tokens"] = mixed_kwargs.pop("max_tokens")

        await self.keep_alive()

        try:
            task_stream_resp = asyncio.create_task(self.client.responses.create(**mixed_kwargs))
            await asyncio.wait_for(task_stream_resp, timeout=int(G.A.OPENAI_TIMEOUT) if G.A.OPENAI_TIMEOUT != '0' else None)
            resp = task_stream_resp.result()

        except openai.InternalServerError as oe:
            if not swallow:
                raise
            else:
                # Create a fake response
                fake_text = swallow if isinstance(swallow, str) else 'null'
                resp = FakeChatCompletion(fake_text)
                sync_messenger(info=f"Swallowed OpenAI api exception: {str(oe)}, returning default: {fake_text}")

        return resp
    
    @Decos.catch_exceptions
    @Decos.conn_retryer_factory()
    async def make_embedding(self, **kwargs) -> CreateEmbeddingResponse:
        """As above, just the embedding version."""
        if "embedding" not in self.caps:
            raise MaicaResponseError("Connected model is not capable of embedding")

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
        resp = task_resp.result()

        return resp
    
    @Decos.catch_exceptions
    @Decos.conn_retryer_factory()
    async def make_reranking(self, **kwargs) -> dict:
        """Generate reranking. This is acutally not OpenAI but VLLM standard."""
        if "reranking" not in self.caps:
            raise MaicaResponseError("Connected model is not capable of reranking")

        kwargs.update(
            {
                "model": self.model_actual
            }
        )
        mixed_exbody = {**self.gen_kwargs.get('extra_body', {}), **kwargs.get('extra_body', {})}
        mixed_kwargs = {**self.gen_kwargs, **kwargs}
        mixed_kwargs['extra_body'] = mixed_exbody

        await self.keep_alive()

        task_resp = asyncio.create_task(
            self.client.post(
                "rerank",
                cast_to=dict[str, Any],
                body=mixed_kwargs,
            )
        )

        await asyncio.wait_for(task_resp, timeout=int(G.A.OPENAI_TIMEOUT) if G.A.OPENAI_TIMEOUT != '0' else None)
        resp = task_resp.result()

        return resp

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

        self.parent = parent
        self.rsc = rsc

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

    @staticmethod
    async def vector_pool() -> MilvusDbConnectionManager | pymilvus.AsyncMilvusClient:
        if not G.A.MILVUS_ADDR:
            return None
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
        if not G.A.MCORE_ADDR:
            raise CriticalMaicaError("MAICA_MCORE_ADDR is required")
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
        if not G.A.MFOCUS_ADDR:
            raise CriticalMaicaError("MAICA_MFOCUS_ADDR is required")
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
        """Disable if no addr provided, or is_mcore_vl."""
        if G.A.MVISTA_ADDR and not is_mcore_vl():
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
        
    @staticmethod
    async def reranking_conn():
        """Disable if no addr provided."""
        if G.A.RERANKING_ADDR:
            conn = await AiConnectionManager.async_create(
                api_key=G.A.RERANKING_KEY,
                base_url=G.A.RERANKING_ADDR,
                name='reranking_conn',
                model=G.A.RERANKING_CHOICE or 0,
                caps=["reranking"],
            )
            conn.default_params(**json.loads(G.A.RERANKER_EXTRA))
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
                    await messenger(rsc.websocket, 'maica_future_warning', f'Requests containing no {warnkey} will likely be deprecated in the future', 302, type=MsgType.WARN)
    
    return input_json
