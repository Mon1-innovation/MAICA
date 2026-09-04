"""
Import layer 4.2
"""
from __future__ import annotations

import asyncio
import orjson
import datetime

from typing import *
from enum import StrEnum
from math import ceil
from pydantic import BaseModel, Field, TypeAdapter, create_model
from random import sample
from dateutil.relativedelta import relativedelta
from .maica_utils import *
from .chat_session import *

if TYPE_CHECKING:
    from maica.maica_utils import FullSocketsContainer

_Bt = BilingualText

class SessionPersistentLlmMixin():

    session_num: int
    fsc: FullSocketsContainer
    content: dict
    content_temp: dict


    async def to_vector(
        self,
        _data: Optional[list] = None,
        target_lang: Optional[TargetLangType] = None,
    ):
        """As said, to milvus. Milvus is not considered persistent storage so only write."""
        vector_pool = self.fsc.vector_pool
        if not self.fsc.is_vector_ready:
            return
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num

        await vector_pool.cross_insert(
            embedding_conn=self.fsc.embedding_conn,
            data = _data if _data is not None else self.form_info(target_lang=target_lang),
            user_id=user_id,
            chat_session_num=session_num,
        )


    async def _sync_vectors_from_db(self):
        """Rebuild this scope's vector references from the persisted archive."""
        await self.from_db()

        target_lang = self.read_key("target_lang", where="pers") or self.fsc.maica_settings.basic.target_lang
        data = self.form_info(
            where="pers",
            target_lang=target_lang,
        ) if self.content else []
        await self.to_vector(_data=data, target_lang=target_lang)


    async def filter_vector(self, query: str, topk: int = 5) -> Set:
        """Embed and search query from milvus."""
        vector_pool = self.fsc.vector_pool
        if not self.fsc.is_vector_ready:
            return []

        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num

        await self._sync_vectors_from_db()

        res_set = await vector_pool.embed_search(
            embedding_conn=self.fsc.embedding_conn,
            data=[query],
            user_id=user_id,
            chat_session_num=session_num,
            topk=topk,
        )

        return res_set


    async def filter_reranker(self, query: str, documents: Optional[set] = None, topk: int = 2) -> list:
        """More precisely filter results, suggest using filter_vector first."""
        reranking_conn = self.fsc.reranking_conn
        if not self.fsc.is_reranking_ready:
            return []

        if (
            documents is None
            and self.fsc.is_vector_ready
        ):
            documents = await self.filter_vector(query, 10)
            # We include full extras since there's no other way
            documents |= self.form_info(where='temp')

        elif documents is None:
            documents = self.form_info()

        documents = list(documents)

        if not documents:
            return []

        reranking_params = {
            "query": query,
            "documents": documents,
            "top_n": topk,
        }

        resp = await reranking_conn.make_reranking(**reranking_params)

        cfd_min = 0.5
        res_list = []

        _relevances = []
        for i in resp["results"]:
            _relevances.append(i["relevance_score"])
            if i["relevance_score"] >= cfd_min:
                res_list.append(i["document"]["text"])

        sync_messenger(info=f"Reranking found {len(_relevances)} results" + (f", distance range {min(_relevances)}~{max(_relevances)}" if _relevances else ""), type=MsgType.DEBUG)
        sync_messenger(info=f"{len(res_list)} results adopted", type=MsgType.DEBUG)

        return res_list


    async def filter_llm(self, query: str, documents: Optional[set] = None, topk: int = 3) -> list:
        """Traditional MFocus sfe implementation."""
        session = MaicaSession()
        target_lang = self.fsc.maica_settings.basic.target_lang
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.fsc.maica_settings.temp.chat_session
        conn = self.fsc.mnerve_conn or self.fsc.mfocus_conn

        if (
            documents is None
            and self.fsc.is_vector_ready
        ):
            documents = await self.filter_vector(query, 10)
            documents |= self.form_info(where='temp')

        elif documents is None:
            documents = self.form_info()

        documents = list(documents)

        if not documents:
            return []

        if TYPE_CHECKING:
            type DocEnum = str
        else:
            DocEnum = StrEnum(
                f"DocEnum_{user_id}_{session_num}",
                {
                    k: k for k
                    in documents
                }
            )

        class PersSelectionResults(GenCorrectionModel):
            items: list[DocEnum] = Field(
                min_length=0,
                max_length=topk,
                description=f"0到{topk}个最相关的条目, 原样输出." if target_lang == 'zh' else f"0 ~ {topk} most relevant items, output as-is."
            )

        system = MaicaSessionItem(
            "system",
            _Bt(
f"""\
你是一个人工智能助手, 你的任务是从信息中查找与问题最相关的条目.
你是角色"莫妮卡". 你应选择0到{topk}条互不重复的条目, 并原样输出.
如果没有任何条目与问题相关, 你可以输出空值.\
""",
f"""\
You are a helpful assistant, your task is finding most relevant items with the query from provided information.
Your character is called "Monika". You should choose 0 ~ {topk} unique items and output them as-is.
If none of the information is relevant with query, you can output empty.\
"""
            ),
        )
        session.append(system)

        user_query = MaicaSessionItem(
            "user",
            query,
            target_lang=target_lang,
        )
        session.append(user_query)

        completion_args = {
            "input": session.utilize(
                manual_prompt=True,
                ignore_additions=True,
            ),
            "text": pyd_to_openai(PersSelectionResults)
        }

        resp = await conn.make_completion(**completion_args)
        selection_result = PersSelectionResults.model_validate_json(resp.output_text)

        return selection_result.items
    

class SessionTriggerLlmMixin():

    session_num: int
    fsc: FullSocketsContainer
    content: list
    content_temp: list


    async def predict_trigger(self, query: str):
        """We make st do this itself, since we used llm in sp already."""
        session = MaicaSession()
        target_lang = self.fsc.maica_settings.basic.target_lang
        conn = self.fsc.mnerve_conn or self.fsc.mfocus_conn

        text_l = []
        for tr in self._get_triggers():
            t, _ = tr.to_descr()
            if t:
                text_l.append(t)

        descr_text = list_to_bullets(text_l)

        if not descr_text:
            return False, None

        # Dynamic class here, since each time the enum changes
        # We also write the alternative non-precision way
        # if True:
        #     TrigSelectionResults = create_model(
        #         "TrigSelectionResults",
        #         item=(
        #             Optional[
        #                 Literal[*choices_l]
        #             ],
        #             Field(
        #                 ...,
        #                 description="你选择的条目, 原样输出." if target_lang == 'zh' else "The item you choose, output as-is."
        #             )
        #         )
        #     )
        # else:
        #     class TrigSelectionResults(BaseModel):
        #         item: Optional[str] = Field(
        #             description="你选择的条目, 原样输出." if target_lang == 'zh' else "The item you choose, output as-is."
        #         )

        # No that's dumb and costy. We just need to verify a true-or-false, if the query can be satisfied.
        class TrigSelectionResults(GenCorrectionModel):
            requested: bool = Field(
                description="是否需要使用工具." if target_lang == 'zh' else "If any tool is required."
            )
            operation: Optional[str] = Field(
                description="你选择的工具, 原样输出." if target_lang == 'zh' else "The tool you choose, output as-is."
            )
            _default_resp = {
                "requested": False,
                "operation": None,
            }

        system = MaicaSessionItem(
            "system",
            _Bt(
"""\
你是一个人工智能助手, 你的任务是根据用户要求, 从提供的工具中作出选择.
你是角色"莫妮卡". 提供的工具均用于游戏内操作, 请严格遵循以下规则:
- 如果用户要求与除对话外的游戏操作无关, 对requested输出false.
- 如果有关, 对requested输出true.
    - 如果没有合适的工具满足要求, 或requested为false, 对operation输出null.
    - 如果有, 对operation输出对应的工具选择.
以下是工具列表:\
""",
"""\
You are a helpful assistant, your task is choosing from provided tools according to user's request.
Your character is called "Monika". Provided tools are all used for in-game actions, please precisely follow these rules:
- If user request does not involve in-game actions except chatting, output false in "requested" field.
- If it does involve, output true in "requested" field.
    - If none of provided tools could satisfy request, or "requested" field is false, output null in "operation" field.
    - If there is, output corresponding tool choice in "operaiton" field.
Here is the tools list:\
"""
            ) + descr_text,
        )
        session.append(system)

        user_query = MaicaSessionItem(
            "user",
            query,
            target_lang=target_lang,
        )
        session.append(user_query)

        completion_args = {
            "input": session.utilize(
                manual_prompt=True,
                ignore_additions=True,
            ),
            "text": pyd_to_openai(TrigSelectionResults)
        }

        resp = await conn.make_completion(**completion_args)
        selection_result = TrigSelectionResults.model_validate_json(resp.output_text)

        return selection_result.requested, selection_result.operation
