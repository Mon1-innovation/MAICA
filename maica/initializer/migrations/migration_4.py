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

register_migration(upper_version, migrate)