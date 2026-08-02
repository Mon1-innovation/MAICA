"""Import layer 2.9"""
from __future__ import annotations

import orjson
import asyncio
import hashlib
import sqlalchemy

from math import ceil
from typing import *

from .gvars import *
from .maica_utils import *
from .setting_utils import *
from .fsc_early import *
from .locater import *
from .database_utils import DatabaseUtils
from .database_models import SqlVectorReference

if TYPE_CHECKING:
    from .connection_utils import AiConnectionManager


def _content_hash_filter(content_hashes: Iterable[str]) -> str:
    return f"content_hash in {orjson.dumps(list(content_hashes)).decode()}"


class MilvusSearchMixin():
    _write_lock: asyncio.Lock


    @staticmethod
    def _content_hash(raw_text: str) -> str:
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    async def _embed(self, embedding_conn: AiConnectionManager, data: Iterable[str]) -> List[Tuple[str, list]]:
        """We write the embed method here, since it's strongly bound to milvus."""
        data = list(data)
        resp = await embedding_conn.make_embedding(input=data)

        embed_res = [i.embedding for i in resp.data]
        return list(zip(data, embed_res))


    async def _reference_hashes(self, user_id: int, chat_session_num: int) -> set[str]:
        async with DatabaseUtils.SessionData() as dbs:
            stmt = sqlalchemy.select(SqlVectorReference.content_hash).where(
                SqlVectorReference.user_id == user_id,
                SqlVectorReference.chat_session_num == chat_session_num,
            )
            return set((await dbs.scalars(stmt)).all())


    async def _query_vectors(self, content_hashes: set[str]) -> dict[str, str]:
        if not content_hashes:
            return {}
        rows = await self.query(
            collection_name=self.db,
            filter=_content_hash_filter(content_hashes),
            output_fields=["content_hash", "raw_text"],
            consistency_level="Strong",
        )
        return {row["content_hash"]: row["raw_text"] for row in rows}


    async def _ensure_vectors(
        self,
        embedding_conn: AiConnectionManager,
        texts_by_hash: dict[str, str],
    ) -> set[str]:
        existing = await self._query_vectors(set(texts_by_hash))
        for content_hash, raw_text in existing.items():
            if raw_text != texts_by_hash[content_hash]:
                raise MaicaDbError(f"SHA-256 collision detected for vector {content_hash}")

        missing_hashes = set(texts_by_hash) - set(existing)
        if not missing_hashes:
            return set()

        missing_texts = [texts_by_hash[content_hash] for content_hash in missing_hashes]
        embedded = await self._embed(embedding_conn=embedding_conn, data=missing_texts)
        await self.pool.insert(
            collection_name=self.db,
            data=[
                {
                    "content_hash": self._content_hash(raw_text),
                    "raw_text": raw_text,
                    "vector": vector,
                }
                for raw_text, vector in embedded
            ],
            consistency_level="Strong",
        )
        return missing_hashes


    async def _delete_unreferenced(self, candidates: set[str]):
        if not candidates:
            return
        async with DatabaseUtils.SessionData() as dbs:
            stmt = sqlalchemy.select(SqlVectorReference.content_hash).where(
                SqlVectorReference.content_hash.in_(candidates)
            ).distinct()
            referenced = set((await dbs.scalars(stmt)).all())

        orphaned = candidates - referenced
        if orphaned:
            await self.pool.delete(
                collection_name=self.db,
                ids=list(orphaned),
                consistency_level="Strong",
            )


    async def _sync_references(
        self,
        user_id: int,
        chat_session_num: int,
        desired_hashes: set[str],
    ) -> tuple[int, int]:
        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():
                stmt = sqlalchemy.select(SqlVectorReference.content_hash).where(
                    SqlVectorReference.user_id == user_id,
                    SqlVectorReference.chat_session_num == chat_session_num,
                )
                old_hashes = set((await dbs.scalars(stmt)).all())
                to_add = desired_hashes - old_hashes
                to_remove = old_hashes - desired_hashes

                if to_remove:
                    await dbs.execute(
                        sqlalchemy.delete(SqlVectorReference).where(
                            SqlVectorReference.user_id == user_id,
                            SqlVectorReference.chat_session_num == chat_session_num,
                            SqlVectorReference.content_hash.in_(to_remove),
                        )
                    )
                dbs.add_all([
                    SqlVectorReference(
                        user_id=user_id,
                        chat_session_num=chat_session_num,
                        content_hash=content_hash,
                    )
                    for content_hash in to_add
                ])
                await dbs.flush()

                if to_remove:
                    still_referenced_stmt = sqlalchemy.select(SqlVectorReference.content_hash).where(
                        SqlVectorReference.content_hash.in_(to_remove)
                    ).distinct()
                    still_referenced = set((await dbs.scalars(still_referenced_stmt)).all())
                    orphaned = to_remove - still_referenced
                    if orphaned:
                        await self.pool.delete(
                            collection_name=self.db,
                            ids=list(orphaned),
                            consistency_level="Strong",
                        )

        return len(to_add), len(to_remove)


    async def cross_insert(
        self,
        embedding_conn: AiConnectionManager,
        data: Iterable[str],
        user_id: int,
        chat_session_num: int,
    ):
        """Synchronize one reference scope against globally deduplicated vectors."""
        data = list(data)
        if any(not isinstance(item, str) for item in data):
            raise TypeError("Milvus raw_text values must be strings")
        new_texts = set(data)
        texts_by_hash = {self._content_hash(raw_text): raw_text for raw_text in new_texts}

        async with self._write_lock:
            inserted_hashes = await self._ensure_vectors(embedding_conn, texts_by_hash)
            try:
                added, removed = await self._sync_references(
                    user_id,
                    chat_session_num,
                    set(texts_by_hash),
                )
            except Exception:
                try:
                    await self._delete_unreferenced(inserted_hashes)
                except Exception as cleanup_error:
                    sync_messenger(
                        info=f"Failed to clean up newly inserted Milvus vectors after SQL rollback: {cleanup_error}",
                        type=MsgType.WARN,
                    )
                raise

        sync_messenger(
            info=f"Stashed to milvus successfully: {len(new_texts)} incoming, {len(inserted_hashes)} embedded; {added} added, {removed} removed",
            type=MsgType.DEBUG,
        )


    async def embed_search(
        self,
        embedding_conn: AiConnectionManager,
        data: Iterable[str],
        user_id: int,
        chat_session_num: int,
        topk: int = 5,
        cfd_min: float = 0.5,
    ):
        """Embed and search."""

        reference_hashes = await self._reference_hashes(user_id, chat_session_num)
        if not reference_hashes:
            return set()

        embed_res = await self._embed(embedding_conn, data)
        embedded_query = [i[1] for i in embed_res]

        filter_sentence = _content_hash_filter(reference_hashes)

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
                _distances.append(d["distance"])
                if d["distance"] >= cfd_min:
                    res_set.add(d["entity"]["raw_text"])

        sync_messenger(info=f"Vector searching found {len(_distances)} results" + (f", distance range {min(_distances)}~{max(_distances)}" if _distances else ""), type=MsgType.DEBUG)
        sync_messenger(info=f"{len(res_set)} results adopted", type=MsgType.DEBUG)

        return res_set
