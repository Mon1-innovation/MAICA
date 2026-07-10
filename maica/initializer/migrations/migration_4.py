import asyncio
import os
from typing import *
from pymilvus import DataType, CollectionSchema
from maica.maica_utils import *
from .base import register_migration

upper_version = "1.3.000.rc1"

async def migrate():
    if G.A.MILVUS_ADDR:
        sync_messenger(info="[maica-db] Adding collection to Milvus...", type=MsgType.DEBUG)
    
        vector_pool = await ConnUtils.vector_pool()

        # Uncomment this to recreate coll
        # await vector_pool.drop_collection(collection_name=vector_pool.db)

        if await vector_pool.has_collection(collection_name=vector_pool.db):
            sync_messenger(info="[maica-db] Milvus collection already exists, skipping...", type=MsgType.DEBUG)
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

        sync_messenger(info="[maica-db] Milvus databse initialization finished", type=MsgType.LOG)

    else:
        sync_messenger(info="[maica-db] Milvus databse is not enabled, skipping...", type=MsgType.WARN)

    maica_pool = await ConnUtils.maica_pool()
    try:
        if maica_pool.db_type == 'mysql':
            await maica_pool.query_modify("ALTER TABLE `account_status` CHANGE `status` `status` JSON NULL DEFAULT NULL; ")
            await maica_pool.query_modify("ALTER TABLE `account_status` CHANGE `preferences` `preferences` JSON NULL DEFAULT NULL; ")
            await maica_pool.query_modify("ALTER TABLE `crop_archived` CHANGE `archived` `archived` BOOLEAN NOT NULL DEFAULT '0'; ")

            await maica_pool.query_modify("ALTER TABLE ms_cache ADD UNIQUE INDEX uq_hash (hash(64));")
            await maica_pool.query_modify("ALTER TABLE chat_session ADD UNIQUE INDEX uq_id_session (user_id, chat_session_num);")
            await maica_pool.query_modify("ALTER TABLE persistents ADD UNIQUE INDEX uq_id_session (user_id, chat_session_num);")
            await maica_pool.query_modify("ALTER TABLE triggers ADD UNIQUE INDEX uq_id_session (user_id, chat_session_num);")
            
        else:
            # There's no actual json at all in sqlite
            # Nor tinyint

            await maica_pool.query_modify("ALTER TABLE ms_cache CREATE UNIQUE INDEX uq_hash ON ms_cache(hash);")
            await maica_pool.query_modify("ALTER TABLE chat_session CREATE UNIQUE INDEX uq_id_session ON chat_session(user_id, chat_session_num);")
            await maica_pool.query_modify("ALTER TABLE persistents CREATE UNIQUE INDEX uq_id_session ON persistents(user_id, chat_session_num);")
            await maica_pool.query_modify("ALTER TABLE triggers CREATE UNIQUE INDEX uq_id_session ON triggers(user_id, chat_session_num);")

    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t alter table: {str(e)}, maybe manually done already?') from e
    finally:
        await maica_pool.close()

register_migration(upper_version, migrate)

if __name__ == "__main__":
    from maica import init
    init()
    asyncio.run(migrate())