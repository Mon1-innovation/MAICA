"""
This is the in-progress new database module, based on SQLAlchemy.
"""
import asyncio

import urllib.parse

import sqlalchemy
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import load_only

from .database_models import *

from .maica_utils import *

class DatabaseUtils():
    engine_auth: AsyncEngine = None
    engine_data: AsyncEngine = None
    SessionAuth: async_sessionmaker[AsyncSession] = None
    SessionData: async_sessionmaker[AsyncSession] = None


async def dispose_database_engines():
    """Dispose global database pools before their event loop is closed."""
    engines = (DatabaseUtils.engine_auth, DatabaseUtils.engine_data)
    disposed = set()
    for engine in engines:
        if engine is not None and id(engine) not in disposed:
            await engine.dispose()
            disposed.add(id(engine))

def pkg_init_database_utils():

    usr = urllib.parse.quote_plus(G.A.DB_USER)
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

# We can add some convenient utils
async def sqla_get_or_create[T: SqlBaseData](dbs, model: Type[T], params: dict, requires: Optional[Iterable] = None):

    _select_params = [
        getattr(model, k) == v
        for k, v in params.items()
    ]

    async def _select():
        stmt = sqlalchemy.select(model).where(
            *_select_params
        ).with_for_update()

        if requires:
            stmt = stmt.options(
                load_only(
                    *[getattr(model, i) for i in requires]
                )
            )

        return await dbs.scalar(stmt)

    obj = await _select()

    if not obj:
        try:
            async with dbs.begin_nested():

                obj = model(
                    **params
                )
                dbs.add(obj)

                await dbs.flush()

        except IntegrityError:
            obj = await _select()
            if not obj:
                raise

    return obj

async def sqla_create_or_update[T: SqlBaseData](dbs, model: Type[T], unique: dict, carriage: Optional[dict] = None):

    _select_params = [
        getattr(model, k) == v
        for k, v in unique.items()
    ]
    _carriage = carriage or {}

    try:
        async with dbs.begin_nested():

            obj = model(
                **unique,
                **_carriage,
            )
            dbs.add(obj)

            await dbs.flush()

    except IntegrityError as integrity_error:
        if carriage:
            stmt = sqlalchemy.update(model).where(
                *_select_params,
            ).values(
                **_carriage
            )

            await dbs.execute(stmt)

        existing = await dbs.scalar(
            sqlalchemy.select(model).where(*_select_params)
        )
        if existing is None:
            raise integrity_error

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
