
import asyncio
import datetime

from typing import *


from sqlalchemy import (
    UniqueConstraint,
    JSON,
    Boolean,
    DateTime,
    String,
    Text,
    inspect,
)
from sqlalchemy.sql import (
    func,
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

class OrmToDictMixin():
    def model_to_dict(self):
        return {
            c.key: getattr(self, c.key)
            for c in inspect(self).mapper.column_attrs
        }

class SqlBaseAuth(DeclarativeBase, OrmToDictMixin):
    pass

class SqlBaseData(DeclarativeBase, OrmToDictMixin):
    pass

class SqlUser(SqlBaseAuth):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    is_email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    password: Mapped[str] = mapped_column(String(100))
    suspended_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

class SqlAccountStatus(SqlBaseData):
    __tablename__ = "account_status"

    id: Mapped[int] = mapped_column("user_id", primary_key=True, autoincrement=False)
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
        UniqueConstraint("user_id", "chat_session_num", name="uq_chat_session_user_session"),
    )

    id: Mapped[int] = mapped_column("chat_session_id", primary_key=True)
    user_id: Mapped[int]
    chat_session_num: Mapped[int]
    content: Mapped[Optional[str]] = mapped_column(Text)

class SqlCropArchived(SqlBaseData):
    __tablename__ = "crop_archived"

    id: Mapped[int] = mapped_column("archive_id", primary_key=True)
    chat_session_id: Mapped[int]
    content: Mapped[Optional[str]] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

class SqlCsessionArchived(SqlBaseData):
    __tablename__ = "csession_archived"

    id: Mapped[int] = mapped_column("archive_id", primary_key=True)
    chat_session_id: Mapped[int]
    content: Mapped[Optional[str]] = mapped_column(Text)

class SqlMsCache(SqlBaseData):
    __tablename__ = "ms_cache"
    __table_args__ = (
        UniqueConstraint("hash", name="uq_hash"),
    )

    id: Mapped[int] = mapped_column("spire_id", primary_key=True)
    hash: Mapped[str] = mapped_column(String(255))
    content: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

class SqlMvMeta(SqlBaseData):
    __tablename__ = "mv_meta"

    id: Mapped[int] = mapped_column("vista_id", primary_key=True)
    user_id: Mapped[int]
    uuid: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

class SqlPersistent(SqlBaseData):
    __tablename__ = "persistents"
    __table_args__ = (
        UniqueConstraint("user_id", "chat_session_num", name="uq_persistents_user_session"),
    )

    id: Mapped[int] = mapped_column("persistent_id", primary_key=True)
    user_id: Mapped[int]
    chat_session_num: Mapped[int]
    content: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

class SqlTrigger(SqlBaseData):
    __tablename__ = "triggers"
    __table_args__ = (
        UniqueConstraint("user_id", "chat_session_num", name="uq_triggers_user_session"),
    )

    id: Mapped[int] = mapped_column("trigger_id", primary_key=True)
    user_id: Mapped[int]
    chat_session_num: Mapped[int]
    content: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

