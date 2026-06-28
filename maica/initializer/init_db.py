import asyncio
import os
from typing import *
from pymilvus import DataType, CollectionSchema
from maica.maica_utils import *

async def create_tables():

    AUTH_DB = G.A.AUTH_DB
    MAICA_DB = G.A.DATA_DB

    basic_pool = await ConnUtils.basic_pool()
    auth_created = False

    if basic_pool:
        # We have to create databases before tables
        result = await basic_pool.query_get("SHOW DATABASES", fetchall=True)
        curr_dbs = []
        for curr_db in result:
            curr_dbs.append(curr_db[0])

        if not AUTH_DB in curr_dbs:
            sync_messenger(info=f"[maica-db] AUTH_DB {AUTH_DB} does not exist, creating...", type=MsgType.DEBUG)
            await basic_pool.query_modify(f"CREATE DATABASE IF NOT EXISTS {AUTH_DB}")
            auth_created = True
        else:
            sync_messenger(info=f"[maica-db] AUTH_DB {AUTH_DB} exists, skipping...", type=MsgType.WARN)

        if not MAICA_DB in curr_dbs:
            sync_messenger(info=f"[maica-db] DATA_DB {MAICA_DB} does not exist, creating...", type=MsgType.DEBUG)
            await basic_pool.query_modify(f"CREATE DATABASE IF NOT EXISTS {MAICA_DB}")
        else:
            sync_messenger(info=f"[maica-db] DATA_DB {MAICA_DB} exists, skipping...", type=MsgType.WARN)
    elif not os.path.exists(get_inner_path(AUTH_DB)):
        auth_created = True

    auth_pool = await ConnUtils.auth_pool(ro=False)
    maica_pool = await ConnUtils.maica_pool()

    auth_tables = [
"""
CREATE TABLE IF NOT EXISTS `users` (
`id` int(10) unsigned NOT NULL AUTO_INCREMENT,
`username` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
`nickname` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
`email` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
`is_email_confirmed` tinyint(1) NOT NULL DEFAULT '0',
`password` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
`suspended_until` datetime DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""
    ] if basic_pool else [
"""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    nickname TEXT DEFAULT NULL,
    email TEXT NOT NULL,
    is_email_confirmed INTEGER NOT NULL DEFAULT 0,
    password TEXT NOT NULL,
    suspended_until DATETIME DEFAULT NULL
);
"""
    ]
    maica_tables = [
"""
CREATE TABLE IF NOT EXISTS `account_status` (
`user_id` int(11) NOT NULL,
`status` text DEFAULT NULL,
`preferences` text DEFAULT NULL,
PRIMARY KEY (`user_id`)
)
""",
"""
CREATE TABLE IF NOT EXISTS `crop_archived` (
`archive_id` int(11) NOT NULL AUTO_INCREMENT,
`chat_session_id` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
`archived` int(11) DEFAULT NULL,
PRIMARY KEY (`archive_id`)
)
""",
"""
CREATE TABLE IF NOT EXISTS `chat_session` (
`chat_session_id` int(11) NOT NULL AUTO_INCREMENT,
`user_id` int(11) NOT NULL,
`chat_session_num` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
PRIMARY KEY (`chat_session_id`)
)
""",
"""
CREATE TABLE IF NOT EXISTS `csession_archived` (
`archive_id` int(11) NOT NULL AUTO_INCREMENT,
`chat_session_id` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
PRIMARY KEY (`archive_id`)
)
""",
"""
CREATE TABLE IF NOT EXISTS `persistents` (
`persistent_id` int(11) NOT NULL AUTO_INCREMENT,
`user_id` int(11) NOT NULL,
`chat_session_num` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
`timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (`persistent_id`)
)
""",
"""
CREATE TABLE IF NOT EXISTS `triggers` (
`trigger_id` int(11) NOT NULL AUTO_INCREMENT,
`user_id` int(11) NOT NULL,
`chat_session_num` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
`timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (`trigger_id`)
)
""",
"""
CREATE TABLE IF NOT EXISTS `ms_cache` (
`spire_id` int(11) NOT NULL AUTO_INCREMENT,
`hash` text NOT NULL,
`content` text DEFAULT NULL,
`timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (`spire_id`)
)
"""
    ] if basic_pool else [
"""
CREATE TABLE IF NOT EXISTS account_status (
    user_id INTEGER PRIMARY KEY NOT NULL,
    status TEXT DEFAULT NULL,
    preferences TEXT DEFAULT NULL
)
""",
"""
CREATE TABLE IF NOT EXISTS crop_archived (
    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_session_id INTEGER NOT NULL,
    content TEXT DEFAULT NULL,
    archived INTEGER DEFAULT NULL
)
""",
"""
CREATE TABLE IF NOT EXISTS chat_session (
    chat_session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_session_num INTEGER NOT NULL,
    content TEXT DEFAULT NULL
)
""",
"""
CREATE TABLE IF NOT EXISTS csession_archived (
    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_session_id INTEGER NOT NULL,
    content TEXT DEFAULT NULL
)
""",
"""
CREATE TABLE IF NOT EXISTS persistents (
    persistent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_session_num INTEGER NOT NULL,
    content TEXT DEFAULT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""",
"""
CREATE TABLE IF NOT EXISTS triggers (
    trigger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_session_num INTEGER NOT NULL,
    content TEXT DEFAULT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""",
"""
CREATE TABLE IF NOT EXISTS ms_cache (
    spire_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT NOT NULL,
    content TEXT DEFAULT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""",
"""
CREATE TRIGGER IF NOT EXISTS update_timestamp_persistents
AFTER UPDATE ON persistents
FOR EACH ROW
BEGIN
    UPDATE persistents
    SET timestamp = CURRENT_TIMESTAMP
    WHERE persistent_id = OLD.persistent_id;
END;
""",
"""
CREATE TRIGGER IF NOT EXISTS update_timestamp_triggers
AFTER UPDATE ON triggers
FOR EACH ROW
BEGIN
    UPDATE triggers
    SET timestamp = CURRENT_TIMESTAMP
    WHERE trigger_id = OLD.trigger_id;
END;
""",
"""
CREATE TRIGGER IF NOT EXISTS update_timestamp_ms_cache
AFTER UPDATE ON ms_cache
FOR EACH ROW
BEGIN
    UPDATE ms_cache
    SET timestamp = CURRENT_TIMESTAMP
    WHERE spire_id = OLD.spire_id;
END;
""",
    ]

    # Notice: These triggers act as 'on update CURRENT_TIMESTAMP', since
    # there is no convenient way for this in SQLite.

    if basic_pool:
        for table in maica_tables:
            table += " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"

    if auth_created:
        for table in auth_tables:
            sync_messenger(info="[maica-db] Adding table to AUTH_DB...", type=MsgType.DEBUG)
            await auth_pool.query_modify(table)
    else:
        sync_messenger(info="\n[maica-db] Warning: AUTH_DB was not created by MAICA, so we're not writing anything for security reason.\nPlease manually make sure AUTH_DB is already ready for authentication, or delete at your own risk.", type=MsgType.WARN)

    for table in maica_tables:
        sync_messenger(info="[maica-db] Adding table to DATA_DB...", type=MsgType.DEBUG)
        await maica_pool.query_modify(table)

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

    sync_messenger(info="[maica-db] MAICA databse initialization finished", type=MsgType.LOG)

if __name__ == "__main__":
    from maica import init
    init()
    asyncio.run(create_tables())