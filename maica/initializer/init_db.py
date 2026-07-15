"""
Do not add future inits here, since it's actually migration_0. Make new migs instead.
"""

import os
import urllib.parse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from maica.maica_utils import *


async def _database_exists(engine, database_name: str) -> bool:
    result = await engine.execute(text("SHOW DATABASES LIKE :database_name"), {"database_name": database_name})
    return result.first() is not None


async def _create_mysql_database(engine, database_name: str):
    # Database names come from application settings; quote backticks defensively for MySQL identifiers.
    quoted_name = database_name.replace("`", "``")
    await engine.execute(text(f"CREATE DATABASE IF NOT EXISTS `{quoted_name}`"))


async def create_tables():

    AUTH_DB = G.A.AUTH_DB
    MAICA_DB = G.A.DATA_DB

    auth_created = False

    if not is_auth_sqlite() or not is_data_sqlite():
        usr = urllib.parse.quote_plus(G.A.DB_USER)
        pwd = urllib.parse.quote_plus(G.A.DB_PASSWORD)
        addr = G.A.DB_ADDR
        server_url = f"mysql+aiomysql://{usr}:{pwd}@{addr}"
        server_engine = create_async_engine(server_url, pool_pre_ping=True, pool_recycle=3600)
        try:
            async with server_engine.begin() as conn:
                if not is_auth_sqlite():
                    if not await _database_exists(conn, AUTH_DB):
                        sync_messenger(info=f"[maica-db] AUTH_DB {AUTH_DB} does not exist, creating...", type=MsgType.DEBUG)
                        await _create_mysql_database(conn, AUTH_DB)
                        auth_created = True
                    else:
                        sync_messenger(info=f"[maica-db] AUTH_DB {AUTH_DB} exists, skipping...", type=MsgType.WARN)

                if not is_data_sqlite():
                    if not await _database_exists(conn, MAICA_DB):
                        sync_messenger(info=f"[maica-db] DATA_DB {MAICA_DB} does not exist, creating...", type=MsgType.DEBUG)
                        await _create_mysql_database(conn, MAICA_DB)
                    else:
                        sync_messenger(info=f"[maica-db] DATA_DB {MAICA_DB} exists, skipping...", type=MsgType.WARN)
        finally:
            await server_engine.dispose()

    if is_auth_sqlite() and not os.path.exists(get_inner_path(AUTH_DB)):
        auth_created = True

    if auth_created:
        sync_messenger(info="[maica-db] Adding table to AUTH_DB...", type=MsgType.DEBUG)
        async with DatabaseUtils.engine_auth.begin() as conn:
            await conn.run_sync(SqlBaseAuth.metadata.create_all)
    else:
        sync_messenger(info="\n[maica-db] Warning: AUTH_DB was not created by MAICA, so we're not writing anything for security reason.\nPlease manually make sure AUTH_DB is already ready for authentication, or delete at your own risk.", type=MsgType.WARN)

    sync_messenger(info="[maica-db] Adding table to DATA_DB...", type=MsgType.DEBUG)
    async with DatabaseUtils.engine_data.begin() as conn:
        await conn.run_sync(SqlBaseData.metadata.create_all)

    sync_messenger(info="[maica-db] MAICA databse initialization finished", type=MsgType.LOG)
