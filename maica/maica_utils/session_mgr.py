"""
Import layer 4.1
This module is for v2 session management, applied for DAA4.
"""
import time
import orjson
import types
import sqlalchemy
from sqlalchemy.orm import load_only

from typing import *
from pydantic import BaseModel, Field, model_validator
from pydantic.dataclasses import dataclass as pdataclass
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from .maica_utils import *
from .fsc_late import *
from .db_bound_obj import DbBoundObject
from .session_rel import SessionPersistentMixin, SessionTriggerMixin
from .database_models import *

_Bt = BilingualText

@pdataclass
class MaicaSessionItem():
    """Element of MaicaSession."""
    class Context(BaseModel):
        """Specifically context object of MaicaSessionItem."""
        strict_conv: bool = True
        player_name: str = "[player]"
        apply_nickname: bool = True
        nsfw_acceptive: bool = True
        known_info: dict[
            str,
            Union[
                str,
                BilingualText,
            ]
        ] = Field(default_factory=dict)
        image_urls: list[str] = Field(default_factory=list)
        memory_concl: Optional[str] = None

    role: Literal["system", "user", "assistant", "misc"] = 'misc'
    content: str | BilingualText = ''
    target_lang: Optional[Literal['zh', 'en', 'auto']] = None
    context: Context = Field(default_factory=Context)

    # If item role is misc, we stop using maica format and store entire object.
    preserved: dict = field(default_factory=dict)

    def __post_init__(self):
        self.timestamp = time.time()

    def load(self, item: dict):
        assert isinstance(item, dict), f"Session item can only load from dict, {type(item)} {str(item)} found"
        for k, v in item.items():
            setattr(self, k, v)

    def json(self) -> dict:
        return self.model_dump()
    
    def utilize(self, text_only: Literal[False, None, True] = None) -> dict:
        """
        text_only:
        False: force image
        None: auto decide (for core model)
        True: disable image
        """
        if self.role in ["system", "user", "assistant"]:
            d = {"role": self.role}
            content = to_str(self.content, self.target_lang)

            if (
                (
                    is_mcore_vl()
                    and not text_only is True
                ) or
                text_only is False
            ):
                image_urls = self.context.image_urls
                if image_urls:
                    content = [
                        {"type": "text", "text": content}
                    ]
                    for url in image_urls:
                        content.append({"type": "image_url", "image_url": {"url": url}})

            d["content"] = content
            return d
        
        else:
            return self.preserved

    def form_known_info(self):
        """
        Form the known_info dict into a str. Maybe we use markdown since it's more modern.
        Note that in v1.3, we have unified known_info, so it's completely dict[str, str].
        """
        known_info = self.context.known_info
        # {
        #     "time_acquire": "现在是...",
        #     "date_acquire": "今天是...",
        #     "persistent_acquire": "莫妮卡...; [player]...",
        #     "mt_prediction": "用户的请求是可以完成的...",

        # Specially, mf_llm_concl is also here:
        #     "generated_guidance": "总的来说, ...",
        # If generated_guidance exist, we ignore everything else.
        # }

        if known_info:
            if "generated_guidance" in known_info:
                known_str = known_info["generated_guidance"]

            else:
                known_str = _Bt()
                for t in known_info.values():
                    known_str += "\n- "
                    known_str += t
                known_str += "\n"
        else:
            known_str = ""
        return known_str
    
    def context_from_fsc(self, fsc: FullSocketsContainer):
        """Gets basic context from a fsc."""
        self.target_lang = fsc.maica_settings.basic.target_lang

        context = self.context
        context.strict_conv = fsc.maica_settings.temp.common.strict_conv
        context.nsfw_acceptive = fsc.maica_settings.extra.nsfw_acceptive
        context.image_urls = fsc.maica_settings.temp.mvista.mv_imgs

class MaicaSession(list[MaicaSessionItem], DbBoundObject):
    """
    The v2 session.
    """
    SESSION_DB_MIN = 1
    _model = SqlChatSession

    def clear(self):
        list.clear(self)
        DbBoundObject.clear(self)

    def reset(self):
        super().reset()

        self.default_target_lang: Literal['zh', 'en', 'auto'] = 'zh'
        self.default_context = MaicaSessionItem.Context()

        # Should we load fsc settings into defaults here?
        # We probably should.
        self.default_target_lang = self.fsc.maica_settings.basic.target_lang
        self.default_context.strict_conv = self.fsc.maica_settings.temp.common.strict_conv
        self.default_context.apply_nickname = self.fsc.maica_settings.extra.prompt_allow_nickname
        self.default_context.nsfw_acceptive = self.fsc.maica_settings.extra.nsfw_acceptive

    def __init__(self, session_num: int = 0, fsc: Optional[FullSocketsContainer] = None, *args, **kwargs):
        # Initialize the base list class
        list.__init__(self, *args, **kwargs)
        DbBoundObject.__init__(self, session_num, fsc)
        # It should also autorun DbBoundObject.__post_init__()
        # which also runs self.reset()

    def _sync_session_item(self, object: MaicaSessionItem):
        object.target_lang = object.target_lang or self.default_target_lang
        for field in self.default_context.__class__.model_fields.keys() - object.model_fields_set:
            setattr(object, field, getattr(self.default_context, field))

    # We override append to automatically manage context
    def append(self, object):
        if isinstance(object, MaicaSessionItem):
            self._sync_session_item(object)
        return super().append(object)
    
    # Well we have to use insert sometimes
    def insert(self, index, object):
        if isinstance(object, MaicaSessionItem):
            self._sync_session_item(object)
        return super().insert(index, object)
    
    # Just doing it for safety
    def extend(self, iterable):
        for object in iterable:
            if isinstance(object, MaicaSessionItem):
                self._sync_session_item(object)
        return super().extend(iterable)
    
    def load(self, item: Union[list, str]):
        self.clear()
        super().load(item)
        for i in self.content:
            si = MaicaSessionItem(); si.load(i)
            self.append(si)

    def sanitize(self):
        # Make sure system is #0
        if not len(self) or not self[0].role == "system":
            self.insert(0, MaicaSessionItem("system"))

    def _utilize_context(
            self,
            manual_prompt: Optional[Literal[True] | str | BilingualText] = None,
            ignore_additions: bool = False,
        ):
        """
        Parses corresponding contexts into prompt information, and automatically replaces it.
        Manual prompt mainly for tool LLMs. This way we make messages construction look prettier.
        """

        # First sanitize
        self.sanitize()
        assert len(self) > 1, "No item could be utilized"

        # Then acquire context
        curr_item = self[-1]
        curr_context = curr_item.context
        prompt_item = self[0]
        prompt_context = prompt_item.context
        target_lang = curr_item.target_lang

        # Then generate system prompt from context
        if curr_context.strict_conv:
            prompt = _Bt(
                G.A.PROMPT_ZC,
                G.A.PROMPT_EC,
                G.A.PROMPT_AC,
            )
        else:
            prompt = _Bt(
                G.A.PROMPT_ZW,
                G.A.PROMPT_EW,
                G.A.PROMPT_AW,
            )

        # Extend the prompt for conditions
        if curr_context.nsfw_acceptive:
            prompt += _Bt(
                G.A.PROMPT_ZNP,
                G.A.PROMPT_ENP,
                G.A.PROMPT_ANP
            )

        # At this point, manual_prompt should kick in
        # If manual_prompt is provided, we ignore strict_conv, nsfw_acceptive
        if manual_prompt:
            if not isinstance(manual_prompt, _Bt):
                prompt = _Bt(manual_prompt)
            elif isinstance(manual_prompt, str):
                prompt = manual_prompt
            else:
                # Set to True, we take the actual current context as manual
                prompt = prompt_item.content

        # For later formatting, like {known_info}
        format_kvs = {}

        if not ignore_additions:
            # Parse known info
            if curr_context.known_info:
                prompt += "\n"
                prompt += _Bt(
                    G.A.PROMPT_ZKP,
                    G.A.PROMPT_EKP,
                    G.A.PROMPT_AKP,
                )
                format_kvs["known_info"] = curr_item.form_known_info()

            # Add memory conclusion
            if prompt_context.memory_concl:
                prompt += _Bt(
                    G.A.PROMPT_ZMP,
                    G.A.PROMPT_EMP,
                    G.A.PROMPT_AMP,
                )
                format_kvs['memory_concl'] = prompt_context.memory_concl

            for k, v in format_kvs:
                format_kvs[k] = to_str(v, target_lang)

        prompt = prompt.format(
            player_name=curr_context.player_name,
            player_nickname="[player_nickname]" if curr_context.apply_nickname else "",
            **format_kvs,
        )

        # Then inject
        # Note that system prompt item should not be modified from external
        self[0].content = prompt

    def json(self) -> list:
        self._utilize_context()
        return [i.json() for i in self]
    
    def utilize(
            self,
            text_only: Literal[False, None, True] = None,
            manual_prompt: Optional[Literal[True] | str | BilingualText] = None,
            ignore_additions: bool = False,
        ):
        # If session == -1, we shall preserve the prompt as-is
        # If using custom inner sessions, override params insead of using -1
        session_num = self.session_num
        if session_num >= 0:
            self._utilize_context(manual_prompt, ignore_additions)
        else:
            self.sanitize()
        return [i.utilize(text_only) for i in self]
    
    async def to_archive(self) -> int:
        """This requires self.prim_key_id to function."""
        # Common
        self._check_ess()

        # Ensure row exists
        if not self.prim_key_id:
            await self.init_db()

        async with DatabaseUtils.SessionData() as dbs:
            model = self._model
            arc_model = SqlCropArchived

            stmt = sqlalchemy.select(arc_model).where(
                arc_model.chat_session_id == self.prim_key_id,
                arc_model.archived == False,
            ).options(
                load_only(arc_model.id)
            )

            arc_obj = await dbs.scalar(stmt)
            if not arc_obj:
                arc_obj = arc_model(
                    chat_session_id=self.prim_key_id,
                    content=orjson.dumps(self.json()).decode(),
                )
                dbs.add(arc_obj)

            else:
                archive_content = arc_obj.content
                archive_content_j = orjson.loads(archive_content)
                archive_content_j.extend(self.json())
                archive_content = orjson.dumps(archive_content_j).decode()
                arc_obj.content = archive_content

            should_seal = len(archive_content) >= 100000
            arc_obj.archived = should_seal

            await dbs.commit()
    
    async def crop_length(self) -> Tuple[list, Literal[0, 1, 2]]:
        """Making it V2 style."""
        use_api = bool(int(G.A.CALC_TOKENS))
        max_length = self.fsc.maica_settings.basic.session_len_limit
        warn_length = int(max_length * (2/3))
        generate_length = self.fsc.maica_settings.super.max_tokens

        async def _tokens_calc(messages):
            # This method lets model deployment calculate tokens amount
            # With vllm optimizations and local network, it should be fast enough for loop calculation
            # I'm not that sure

            host_info = ExplainUrl(G.A.MCORE_ADDR)
            return (await dld_json(f"{host_info[0]}://{host_info[1]}:{host_info[2]}/tokenize", False, False, 'post', carriage={"messages": messages}))['count']

        async def tokens_calc(messages):
            if use_api:
                # vllm is not stable sometimes, so we add sanity check
                count = await _tokens_calc(messages)
                sane_minimal = len(''.join([i['content'] for i in messages]))
                sane_maximal = max_length + generate_length + 100
                assert sane_minimal <= count <= sane_maximal, f"Token counting API bahvior insane, returning {count} out of range {sane_minimal}-{sane_maximal}"
            else:
                # It's binary already, we just take bytes / 3 as a approximation of token count
                return len(orjson.dumps(messages)) / 3

        def tokens_eval(count):
            match count:
                case x if x < warn_length:
                    return 0
                case x if warn_length <= x < max_length:
                    return 1
                case x if max_length <= x:
                    return 2
                
        cycle = 0; last_self_len = len(self)
        archiver = MaicaSession()
        if not self.prim_key_id:
            await self.init_db()
        archiver.default_context = self.default_context
        archiver.prim_key_id = self.prim_key_id

        while True:
            cycle += 1
            messages = self.utilize(text_only=True)
            message_len = await tokens_calc(messages)
            messages_stat = tokens_eval(message_len)

            # If the session exceeds max length, we want to crop it until it goes below warn length
            # So we don't have to perform this too often
            if cycle <= 1:
                initial_stat = messages_stat
                stat_threshold = 0 if initial_stat >= 2 else 1
            if messages_stat <= stat_threshold:
                break

            # Here the session needs cropping
            while self[-1].role != "assistant" and len(self) > 1:
                archiver.insert(0, self.pop(-1))

            # Here be the deadlock preventions
            if last_self_len == len(self):
                raise MaicaDbWarning(f"Session cropper hit unexpected dead loop.\nSelf dump: {str(self)}\nArchiver dump: {str(archiver)}")
            last_self_len = len(self)

            if cycle >= 100:
                sync_messenger(f"Session cropper hit extreme fragmentation.\nSelf dump: {str(self)}\nArchiver dump: {str(archiver)}\nBreaking loop and trying to continue", tracker_id=self.fsc.tracker_id, type=MsgType.WARN)
                break

        # Now finished cropping
        return archiver, initial_stat
    
    async def wrapped_save(self) -> Literal[0, 1, 2]:
        """V1 comtatible behavior."""
        archiver, stat = await self.crop_length()
        await self.to_db()
        if len(archiver):
            await archiver.to_archive()
        return stat

# These should be far more simple
class SessionPersistent(DbBoundObject, SessionPersistentMixin):
    
    _model = SqlPersistent
    _empty = dict

    def clear(self):
        self.clear_temp()
        return super().clear()
    
    def clear_temp(self):
        self.content_temp = {}

class SessionTrigger(DbBoundObject, SessionTriggerMixin):

    _model = SqlTrigger

    def clear(self):
        self.clear_temp()
        return super().clear()
    
    def clear_temp(self):
        self.content_temp = []
    
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
"""
What now, we maintain an index to store all session-relative DBOs.
The next layer of dict is for types.
"""

_DboType = TypeVar('_DboType', bound="DbBoundObject")

async def _get_real_session_num(dbo: _DboType | DbBoundObject, fsc: FullSocketsContainer) -> int:
    """Some dbos use session 0 if determined not exist. Input DBO cls here just for convenience."""
    user_id = fsc.maica_settings.verification.user_id; session_num = fsc.maica_settings.temp.chat_session

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

def _id_acquire_dbo(cls: _DboType, sub_dict_k: str, user_id: int, session_num: int) -> MaicaSession | SessionPersistent | SessionTrigger:
    global _sessions_index
    assert user_id > 0, "Sessions are designed to be user-bound, do not acquire system-wide"
        
    sub_dict = _sessions_index[sub_dict_k]

    # Ensure it exists in index
    mapping = (user_id, session_num)
    if not mapping in sub_dict.keys():
        sub_dict[mapping] = [cls(session_num), time.time()]
    # This shouldn't happen theoretically, but we cover it anyway
    elif sub_dict[mapping][0].is_destroyed:
        sub_dict[mapping] = [cls(session_num), time.time()]
    else:
        sub_dict[mapping][1] = time.time()

    session = sub_dict[mapping][0]

    return session
        
async def _fsc_acquire_dbo(type: Literal["session", "persistent", "trigger"], fsc: FullSocketsContainer):
    user_id = fsc.maica_settings.verification.user_id; session_num = fsc.maica_settings.temp.chat_session

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

    match type:
        case "session" if session_num <= 0:
            # Temporary session, reset everytime
            session.reset()
        case "persistent" | "trigger":
            session.clear_temp()

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
    for n, l in _sessions_index.items():
        for k, v in l.items():
            if v[1] < timestamp and not v[0].lock.locked():
                v[0].destroy()
                _sessions_index.pop(k)
                gced.append((n, k))
    return gced