"""Import layer 2.9"""
from __future__ import annotations

from math import ceil
from typing import *

from .gvars import *
from .maica_utils import *
from .setting_utils import *
from .fsc_early import *
from .locater import *

if TYPE_CHECKING:
    from .connection_utils import AiConnectionManager


def _filter_to_sentence(filter: dict):
    filter_sentence = " and ".join(
        [
            f"{k} == {v}"
            for k, v in filter.items()
        ]
    ) if filter else ''
    return filter_sentence


class MilvusSearchMixin():

    async def _embed(self, embedding_conn: AiConnectionManager, data: list[str]) -> List[Tuple[str, list]]:
        """We write the embed method here, since it's strongly bound to milvus."""
        if isinstance(data, str):
            data = [data]
        else:
            data = list(data)
        resp = await embedding_conn.make_embedding(input=data)

        embedded = [i.embedding for i in resp.data]
        return list(zip(data, embedded))


    async def cross_insert(
        self,
        embedding_conn: AiConnectionManager,
        data: Iterable,
        unique: str = "raw_text",
        filter: Optional[dict] = None,
    ):
        """Diff and insert, at high efficiency."""

        filter_sentence = _filter_to_sentence(filter)

        # First query and calcs
        old = await self.query(
            collection_name=self.db,
            filter=filter_sentence,
            output_fields=["id", unique],
            consistency_level="Strong",
        )

        old_texts = {x[unique] for x in old}
        new_texts = set(data)

        to_add = new_texts - old_texts
        to_del = old_texts - new_texts

        sync_messenger(info=f"Stashing to milvus, found {len(old_texts)} old; {len(new_texts)} new; {len(to_add)} add; {len(to_del)} del", type=MsgType.DEBUG)

        # Then procedures
        if to_add:
            packed_embedded = await self._embed(embedding_conn, to_add)
        else:
            packed_embedded = []

        if to_del:
            delete_ids = [item["id"] for item in old if item["raw_text"] in to_del]
            await self.pool.delete(
                collection_name=self.db,
                ids=delete_ids,
                consistency_level="Strong",
            )

        if packed_embedded:
            await self.pool.insert(
                collection_name=self.db,
                data=[
                    {
                        unique: t[0],
                        "vector": t[1],
                    } | filter or {}
                    for t in packed_embedded
                ],
                consistency_level="Strong",
            )

        sync_messenger(info="Stashed to milvus successfully", type=MsgType.DEBUG)


    async def embed_search(
        self,
        embedding_conn: AiConnectionManager,
        data: Iterable,
        filter: Optional[dict] = None,
        topk: int = 5,
        cfd_min: float = 0.5,
    ):
        """Embed and search."""

        embed_res = await self._embed(embedding_conn, data)
        embedded_query = [i[1] for i in embed_res]

        filter_sentence = _filter_to_sentence(filter)

        search_res = await self.pool.search(
            collection_name=self.db,
            filter=filter_sentence,
            data=embedded_query,
            output_fields=["raw_text"],
            limit=topk,
            search_params={
                "params": {"ef": 64},
            },
            consistency_level="Strong",
        )
        
        prio_max = ceil(topk / len(search_res))
        res_set: Set[str] = set()

        _distances = []
        for result_group in search_res:
            for d in result_group[:prio_max]:
                if d["distance"] >= cfd_min:
                    _distances.append(d["distance"])
                    res_set.add(d["entity"]["raw_text"])
        if res_set:
            sync_messenger(info=f"Vector searching found {len(res_set)} results, distance range {min(_distances)}~{max(_distances)}", type=MsgType.DEBUG)
        else:
            sync_messenger(info="Vector searching result is empty", type=MsgType.DEBUG)

        return res_set