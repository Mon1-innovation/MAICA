import asyncio
from types import SimpleNamespace

import sqlalchemy
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from maica.maica_utils import DatabaseUtils, MaicaDbError, SqlBaseData, SqlVectorReference
from maica.maica_utils.connection_mixin import MilvusSearchMixin
from maica.initializer.migrations.migration_5 import _is_reference_collection


class FakeEmbeddingConnection:
    def __init__(self):
        self.inputs = []

    async def make_embedding(self, input):
        self.inputs.extend(input)
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(len(item))]) for item in input]
        )


class FakeVectorStore(MilvusSearchMixin):
    db = "test_vectors"

    def __init__(self):
        self.pool = self
        self.vectors = {}
        self.fail_deletes = False
        self._write_lock = asyncio.Lock()

    async def _query_vectors(self, content_hashes):
        return {
            content_hash: self.vectors[content_hash]["raw_text"]
            for content_hash in content_hashes
            if content_hash in self.vectors
        }

    async def insert(self, collection_name, data, consistency_level):
        assert collection_name == self.db
        assert consistency_level == "Strong"
        for row in data:
            self.vectors[row["content_hash"]] = row

    async def delete(self, collection_name, ids, consistency_level):
        assert collection_name == self.db
        assert consistency_level == "Strong"
        if self.fail_deletes:
            raise RuntimeError("Milvus delete failed")
        for content_hash in ids:
            self.vectors.pop(content_hash, None)

    async def search(self, collection_name, filter, data, output_fields, **kwargs):
        assert collection_name == self.db
        assert "content_hash in" in filter
        hits = [
            {"distance": 1.0, "entity": {"raw_text": row["raw_text"]}}
            for content_hash, row in self.vectors.items()
            if content_hash in filter
        ]
        return [hits]


def test_reference_collection_schema_check_includes_vector_dimensions() -> None:
    description = {
        "fields": [
            {"name": "content_hash", "is_primary": True},
            {"name": "raw_text"},
            {"name": "vector", "params": {"dim": 768}},
        ]
    }
    assert _is_reference_collection(description, 768)
    assert not _is_reference_collection(description, 1024)


def test_vectors_are_shared_and_deleted_after_the_last_reference() -> None:
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        old_factory = DatabaseUtils.SessionData
        DatabaseUtils.SessionData = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SqlBaseData.metadata.create_all)

            store = FakeVectorStore()
            embedding = FakeEmbeddingConnection()
            first_scope = {"user_id": 1, "chat_session_num": 1}
            second_scope = {"user_id": 1, "chat_session_num": 2}

            await store.cross_insert(embedding, ["shared", "first only"], **first_scope)
            await store.cross_insert(embedding, ["shared"], **second_scope)

            assert sorted(embedding.inputs) == ["first only", "shared"]
            assert len(store.vectors) == 2
            assert await store.audit_reference_consistency() == set()

            missing_hash = store._content_hash("shared")
            missing_vector = store.vectors.pop(missing_hash)
            assert await store.audit_reference_consistency() == {missing_hash}
            store.vectors[missing_hash] = missing_vector
            async with DatabaseUtils.SessionData() as dbs:
                refs = (await dbs.scalars(sqlalchemy.select(SqlVectorReference))).all()
                assert len(refs) == 3

            results = await store.embed_search(embedding, ["query"], **second_scope)
            assert results == {"shared"}

            store.fail_deletes = True
            await store.cross_insert(embedding, [], **first_scope)
            async with DatabaseUtils.SessionData() as dbs:
                refs = (await dbs.scalars(sqlalchemy.select(SqlVectorReference))).all()
                assert len(refs) == 1
            assert len(store.vectors) == 2

            store.fail_deletes = False
            await store.cross_insert(embedding, [], **first_scope)
            assert {row["raw_text"] for row in store.vectors.values()} == {"shared", "first only"}

            await store.cross_insert(embedding, [], **second_scope)
            assert {row["raw_text"] for row in store.vectors.values()} == {"first only"}

            await store.cross_insert(
                embedding,
                ["backend data"],
                user_id=-1,
                chat_session_num=0,
            )
            results = await store.embed_search(
                embedding,
                ["query"],
                user_id=-1,
                chat_session_num=0,
            )
            assert results == {"backend data"}

            collision_hash = store._content_hash("collision input")
            store.vectors[collision_hash] = {"raw_text": "different text", "vector": [1.0]}
            with pytest.raises(MaicaDbError, match="SHA-256 collision"):
                await store.cross_insert(
                    embedding,
                    ["collision input"],
                    user_id=1,
                    chat_session_num=1,
                )
        finally:
            DatabaseUtils.SessionData = old_factory
            await engine.dispose()

    asyncio.run(scenario())
