"""
DB bound instances look alike, so what about we write all-in-one and let things inherit.
"""

import asyncio
import orjson
import functools
import types

import sqlalchemy
from sqlalchemy.orm import load_only

from typing import *
from pydantic import Field
from .maica_utils import *
from .fsc_late import FullSocketsContainer
from .database_utils import *
from .database_models import *

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

@dataclass
class DbBoundObject(CheckDestroyed):
    """
    A basic db-bound object.
    This is like the concept of ORM, but I made this before even knowning it.
    _model and fsc are required to function, fill in sub objects.

    Something to notice, this is designed to be session_num bound. WILL NOT change session_num on fsc change.
    Notice: This cannot inherit from BaseModel because subclasses might inherit from list (session).
    """
    session_num: int = 0
    """fsc chat_session is flexible, we shouldn't depend on it if we want this to be session-unique."""
    fsc: Optional[FullSocketsContainer] = None

    _model: ClassVar[Type[SqlBaseData]]

    SESSION_DB_MIN: ClassVar[int] = 0
    SESSION_DB_BELOW: ClassVar[int] = 10

    _empty = list
    """To properly reset self. Override if necessary."""

    def clear(self):
        self.text: str = ''
        self.content: Union[dict, list] = self._empty()

    def reset(self):
        """Normally just use clear."""
        self.prim_key_id: Optional[int] = None
        self.clear()

    def __post_init__(self):
        self.i_name = self._model.__tablename__
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
            if not item:
                raise MaicaInputWarning("Cannot load empty serialized data")
            if item[0] not in ('[', '{'):
                item = f"[{item}]"
            self.content = orjson.loads(item)
            self.text = item

    def _post_upload(self, *args, **kwargs):
        """For post-upload checks. Override it."""
        ...

    def local_sync(self, from_which: Literal["text", "content"] = "content"):
        """Sync local contents, run before to_db."""
        match from_which:
            case "text":
                self.load(self.text)
            case "content":
                self.load(self.content)

    def _check_ess(self):
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num
        if not user_id or session_num is None:
            raise MaicaDbError("DB credentials not complete")
        maica_assert(self.SESSION_DB_MIN <= session_num < self.SESSION_DB_BELOW, full_info=f"{session_num} is not acceptable {self.i_name}")

    async def init_db(self):
        # Common
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num
        self._check_ess()

        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():

                obj = await sqla_get_or_create(
                    dbs,
                    self._model,
                    {
                        "user_id": user_id,
                        "chat_session_num": session_num,
                    },
                    requires=("id", ),
                )
            
        self.prim_key_id = obj.id

    async def to_db(self, skip_sync = False):
        # Common
        self._check_ess()

        # First prepare data
        # If skip_sync is used, by default we assume it's uploading
        if not skip_sync:
            self.local_sync()
        else:
            # So, we run post_upload checks here
            try:
                self._post_upload()
            except CommonMaicaException:
                self.clear()
                raise
            except Exception as exc:
                self.clear()
                raise MaicaInputWarning(f"Invalid {self.i_name} content: {exc}") from exc

        # Ensure row exists
        if not self.prim_key_id:
            await self.init_db()

        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():
                model = self._model

                # Update content
                stmt = sqlalchemy.update(model).where(
                    model.id == self.prim_key_id,
                ).values(
                    content=self.text,
                )

                await dbs.execute(stmt)

    async def from_db(self):
        # Common
        self._check_ess()

        # Ensure row exists
        if not self.prim_key_id:
            await self.init_db()

        async with DatabaseUtils.SessionData() as dbs:
            model = self._model

            stmt = sqlalchemy.select(model).where(
                model.id == self.prim_key_id,
            ).options(
                load_only(model.content),
            )

            obj = await dbs.scalar(stmt)

            if obj.content:
                self.load(obj.content)
            else:
                self.clear()

    def destroy(self):
        if not self.is_destroyed:
            self.reset()
            self.fsc = None
            self.is_destroyed = True
