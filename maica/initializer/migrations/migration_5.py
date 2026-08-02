"""Move Milvus session ownership into SQL references and deduplicate vectors."""

import asyncio

from pymilvus import CollectionSchema, DataType

from maica.maica_utils import *
from .base import register_migration

target_version = "1.3.000.rc2"


def _is_reference_collection(description: dict, expected_dims: int) -> bool:
    fields = {field["name"]: field for field in description.get("fields", [])}
    return (
        set(fields) == {"content_hash", "raw_text", "vector"}
        and fields["content_hash"].get("is_primary", False)
        and int(fields["vector"].get("params", {}).get("dim", 0)) == expected_dims
    )


async def _recreate_vector_collection():
    vector_pool = await ConnUtils.vector_pool()
    try:
        expected_dims = int(G.A.EMBEDDING_DIMS)
        schema_ready = False
        if await vector_pool.has_collection(collection_name=vector_pool.db):
            description = await vector_pool.describe_collection(collection_name=vector_pool.db)
            schema_ready = _is_reference_collection(description, expected_dims)
            if schema_ready:
                sync_messenger(info="[migration-5] Milvus collection already uses the reference schema", type=MsgType.DEBUG)
            else:
                await vector_pool.drop_collection(collection_name=vector_pool.db)

        if not schema_ready:
            schema: CollectionSchema = vector_pool.create_schema(
                auto_id=False,
                enable_dynamic_field=False,
            )
            schema.add_field("content_hash", DataType.VARCHAR, max_length=64, is_primary=True)
            schema.add_field("raw_text", DataType.VARCHAR, max_length=65535)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=expected_dims)

            await vector_pool.create_collection(collection_name=vector_pool.db, schema=schema)

        if not await vector_pool.list_indexes(collection_name=vector_pool.db, field_name="vector"):
            index_params = vector_pool.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 16, "efConstruction": 256},
            )
            await vector_pool.create_index(
                collection_name=vector_pool.db,
                index_params=index_params,
            )
    finally:
        await vector_pool.close()


async def migrate():
    try:
        async with DatabaseUtils.engine_data.begin() as conn:
            await conn.run_sync(SqlVectorReference.__table__.create, checkfirst=True)
    except Exception as exc:
        raise MaicaDbWarning(f"Couldn't create vector reference table: {exc}") from exc

    if G.A.MILVUS_ADDR:
        sync_messenger(info="[migration-5] Recreating Milvus collection for deduplicated vectors...", type=MsgType.DEBUG)
        await _recreate_vector_collection()
        sync_messenger(info="[migration-5] Milvus reference schema initialized", type=MsgType.LOG)
    else:
        sync_messenger(info="[migration-5] Milvus is not enabled, skipping collection migration...", type=MsgType.WARN)


register_migration(target_version, migrate)

if __name__ == "__main__":
    from maica import init
    init()
    asyncio.run(migrate())
