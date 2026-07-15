import asyncio
import os
from typing import *
from pymilvus import DataType, CollectionSchema
from sqlalchemy import inspect, text
from maica.maica_utils import *
from .base import register_migration

upper_version = "1.2.006.rc6"

async def _create_index_if_missing(conn, table_name: str, index_name: str, columns: list[str], ddl: str):
    indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes(table_name))
    constraints = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_unique_constraints(table_name))
    expected_columns = set(columns)
    if any(
        item.get("name") == index_name
        or set(item.get("column_names") or []) == expected_columns
        for item in [*indexes, *constraints]
    ):
        sync_messenger(info=f"[migration-4] Index {index_name} already exists on {table_name}, skipping...", type=MsgType.DEBUG)
        return
    await conn.execute(text(ddl))

async def migrate():
    if G.A.MILVUS_ADDR:
        sync_messenger(info="[migration-4] Adding collection to Milvus...", type=MsgType.DEBUG)
    
        vector_pool = await ConnUtils.vector_pool()

        # Uncomment this to recreate coll
        # await vector_pool.drop_collection(collection_name=vector_pool.db)

        if await vector_pool.has_collection(collection_name=vector_pool.db):
            sync_messenger(info="[migration-4] Milvus collection already exists, skipping...", type=MsgType.DEBUG)
        else:

            schema: CollectionSchema = await vector_pool.create_schema(
                auto_id=True,
                enable_dynamic_field=True,
                partition_key_field="user_id",
                num_partitions=64,
            )

            schema.add_field("id", DataType.INT64, is_primary=True)

            schema.add_field("user_id", DataType.INT64, is_partition_key=True)

            schema.add_field("chat_session_num", DataType.INT64, nullable=True, default_value=0)

            schema.add_field("type", DataType.VARCHAR, max_length=32, nullable=True, default_value="persistent")

            schema.add_field("raw_text", DataType.VARCHAR, max_length=65535)

            schema.add_field("is_prod", DataType.BOOL, nullable=True, default_value=True)

            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=int(G.A.EMBEDDING_DIMS))

            await vector_pool.create_collection(
                collection_name=vector_pool.db,
                schema=schema,
            )

            index_params = await vector_pool.prepare_index_params()

            index_params.add_index(
                field_name="vector",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 16, "efConstruction": 256}
            )

            await vector_pool.create_index(
                collection_name=vector_pool.db,
                index_params=index_params,
            )

        sync_messenger(info="[migration-4] Milvus databse initialization finished", type=MsgType.LOG)

    else:
        sync_messenger(info="[migration-4] Milvus databse is not enabled, skipping...", type=MsgType.WARN)

    try:
        async with DatabaseUtils.engine_data.begin() as conn:
            if conn.dialect.name == 'mysql':
                await conn.execute(text("ALTER TABLE `account_status` CHANGE `status` `status` JSON NULL DEFAULT NULL"))
                await conn.execute(text("ALTER TABLE `account_status` CHANGE `preferences` `preferences` JSON NULL DEFAULT NULL"))
                await conn.execute(text("ALTER TABLE `crop_archived` CHANGE `archived` `archived` BOOLEAN NOT NULL DEFAULT '0'"))

                await _create_index_if_missing(conn, "ms_cache", "uq_hash", ["hash"], "CREATE UNIQUE INDEX uq_hash ON ms_cache (hash(64))")
            else:
                # There's no actual json at all in sqlite, nor tinyint.
                await _create_index_if_missing(conn, "ms_cache", "uq_hash", ["hash"], "CREATE UNIQUE INDEX uq_hash ON ms_cache (hash)")

            await _create_index_if_missing(conn, "chat_session", "uq_chat_session_user_session", ["user_id", "chat_session_num"], "CREATE UNIQUE INDEX uq_chat_session_user_session ON chat_session (user_id, chat_session_num)")
            await _create_index_if_missing(conn, "persistents", "uq_persistents_user_session", ["user_id", "chat_session_num"], "CREATE UNIQUE INDEX uq_persistents_user_session ON persistents (user_id, chat_session_num)")
            await _create_index_if_missing(conn, "triggers", "uq_triggers_user_session", ["user_id", "chat_session_num"], "CREATE UNIQUE INDEX uq_triggers_user_session ON triggers (user_id, chat_session_num)")

    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t alter table: {str(e)}, maybe manually done already?') from e

register_migration(upper_version, migrate)

if __name__ == "__main__":
    from maica import init
    init()
    asyncio.run(migrate())
