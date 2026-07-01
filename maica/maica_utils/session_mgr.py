"""
Import layer 4.1
This module is for v2 session management, applied for DAA4.
"""
import time
import orjson
import types
from typing import *
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from .maica_utils import *
from .fsc_late import *
from .db_bound_obj import DbBoundObject
from .session_rel import SessionPersistentMixin, SessionTriggerMixin

@dataclass
class MaicaSessionItem():
    role: Literal["system", "user", "assistant", "misc"] = 'misc'
    content: str | BilingualText = ''
    target_lang: Optional[Literal['zh', 'en', 'auto']] = None
    # There might be other things here, like tool_call_id
    context: dict = field(default_factory=lambda: {})
        # "strict_conv": True,
        # "player_name": "[player]",
        # "nsfw_acceptive": True,
        # "known_info": {},
        # "image_urls": [],
        # "memory_concl": "",
        # Extra kvs are valid here, expect them in procedures

    # If item role is misc, we stop using maica format and store entire object.
    preserved: dict = field(default_factory=lambda: {})

    timestamp = time.time()

    def __post_init__(self):
        assert self.role in ["system", "user", "assistant", "misc"], f"Role not recognizable: {self.role}"

    def load(self, item: dict):
        assert isinstance(item, dict), f"Session item can only load from dict, {type(item)} {str(item)} found"
        for k, v in item.items():
            setattr(self, k, v)

    def json(self) -> dict:
        data = dict(vars(self))
        if isinstance(data["content"], BilingualText):
            data["content"] = data["content"].to_str(self.target_lang)
        return data
    
    def utilize(self, text_only: Literal[False, None, True] = None) -> dict:
        """
        text_only:
        False: force image
        None: auto decide (for core model)
        True: disable image
        """
        if self.role in ["system", "user", "assistant"]:
            d = {"role": self.role}
            content = self.content if isinstance(self.content, str) else self.content.to_str(self.target_lang)

            if is_mcore_vl() and not text_only is True:
                image_urls = self.context.get(image_urls)
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

    def form_known_info(self) -> str:
        """Form the known_info dict into a str. Maybe we use markdown since it's more modern."""
        known_info = self.context.get("known_info"); known_str = ""
        # {
        #     "time_acquire": "现在是...",
        #     "date_acquire": "今天是...",
        #     "persistent_acquire": ["莫妮卡...", "[player]..."]
        # }
        for k, v in known_info.items():
            if isinstance(v, list):
                v = "; ".join(v)
            known_str += f"\n- {v}"
        known_str += "\n"
        return known_str

class MaicaSession(list[MaicaSessionItem], DbBoundObject):
    """
    The v2 session.
    """
    TABLE: ClassVar[Optional[str]] = "chat_session"
    PRIM_KEY_NAME: ClassVar[Optional[str]] = "chat_session_id"
    SESSION_DB_MIN = 1

    def clear(self):
        list.clear(self)
        DbBoundObject.clear(self)

    def reset(self):
        super().reset()

        self.default_target_lang: Literal['zh', 'en', 'auto'] = 'zh'
        self.default_context: dict = {
            "strict_conv": True,
            "player_name": "[player]",
            "nsfw_acceptive": True,
            # We make it dict to be flexible
            "known_info": {},
            "image_urls": [],
            "memory_concl": "",
        }

    def __init__(self, session_num: int = -1, fsc: Optional[FullSocketsContainer] = None, *args, **kwargs):
        # Initialize the base list class
        list.__init__(self, *args, **kwargs)
        DbBoundObject.__init__(self, session_num, fsc)
        # It should also autorun DbBoundObject.__post_init__()

    # We override append to automatically manage context
    def append(self, object):
        if isinstance(object, MaicaSessionItem):
            object.target_lang = object.target_lang or self.default_target_lang
            object.context = self.default_context | object.context
        return super().append(object)
    
    # Well we have to use insert sometimes
    def insert(self, index, object):
        if isinstance(object, MaicaSessionItem):
            object.target_lang = object.target_lang or self.default_target_lang
            object.context = self.default_context | object.context
        return super().insert(index, object)
    
    # Just doing it for safety
    def extend(self, iterable):
        for object in iterable:
            if isinstance(object, MaicaSessionItem):
                object.target_lang = object.target_lang or self.default_target_lang
                object.context = self.default_context | object.context
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

    def _prepare_context(self):
        def _basic_gen_system(target_lang, strict_conv):
            if target_lang == 'zh':
                if strict_conv:
                    prompt = G.A.PROMPT_ZC
                else:
                    prompt = G.A.PROMPT_ZW
            elif target_lang == 'en':
                if strict_conv:
                    prompt = G.A.PROMPT_EC
                else:
                    prompt = G.A.PROMPT_EW
            else:
                if strict_conv:
                    prompt = G.A.PROMPT_AC
                else:
                    prompt = G.A.PROMPT_AW
            return prompt
        
        # First sanitize
        self.sanitize()
        assert len(self) > 1, "No query could be utilized"

        # Then acquire context
        curr_item = self[-1]
        curr_context = curr_item.context

        # Then generate system prompt from context
        prompt = _basic_gen_system(curr_item.target_lang, curr_context['strict_conv'])
        exprompt = ""; format_kvs = {}; strip_following_spaces = False

        if curr_context['nsfw_acceptive']:
            if curr_item.target_lang == 'zh':
                prompt += G.A.PROMPT_ZNP
            elif curr_item.target_lang == 'en':
                prompt += G.A.PROMPT_ENP
            else:
                prompt += G.A.PROMPT_ANP

        if curr_context['known_info']:
            if curr_item.target_lang == 'zh':
                exprompt = G.A.PROMPT_ZKP
            elif curr_item.target_lang == 'en':
                exprompt = G.A.PROMPT_EKP
            else:
                exprompt = G.A.PROMPT_AKP

            if strip_following_spaces:
                exprompt = exprompt.strip()
            
            prompt += exprompt
            format_kvs['known_info'] = curr_item.form_known_info()
            strip_following_spaces = True

        prompt_item = self[0]
        prompt_context = prompt_item.content

        if prompt_context['memory_concl']:
            if curr_item.target_lang == 'zh':
                exprompt += G.A.PROMPT_ZMP
            elif curr_item.target_lang == 'en':
                exprompt += G.A.PROMPT_EMP
            else:
                exprompt += G.A.PROMPT_AMP

            if strip_following_spaces:
                exprompt = exprompt.strip()
            
            prompt += exprompt
            format_kvs['memory_concl'] = prompt_context['memory_concl']
            strip_following_spaces = True

        prompt = prompt.format(player_name=curr_context['player_name'], **format_kvs)

        # Then inject
        # Note that system prompt item should not be modified from external
        self[0].content = prompt

    def json(self) -> list:
        self._prepare_context()
        return [i.json() for i in self]
    
    @overload
    def utilize(self, text_only: Literal[False, None, True] = None) -> list: ...

    def utilize(self, *args, **kwargs):
        # If session == -1, we shall preserve the prompt
        session_num = self.session_num
        if session_num >= 0:
            self._prepare_context()
        else:
            self.sanitize()
        return [i.utilize(*args, **kwargs) for i in self]
    
    async def to_archive(self) -> int:
        """This requires self.prim_key_id to function."""
        # Common + prim_key_id
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num
        maica_pool = self.fsc.maica_pool
        assert user_id and session_num and maica_pool and self.prim_key_id, "DB cridentials not complete"
        maica_assert(self.SESSION_DB_MIN <= session_num < self.SESSION_DB_BELOW, full_info=f"{session_num} is not acceptable {self.i_name}")

        # First if an open archive exists
        sql_expression_1 = 'SELECT archive_id, content FROM crop_archived WHERE chat_session_id = %s AND archived = 0'
        result = await maica_pool.query_get(expression=sql_expression_1, values=(self.prim_key_id, ))

        # Then update or new
        if result:
            archive_id, archive_content = result
            json_archive: list = orjson.loads(archive_content)
            json_archive.extend(self.json())
            archive_content = orjson.dumps(json_archive).decode()

            # We control archives' length within a fair range by sealing large archives
            should_seal = int(len(archive_content) >= 100000)

            sql_expression_2 = "UPDATE crop_archived SET content = %s, archived = %s WHERE archive_id = %s"
            await maica_pool.query_modify(expression=sql_expression_2, values=(archive_content, should_seal, archive_id))
        else:
            archive_content = orjson.dumps(self.json()).decode()
            should_seal = int(len(archive_content) >= 100000)
            sql_expression_2 = "INSERT INTO crop_archived (chat_session_id, content, archived) VALUES (%s, %s, %s)"
            await maica_pool.query_modify(expression=sql_expression_2, values=(self.prim_key_id, archive_content, should_seal))
    
    async def crop_length(self) -> Tuple[list, Literal[0, 1, 2]]:
        """Making it V2 style."""
        use_api = bool(int(G.A.CALC_TOKENS))
        max_length = self.fsc.maica_settings.basic.max_length
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
    
    def sync_fsc_settings(self, fsc: Optional[FullSocketsContainer] = None):
        """Syncs fsc settings into self default. Only use for main session."""
        if not fsc:
            # If syncing with pre-inserted fsc, this is likely a managed session
            # That's why we add a check here
            fsc = self.fsc
            assert self.session_num == fsc.maica_settings.temp.chat_session, "This is NOT the session you want, re-acquire first"
        assert fsc, "fsc must exist to sync"

        self.default_target_lang = fsc.maica_settings.basic.target_lang
        self.default_context.update({
                "strict_conv": fsc.maica_settings.temp.strict_conv,
                "player_name": "[player]",
                "nsfw_acceptive": fsc.maica_settings.extra.nsfw_acceptive,
                "image_urls": fsc.maica_settings.temp.mv_imgs if is_mcore_vl() else [],
            }
        )

# These should be far more simple
class SessionPersistent(DbBoundObject, SessionPersistentMixin):
    TABLE: ClassVar[Optional[str]] = "persistents"
    PRIM_KEY_NAME: ClassVar[Optional[str]] = "persistent_id"

    _empty = lambda: {}

    def clear(self):
        self.content_temp = {}
        return super().clear()
    
    def from_db(self):
        return super().from_db()

class SessionTrigger(DbBoundObject, SessionTriggerMixin):
    TABLE: ClassVar[Optional[str]] = "triggers"
    PRIM_KEY_NAME: ClassVar[Optional[str]] = "trigger_id"

    def clear(self):
        self.content_temp = []
        return super().clear()
    
    def from_db(self):
        return super().from_db()
    
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
    table = dbo.TABLE; pkn = dbo.PRIM_KEY_NAME
    user_id = fsc.maica_settings.verification.user_id; session_num = fsc.maica_settings.temp.chat_session
    sql_expression = f'SELECT {pkn} FROM {table} WHERE user_id = %s AND chat_session_num = %s'
    if not await fsc.maica_pool.query_get(sql_expression, (user_id, session_num)):
        return 0
    else:
        return session_num

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
    session.fsc = fsc

    match type:
        case "session" if session_num <= 0:
            # Temporary session, reset everytime
            session.reset()

    return session

@asynccontextmanager
async def acquire_dbo(type: Literal["session", "persistent", "trigger"], fsc: FullSocketsContainer):
    """This should be used as context manager!"""
    session = _fsc_acquire_dbo(type, fsc)
    async with session.lock:
        yield session

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