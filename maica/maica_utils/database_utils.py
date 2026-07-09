"""
This is the in-progress new database module, based on SQLAlchemy.
"""
import asyncio

import urllib.parse

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from .maica_utils import *

usr = G.A.DB_USER
pwd = urllib.parse.quote_plus(G.A.DB_PASSWORD)
addr = G.A.DB_ADDR

if G.A.DB_ADDR != "sqlite":
    AUTH_DB_URL = (
        "mysql+aiomysql://"
        f"{usr}:{pwd}"
        f"@{addr}"
        f"/{G.A.AUTH_DB}"
    )
    DATA_DB_URL = (
        "mysql+aiomysql://"
        f"{usr}:{pwd}"
        f"@{addr}"
        f"/{G.A.DATA_DB}"
    )
else:
    AUTH_DB_URL = (
        "sqlite+aiosqlite:///"
        f"{get_inner_path(G.A.AUTH_DB)}"
    )
    DATA_DB_URL = (
        "sqlite+aiosqlite:///"
        f"{get_inner_path(G.A.DATA_DB)}"
    )

engine_auth = create_async_engine(
    AUTH_DB_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)
engine_data = create_async_engine(
    DATA_DB_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

class ReadOnlySession(AsyncSession):
    async def flush(self, *args, **kwargs):
        raise RuntimeError("Readonly session")

    async def commit(self):
        raise RuntimeError("Readonly session")

SessionAuth = async_sessionmaker(
    bind=engine_auth,
    class_=ReadOnlySession,
    expire_on_commit=False,
)
SessionData = async_sessionmaker(
    bind=engine_data,
    class_=AsyncSession,
    expire_on_commit=False,
)