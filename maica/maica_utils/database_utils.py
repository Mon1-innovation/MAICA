"""
This is the in-progress new database module, based on SQLAlchemy.
"""
import asyncio

import urllib.parse

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)

from .database_models import *

from .maica_utils import *

class DatabaseUtils():
    engine_auth: AsyncEngine = None
    engine_data: AsyncEngine = None
    SessionAuth: async_sessionmaker[AsyncSession] = None
    SessionData: async_sessionmaker[AsyncSession] = None

def pkg_init_database_utils():

    usr = G.A.DB_USER
    pwd = urllib.parse.quote_plus(G.A.DB_PASSWORD)
    addr = G.A.DB_ADDR

    if not is_auth_sqlite():
        AUTH_DB_URL = (
            "mysql+aiomysql://"
            f"{usr}:{pwd}"
            f"@{addr}"
            f"/{G.A.AUTH_DB}"
        )
        ae_params = {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }
    else:
        AUTH_DB_URL = (
            "sqlite+aiosqlite:///"
            f"{get_inner_path(G.A.AUTH_DB)}"
        )
        ae_params = {
            "connect_args": {"timeout": 30}
        }

    if not is_data_sqlite():
        DATA_DB_URL = (
            "mysql+aiomysql://"
            f"{usr}:{pwd}"
            f"@{addr}"
            f"/{G.A.DATA_DB}"
        )
        de_params = {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }
    else:
        DATA_DB_URL = (
            "sqlite+aiosqlite:///"
            f"{get_inner_path(G.A.DATA_DB)}"
        )
        de_params = {
            "connect_args": {"timeout": 30}
        }

    DatabaseUtils.engine_auth = create_async_engine(
        AUTH_DB_URL,
        **ae_params,
    )
    DatabaseUtils.engine_data = create_async_engine(
        DATA_DB_URL,
        **de_params,
    )

    DatabaseUtils.SessionAuth = async_sessionmaker(
        bind=DatabaseUtils.engine_auth,
        class_=ReadOnlySession,
        expire_on_commit=False,
    )
    DatabaseUtils.SessionData = async_sessionmaker(
        bind=DatabaseUtils.engine_data,
        class_=AsyncSession,
        expire_on_commit=False,
    )

class ReadOnlySession(AsyncSession):
    async def flush(self, *args, **kwargs):
        raise RuntimeError("Readonly session")

    async def commit(self):
        raise RuntimeError("Readonly session")

if __name__ == "__main__":

    async def main():

        from maica import init
        init(ignore_envc=True)
        pkg_init_database_utils()
        
        async with DatabaseUtils.SessionData() as session:
            test_mvmeta = SqlMvMeta(user_id = 23, uuid = "aae5d25b-1de8-4d3a-a26d-977326087c8c")

            session.add(test_mvmeta)

            await session.commit()
            await session.refresh(test_mvmeta)

            return test_mvmeta
        
    print(asyncio.run(main()))
