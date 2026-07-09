
import asyncio
import datetime

from typing import *


from sqlalchemy import (
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)
from sqlalchemy.ext.mutable import (
    MutableDict,
    MutableList,
)

class SqlBaseAuth(DeclarativeBase):
    pass

class SqlBaseData(DeclarativeBase):
    pass

class SqlUser(SqlBaseAuth):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    nickname: Mapped[Optional[str]]
    email: Mapped[str] = mapped_column(unique=True)
    is_email_confirmed: Mapped[bool] = mapped_column(default=False)
    password: Mapped[str]
    suspended_until: Mapped[Optional[datetime.datetime]]

class SqlAccountStatus(SqlBaseData):
    __tablename__ = "account_status"

    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    status: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        default=dict,
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        default=dict,
    )

class SqlChatSession(SqlBaseData):
    __tablename__ = "chat_session"
    __table_args__ = (
        UniqueConstraint("user_id", "chat_session_num", name="uq_id_session")
    )

    chat_session_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(unique=True)
    chat_session_num: Mapped[int]
    content: Mapped[str]

class SqlCropArchived(SqlBaseData):
    __tablename__ = "crop_archived"

    archive_id: Mapped[int] = mapped_column(primary_key=True)
    chat_session_id: Mapped[int]
    content: Mapped[str]
    archived: Mapped[bool] = mapped_column(default=False)

class SqlCsessionArchived(SqlBaseData):
    __tablename__ = "csession_archived"

    archive_id: Mapped[int] = mapped_column(primary_key=True)
    chat_session_id: Mapped[int]
    content: Mapped[str]

class SqlMsCache(SqlBaseData):
    __tablename__ = "ms_cache"

    spire_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    hash: Mapped[str]
    content: Mapped[str]
    timestamp: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime)

class SqlMvMeta(SqlBaseData):
    __tablename__ = "mv_meta"

    vista_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    uuid: Mapped[str]
    timestamp: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime)

class SqlPersistent(SqlBaseData):
    __tablename__ = "persistents"
    __table_args__ = (
        UniqueConstraint("user_id", "chat_session_num", name="uq_id_session")
    )

    persistent_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    chat_session_num: Mapped[int]
    content: Mapped[Optional[str]]
    timestamp: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime)

class SqlTrigger(SqlBaseData):
    __tablename__ = "triggers"
    __table_args__ = (
        UniqueConstraint("user_id", "chat_session_num", name="uq_id_session")
    )

    trigger_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    chat_session_num: Mapped[int]
    content: Mapped[Optional[str]]
    timestamp: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime)





