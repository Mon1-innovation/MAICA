"""
DB bound instances look alike, so what about we write all-in-one and let things inherit.
"""

import asyncio
import orjson
import functools
import types

from abc import ABC, abstractmethod
from typing import *
from pydantic import Field
from pydantic.dataclasses import dataclass as pdataclass
from maica.maica_utils import *

class CheckDestroyed():
    @staticmethod
    def _check_destroyed_before_use(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if getattr(self, "is_destroyed", False):
                raise RuntimeError(
                    f"Destroyed instance cannot call {func.__name__}"
                )
            return func(self, *args, **kwargs)
        return wrapper

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name, attr_value in cls.__dict__.items():
            if (
                isinstance(attr_value, types.FunctionType) 
                    and not attr_name.startswith("__")
                    and not attr_name == ("destroy")
            ):
                setattr(cls, attr_name, cls._check_destroyed_before_use(attr_value))

@pdataclass
class DbBoundObject(CheckDestroyed, ABC):
    """
    A basic db-bound object.
    table, prim_key_name and fsc are required to function, fill in sub objects.

    Something to notice, this is designed to be session_num bound. WILL NOT change session_num on fsc change.
    """
    session_num: int = Field(
        frozen=True,
        default=0,
    )
    """fsc chat_session is flexible, we shouldn't depend on it if we want this to be session-unique."""
    fsc: Optional[FullSocketsContainer] = None

    # Enforce implementations
    @property
    @abstractmethod
    def TABLE() -> str: ...
    @property
    @abstractmethod
    def PRIM_KEY_NAME() -> str: ...

    SESSION_DB_MIN: ClassVar[int] = 0
    SESSION_DB_BELOW: ClassVar[int] = 10

    _empty = lambda: []
    """To properly reset self. Override if necessary."""

    def clear(self):
        self.text: str = ''
        self.content: Union[dict, list] = self._empty

    def reset(self):
        """Normally just use clear."""
        self.prim_key_id: Optional[int] = None
        self.clear()

    def __post_init__(self):
        self.i_name = self.TABLE.rstrip('s')
        self.is_destroyed = False
        self.lock = asyncio.Lock()
        self.reset()

    def load(self, item: list | dict | str):
        """Load from item, like uploading or what."""
        if not isinstance(item, str):
            self.text = orjson.dumps(item).decode()
            self.content = item
        else:
            item = item.strip()
            if not item[0] in ('[', '{'):
                item = f"[{item}]"
            self.content = orjson.loads(item)
            self.text = item

    def local_sync(self, from_which: Literal["text", "content"] = "content"):
        """Sync local contents, run before to_db."""
        match from_which:
            case "text":
                self.load(self.text)
            case "content":
                self.load(self.content)

    async def init_db(self):
        # Common
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num
        maica_pool = self.fsc.maica_pool
        assert user_id and session_num and maica_pool, "DB cridentials not complete"
        maica_assert(self.SESSION_DB_MIN <= session_num < self.SESSION_DB_BELOW, full_info=f"{session_num} is not acceptable {self.i_name}")

        # First if row exists already
        sql_expression_1 = f"SELECT {self.PRIM_KEY_NAME} FROM {self.TABLE} WHERE user_id = %s AND chat_session_num = %s"
        result = await maica_pool.query_get(expression=sql_expression_1, values=(user_id, session_num))

        # Then record or new
        if result:
            prim_key_id, = result
        else:
            sql_expression_2 = f"INSERT INTO {self.TABLE} (user_id, chat_session_num, content) VALUES (%s, %s, %s)"
            result = await maica_pool.query_modify(expression=sql_expression_2, values=(user_id, session_num, "[]"))
            prim_key_id = result[1]
        
        self.prim_key_id = prim_key_id

    async def to_db(self, skip_sync = False):
        # Common
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num
        maica_pool = self.fsc.maica_pool
        assert user_id and session_num and maica_pool, "DB cridentials not complete"
        maica_assert(self.SESSION_DB_MIN <= session_num < self.SESSION_DB_BELOW, full_info=f"{session_num} is not acceptable {self.i_name}")

        # First prepare data
        # We can separate this but just in case we forget
        if not skip_sync:
            self.local_sync()

        # Then if this row exists
        if not self.prim_key_id:
            sql_expression_1 = f"SELECT {self.PRIM_KEY_NAME} FROM {self.TABLE} WHERE user_id = %s AND chat_session_num = %s"
            result = await maica_pool.query_get(expression=sql_expression_1, values=(user_id, session_num))
        else:
            result = (self.prim_key_id, )

        # Then update or new
        if result:
            prim_key_id, = result
            sql_expression_2 = f"UPDATE {self.TABLE} SET content = %s WHERE {self.PRIM_KEY_NAME} = %s"
            result = await maica_pool.query_modify(expression=sql_expression_2, values=(self.content, prim_key_id))
        else:
            await messenger(self.fsc.websocket, f'{self.i_name}_not_present', f"Determined {self.i_name} not exist, inserting new", 306, self.fsc.tracker_id)
            sql_expression_2 = f"INSERT INTO {self.TABLE} (user_id, chat_session_num, content) VALUES (%s, %s, %s)"
            result = await maica_pool.query_modify(expression=sql_expression_2, values=(user_id, session_num, self.content))
            prim_key_id = result[1]

        if not self.prim_key_id:
            self.prim_key_id = prim_key_id

    async def from_db(self):
        # Common
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num
        maica_pool = self.fsc.maica_pool
        assert user_id and session_num and maica_pool, "DB cridentials not complete"
        maica_assert(self.SESSION_DB_MIN <= session_num < self.SESSION_DB_BELOW, full_info=f"{session_num} is not acceptable {self.i_name}")

        # First get data & existence
        sql_expression_1 = f"SELECT {self.PRIM_KEY_NAME}, content FROM {self.TABLE} WHERE user_id = %s AND chat_session_num = %s"
        result = await maica_pool.query_get(expression=sql_expression_1, values=(user_id, session_num))

        # Then load or warn
        if result:
            prim_key_id, db_content = result
            if db_content:
                self.load(db_content)
            else:
                self.clear()
                await messenger(self.fsc.websocket, f'{self.i_name}_no_content', f"Determined {self.i_name} no content, using empty", 306, self.fsc.tracker_id)
        else:
            prim_key_id = None; db_content = ''
            self.clear()
            await messenger(self.fsc.websocket, f'{self.i_name}_not_exist', f"Determined {self.i_name} not exist, using empty", 306, self.fsc.tracker_id)

        if not self.prim_key_id:
            self.prim_key_id = prim_key_id

    def destroy(self):
        if not self.is_destroyed:
            self.reset()
            self.fsc = None
            self.is_destroyed = True

