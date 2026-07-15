
"""
Import layer 4.3
"""
import time
import orjson
import types
import sqlalchemy
from sqlalchemy.orm import load_only

from typing import *
from pydantic import BaseModel, Field, model_validator
from pydantic.dataclasses import dataclass as pdataclass
from contextlib import asynccontextmanager
from .maica_utils import *
from .fsc_late import *
from .db_bound_obj import DbBoundObject
from .session_early import SessionPersistentMixin, SessionTriggerMixin
from .session_late import SessionPersistentLlmMixin, SessionTriggerLlmMixin
from .database_utils import *
from .database_models import *
from .chat_session import *

_Bt = BilingualText

# These should be far more simple
class SessionPersistent(DbBoundObject, SessionPersistentMixin, SessionPersistentLlmMixin):
    
    _model = SqlPersistent
    _empty = dict

    def clear(self):
        self.clear_temp()
        return super().clear()
    
    def clear_temp(self):
        self.content_temp = {}

    def on_acquire(self):
        self.clear_temp()

    def _post_upload(self, *args, **kwargs):
        self._chk_len(self._conclude_extra_sf())
        return super()._post_upload(*args, **kwargs)

class SessionTrigger(DbBoundObject, SessionTriggerMixin, SessionTriggerLlmMixin):

    _model = SqlTrigger

    def clear(self):
        self.clear_temp()
        return super().clear()
    
    def clear_temp(self):
        self.content_temp = []

    def on_acquire(self):
        self.clear_temp()
    
# That float is last acquired timestamp
_sessions_index: Dict[
    str,
    Dict[
        Tuple[int, int],
        List[DbBoundObject | float]
    ]
] = {
    "maica_sessions": {},
    "session_persistents": {},
    "session_triggers": {},
}

async def _get_real_session_num(dbo: DbBoundObject, fsc: FullSocketsContainer) -> int:
    """Some dbos use session 0 if determined not exist. Input DBO cls here just for convenience."""
    user_id = fsc.maica_settings.verification.user_id
    session_num = fsc.maica_settings.temp.chat_session

    async with DatabaseUtils.SessionData() as dbs:
        model = dbo._model

        stmt = sqlalchemy.select(model).where(
            model.user_id == user_id,
            model.chat_session_num == session_num,
        ).options(
            load_only(model.id)
        )
        obj = await dbs.scalar(stmt)

        if obj:
            return session_num
        else:
            return 0

def _id_acquire_dbo[T: DbBoundObject](cls: Type[T], sub_dict_k: str, user_id: int, session_num: int) -> T:
    global _sessions_index
    if user_id <= 0:
        raise MaicaInputError("Sessions are designed to be user-bound, not system-wide")
        
    sub_dict = _sessions_index[sub_dict_k]

    # Ensure it exists in index
    mapping = (user_id, session_num)
    if mapping not in sub_dict.keys():
        sub_dict[mapping] = [cls(session_num), time.time()]
    # This shouldn't happen theoretically, but we cover it anyway
    elif sub_dict[mapping][0].is_destroyed:
        sub_dict[mapping] = [cls(session_num), time.time()]
    else:
        sub_dict[mapping][1] = time.time()

    session = sub_dict[mapping][0]

    return session
        
async def _fsc_acquire_dbo(type: Literal["session", "persistent", "trigger"], fsc: FullSocketsContainer):
    user_id = fsc.maica_settings.verification.user_id
    session_num = fsc.maica_settings.temp.chat_session

    match type:
        case "session":
            sub_dict_k = "maica_sessions"
            cls = MaicaSession
        case "persistent":
            sub_dict_k = "session_persistents"
            cls = SessionPersistent
            session_num = await _get_real_session_num(cls, fsc)
        case "trigger":
            sub_dict_k = "session_triggers"
            cls = SessionTrigger
            session_num = await _get_real_session_num(cls, fsc)
        case _:
            raise MaicaInputError("Type cannot be recognized")

    session = _id_acquire_dbo(cls, sub_dict_k, user_id, session_num)
    # If former fsc is already destroyed
    session.fsc = fsc

    # Trigger on_acquire action
    session.on_acquire()

    return session

@asynccontextmanager
async def acquire_dbo(type: Literal["session", "persistent", "trigger"], fsc: FullSocketsContainer):
    """This should be used as context manager!"""
    session: MaicaSession | SessionPersistent | SessionTrigger = await _fsc_acquire_dbo(type, fsc)
    try:
        async with session.lock:
            yield session
    finally:
        session.fsc = None

def acquire_session(fsc):
    """Just an alias now."""
    return acquire_dbo("session", fsc)

# To release some memory
def dbos_gc(timestamp):
    gced: List[Tuple] = []
    for name, sessions in _sessions_index.items():
        stale_keys = []
        for key, value in sessions.items():
            if value[1] < timestamp and not value[0].lock.locked():
                value[0].destroy()
                stale_keys.append(key)
        for key in stale_keys:
            sessions.pop(key, None)
            gced.append((name, key))
    return gced
