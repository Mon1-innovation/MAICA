"""Import layer 3"""
from __future__ import annotations

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
from .connection_mixin import MilvusSearchMixin

def pkg_init_connection_utils():
    pass


class MilvusDbConnectionManager(AsyncCreator, MilvusSearchMixin):
    """The vector db. We write it here since it's still db."""

    db_type = 'milvus'


    def __init__(self, db, host, user, password, ro=False):
        self.db: str = db
        """Or shall we call it collection"""
        self.host = host
        """File or url"""
        self.user, self.password = user, password
        """Won't be used if Milvus lite"""
        self.ro = ro
        self.name = self.db
        self.pool: pymilvus.AsyncMilvusClient = None
        """It ain't pool, we just calling it one."""


    async def _ainit(self):
        """Initialize Milvus connection."""

        await self.close()
        self.pool = pymilvus.AsyncMilvusClient(
            uri=self.host,
            user=self.user,
            password=self.password,
        )

        try:
            await self.pool.load_collection(collection_name=self.db)
        except Exception as e:
            sync_messenger(info=f"{self.db} collection cannot be loaded: {str(e)}, this is only normal in migrations", type=MsgType.WARN)


    def __getattr__(self, k):
        return getattr(self.pool, k)


    async def close(self):
        """Close Milvus connection."""
        try:
            await self.pool.close()
        except Exception:...


class AiConnectionManager(AsyncCreator):
    """Maintain an AI connection so you don't have to."""


    def __init__(self, api_key, base_url, name='ai_conn', model: Union[int, str]=0, caps: Optional[List[Literal["completion", "embedding", "reranking"]]]=None):
        self.test = False
        self.api_key, self.base_url, self.name, self.model = api_key, base_url, name, model
        self.gen_kwargs = {}
        self.caps = caps or ["completion"]
        """Capabilities. I don't know if there're models can both generate and embed but to be safe."""


    async def _ainit(self):
        if not self.base_url:
            self.test = True
            self.client = None
            self.model_actual = "DISABLED"
            return
        
        else:
            await self.close()
            await self._connect()


    async def _connect(self):
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

        if isinstance(self.model, int):

            model_list = await self.client.models.list()
            models = model_list.data
            
            if not models:
                raise MaicaResponseError(f"{self.name} returned an empty model list")
            self.model_actual = models[0].id

        else:
            self.model_actual = self.model


    def default_params(self, **kwargs):
        """These params will always be applied to generations. Overwritten."""
        self.gen_kwargs = kwargs


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

        # Flattern system
        messages = mixed_kwargs.get("input")
        if (
            isinstance(messages, list)
            and messages
            and messages[0]["role"] == "system"
        ):
            system = messages.pop(0)
            mixed_kwargs["instructions"] = system["content"]

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

        task_resp = asyncio.create_task(self.client.embeddings.create(**mixed_kwargs))
        await asyncio.wait_for(task_resp, timeout=int(G.A.OPENAI_TIMEOUT) if G.A.OPENAI_TIMEOUT != '0' else None)
        resp = task_resp.result()

        return resp
    

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
            conn.default_params(**json.loads(G.A.RERANKING_EXTRA))
            return conn
        else:
            return None
