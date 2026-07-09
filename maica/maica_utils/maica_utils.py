"""Import layer 1"""
import logging
import asyncio
import httpx
import aiomysql
import openai
import functools
import hashlib
import os
import re
import json
import inspect
import platform
import colorama
import time
import datetime
import random
import traceback
import websockets

from typing import *
from tenacity import *
from pydantic import BaseModel, model_validator
from pydantic.dataclasses import dataclass as pdataclass
from dataclasses import dataclass
from abc import ABC, abstractmethod
from openai.types.chat import ChatCompletionMessage
from typing_extensions import deprecated
from urllib.parse import urlparse
from .locater import *
from .gvars import *

_READ_KWDS = {'select', 'show', 'explain', 'describe'}
_WRITE_KWDS = {
'insert', 'update', 'delete', 'create', 'alter', 
'drop', 'truncate', 'replace', 'merge'
}

colorama.init(autoreset=True)

logger = logging.getLogger('maica')
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    # To prevent this executing twice

    main_handler = logging.StreamHandler(sys.stdout)
    main_handler.setLevel(logging.DEBUG)
    main_handler.addFilter(lambda record: record.levelno <= logging.WARNING)
    err_handler = logging.StreamHandler(sys.stderr)
    err_handler.setLevel(logging.ERROR)

    logger.addHandler(main_handler)
    logger.addHandler(err_handler)

def silent(tf: bool=True) -> None:
    global _silent, logger
    _silent = tf
_silent = False

class _lmlogger():
    """
    Python logging does not support stream output, so I made this.
    Redirect 'stream-maica' output to log file if needed.
    """
    def __init__(self, name='stream-maica'):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._buffer = ''
    
    def buff(self, text):
        self._buffer += text

    def flush(self):
        self._logger.info(self._buffer)
        self._buffer = ''

lmlogger = _lmlogger()

class MsgType():
    """For convenience."""
    PLAIN = 'plain'
    CARRIAGE = 'carriage'
    DEBUG = 'debug'
    INFO = 'info'
    LOG = 'log'
    PRIM_LOG = 'prim_log'
    SYS = 'sys'
    PRIM_SYS = 'prim_sys'
    RECV = 'recv'
    PRIM_RECV = 'prim_recv'
    WARN = 'warn'
    ERROR = 'error'

class FakeChatCompletion():
    """
    A fake OpenAI completion class. Do not use for context.
    Be cautious that this class simulates Response instead of ChatCompletion since v1.3.
    """
    def __init__(self, text):
        self.output_text = text
        self.output = [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text
                    }
                ]
            }
        ]

class CommonMaicaException(Exception):
    """This is a common MAICA exception."""
    def __init__(self, message=None, error_code=None, status=None, send=None, print=None):
        """For send and print, None means default, not False."""
        super().__init__(message)
        self.message, self.error_code, self.status, self.send, self.print = message, error_code, status, send, print

    @property
    def is_critical(self):
        return int(self.error_code) >= 500
    @property
    def is_breaking(self):
        return True
    
class CommonMaicaError(CommonMaicaException):
    """This is a common MAICA error."""
    def __init__(self, message=None, error_code=500, status='maica_unified_error', send=None, print=None):
        super().__init__(message, error_code, status, send, print)
    
class CommonMaicaWarning(CommonMaicaException):
    """This is a common MAICA warning."""
    def __init__(self, message=None, error_code=400, status='maica_unified_warning', send=None, print=None):
        super().__init__(message, error_code, status, send, print)

    @property
    def is_breaking(self):
        return False

class CriticalMaicaError(CommonMaicaError):
    """This is an unrecoverable exception, we should terminate the connection and possibly the entire process."""

class MaicaPermissionError(CommonMaicaError):
    """This suggests the user is accessing without correct permissions."""

class MaicaInputError(CommonMaicaError):
    """This suggests the input appears to be an impossible value, which is a more severe case than warning."""

class MaicaResponseError(CommonMaicaError):
    """This suggests the output is somewhat unexpected, we should terminate the connection and possibly the entire process."""

class MaicaDbError(CommonMaicaError):
    """This suggests the DB query gave an unexpected result, we should terminate the connection and possibly the entire process."""

class MaicaPermissionWarning(CommonMaicaWarning):
    """This suggests the user is accessing without correct permissions, but we don't break the connection for convenience of retrying."""

class MaicaInputWarning(CommonMaicaWarning):
    """This suggests the input is not processable."""

class MaicaDbWarning(CommonMaicaWarning):
    """This suggests the DB query gave an warning."""

class MaicaConnectionWarning(CommonMaicaWarning):
    """This suggests the connection is not behaving normal."""

class MaicaInternetWarning(CommonMaicaWarning):
    """This suggests the backend request action is not behaving normal."""

RETRYABLE_EXCEPTIONS = (
    # aiomysql.OperationalError,
    # aiomysql.InterfaceError,
    # ConnectionError,
    # TimeoutError,
    # httpx.TransportError,
    # openai.APIConnectionError,
    # openai.APITimeoutError,
    # openai.RateLimitError,
    # json.JSONDecodeError,
    # MaicaInternetWarning,

    # This is too unstable.
    Exception,
)

class AsyncCreator(ABC):
    """Inherit this for async init."""
    @abstractmethod
    async def _ainit(self):
        """Placeholder."""

    @classmethod
    async def async_create(cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        await instance._ainit()
        return instance

class LimitedList(list):
    """Might not have applied to all functionalities!"""
    def __init__(self, max_size, *args, **kwargs):
        self.max_size = max_size
        super().__init__(*args, **kwargs)
        
        while len(self) > self.max_size:
            self.pop(0)

    @property
    def list(self):
        while len(self) > self.max_size:
            self.pop(0)
        return list(self)

    def append(self, item):
        if len(self) >= self.max_size:
            self.pop(0)
        super().append(item)
    
    def extend(self, iterable):
        for item in iterable:
            self.append(item)
    
    def insert(self, index, item):
        if len(self) >= self.max_size:
            self.pop(0)
        super().insert(index, item)
    
    def __repr__(self):
        return f"LimitedList(max_size={self.max_size}, {super().__repr__()})"
    
@deprecated("Just use a tuple instead")
class LoginResult():
    """
    A packed login result.
    This does not contain ban status. Check independently.
    """
    user_id = None
    username = None
    nickname = None
    email = None
    is_verified = None
    message = None
    def __init__(self, **kwargs):
        for priokey in ['user_id', 'username', 'nickname', 'email']:
            setattr(self, priokey, kwargs.get(priokey))
        if kwargs.get('is_verified'):
            assert self.user_id and self.username and self.email, "Verification essentials incomplete"
        for key in ['is_verified', 'message']:
            setattr(self, key, kwargs.get(key))

    def __call__(self):
        d = {}
        for key in ['user_id', 'username', 'nickname', 'email', 'is_verified', 'message']:
            d[key] = getattr(self, key)
        return d

class Combiner():
    """For performance since GPT says string adding is not good."""
    def __init__(self, pre_str='', splitter=', '):
        self.str_buffer = pre_str
        self.dyn_buffer = []
        self.splitter = splitter

    def append(self, item):
        self.dyn_buffer.append(item)

    def extend(self, items):
        self.dyn_buffer.extend(items)

    def _migrate(self):
        ext_str = self.splitter.join(self.dyn_buffer)
        if self.str_buffer:
            self.str_buffer += self.splitter
        self.str_buffer += ext_str
        self.dyn_buffer.clear()

    def to_text(self):
        self._migrate()
        return self.str_buffer

class ReUtils():
    """Just a collection."""
    IS = re.I | re.S
    re_sub_password_spoiler = re.compile(r'"password"\s*:\s*"(.*?)"')
    re_search_sfe_fs = re.compile(r"first_session.*?datetime\(([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\)", re.I)
    re_search_sfe_ts = re.compile(r"total_sessions.*?([0-9]*)\s?,", re.I)
    re_search_sfe_tp = re.compile(r"total_playtime.*?([0-9]*)\s?,", re.I)
    re_search_sfe_le = re.compile(r"last_session_end.*?datetime\(([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\)", re.I)
    re_search_sfe_cs = re.compile(r"current_session_start.*?datetime\(([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\)", re.I)
    re_search_sfe_unicode = re.compile(r"u'(.*)'")
    re_search_post_think = re.compile(r'</think>[\s\n]*(.*)$', re.S)
    re_search_answer_none = re.compile(r'[\s\n:]*none[\s\n.]*$', re.I)
    re_search_answer_json = re.compile(r'^.*?([{\[].*[}\]])', re.S)
    re_sub_player_name = re.compile(r'\[player\]')
    re_match_time_acquire = re.compile(r'.*time.*acquire', IS)
    re_match_date_acquire = re.compile(r'.*date.*acquire', IS)
    re_match_weather_acquire = re.compile(r'.*weather.*acquire', IS)
    re_match_event_acquire = re.compile(r'.*event.*acquire', IS)
    re_match_persistent_acquire = re.compile(r'.*persistent.*acquire', IS)
    re_match_search_internet = re.compile(r'.*search.*internet', IS)
    re_match_react_trigger = re.compile(r'.*react.*trigger', IS)
    re_match_conclude_information = re.compile(r'.*conclude.*information', IS)
    re_match_none = re.compile(r'.*none', IS)
    re_findall_quoted = re.compile(r'"(.*?)"') # Normally we request JSON so we consider double quotes only
    re_search_location_prompt = re.compile(r'(地区|周边|附近|周围|nearby|local)', re.I)
    re_search_location_related = re.compile(r'(天气|温度|路况|降雨|weather|traffic|temperature|rain)', re.I)
    re_search_host_addr = re.compile(r"^https?://(.*?)(:|/|$).*", re.I)
    re_sub_capt_status = re.compile(r"(_|^)([A-Za-z])")
    re_findall_square_marks = re.compile(r'\[(?:(?:[A-Za-z ]{1,15}?)|(?:[一-龥 ]{1,4}?))\]')
    re_findall_square_brackets = re.compile(r'(\[.*?\])')
    re_sub_sqlite_escape = re.compile(r'%s')
    re_sub_replacement_chr = re.compile(r'[\uFFF9-\uFFFF]')
    re_sub_serp_datetime = re.compile(r'.{1,10}?,.{1,10}?-\s*')
    re_sub_clear_text = re.compile(r'^[\n\s]*(.*?)[\n\s]*$', re.S)
    re_match_secure_path = re.compile(r'^[a-zA-Z0-9_.-]+$')
    re_search_wiki_avoid = re.compile(r"(模板|模闆|template|消歧义|消歧義|disambiguation)", re.I)
    re_search_type_sping = re.compile(r'"type"\s*?:\s*?"sping"', re.I)
    re_findall_zh_characters = re.compile(r'([一-龥].*[一-龥])')
    re_sub_multi_spaces = re.compile(r'\s{2,}')
    re_sub_ellipsis = re.compile(r'\.\.\.')
    re_sub_strip_spaces = re.compile(r"\s*(.*?)\s*$", re.M)

class Decos():
    """Do not initialize."""
    def conn_retryer_factory(
        max_attempts: int=4,
        min_wait: float=1,
        max_wait: float=10,
        retry_exceptions=RETRYABLE_EXCEPTIONS,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Mostly for instance methods."""
        async def log_retry(retry_state):
            self = retry_state.args[0] if retry_state else None
            rsc = getattr(self, 'rsc', None); name = getattr(self, 'name', 'anon_conn')
            websocket = getattr(rsc, 'websocket', None); tracker_id = getattr(rsc, 'tracker_id', None)
            await messenger(websocket=websocket, status=f'{name}_temp_failure', info=f'{name} temporary failure, retrying {retry_state.attempt_number} time...', code=304, tracker_id=tracker_id, type=MsgType.WARN)

        retry_decorator = retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_exceptions),
            before_sleep=log_retry,
            reraise=True,
        )

        def decorator(func):
            @functools.wraps(func)
            @retry_decorator
            async def wrapper(self, *args, **kwargs):
                return await func(self, *args, **kwargs)
            return wrapper
        return decorator

    def log_task(func):
        """Every~time you call my name~~~"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            func_name = func.__name__
            sync_messenger(info=f"Running task {func_name} now", type=MsgType.PRIM_SYS)
            result = await func(*args, **kwargs)
            sync_messenger(info=f"Task {func_name} finished", type=MsgType.DEBUG)
            return result
        return wrapper

    def catch_exceptions(func):
        """Used for connection_utils."""
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            name = getattr(self, 'name', 'anon_conn')
            try:
                return await func(self, *args, **kwargs)
            except CommonMaicaException as ce:
                raise ce
            except websockets.WebSocketException as we:
                raise we
            except Exception as e:

                match self:
                    case i if getattr(i, "db_type", None) in ("mysql", "sqlite"):
                        exception_cls = MaicaDbError
                        conn_type = 'db_conn'
                    case i if getattr(i, "db_type", None) in ("milvus",):
                        exception_cls = MaicaDbError
                        conn_type = 'vdb_conn'
                    case _:
                        exception_cls = MaicaResponseError
                        conn_type = 'ai_conn'

                raise exception_cls(f'{name} operation failed: {str(e)}', 502, f'{conn_type}_failed') from e
        return wrapper

    def escape_sqlite_expression(func):
        """Used to transform a MySQL expression to SQLite one."""
        @functools.wraps(func)
        def wrapper(self, expression: str, *args, **kwargs):

            expression_new = ReUtils.re_sub_sqlite_escape.sub('?', expression)
            expression_new = expression_new.replace('JSON_SET', 'json_set')

            return func(self, expression_new, *args, **kwargs)
        return wrapper
    
    def ro_expression(func):
        """Used to keep DB query ro."""
        @functools.wraps(func)
        def wrapper(self, expression: str, *args, **kwargs):
            assert not is_word_start(expression.lower(), *_WRITE_KWDS), f'query_get got write expression {expression}'
            return func(self, expression, *args, **kwargs)
        return wrapper
    
    def wo_expression(func):
        """Used to keep DB query wo."""
        @functools.wraps(func)
        def wrapper(self, expression: str, *args, **kwargs):
            assert not is_word_start(expression.lower(), *_READ_KWDS), f'query_modify got read expression {expression}'
            return func(self, expression, *args, **kwargs)
        return wrapper

    def report_data_error(func):
        """Raises when the requested action cannot be done because of corrupted data."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise MaicaInputWarning(f'Acquired persistent not acceptable: {str(e) or "Assertion"}', '405', 'maica_agent_persistent_bad') from e
        return wrapper

    def report_reading_error(func):
        """Raises when the requested variable cannot be read before assignment."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise MaicaInputError(f'Access before necessary assignment', '500', 'maica_settings_read_rejected') from e
        return wrapper

    def report_limit_warning(func):
        """Raises when the input param coming from user is out of bound."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise MaicaInputWarning(f'Input param not acceptable: {str(e) or "Assertion"}', '422', 'maica_settings_param_rejected') from e
        return wrapper

    def report_limit_error(func):
        """Raises when the input param coming from program is out of bound."""
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                assert not getattr(self, '_lock', None)
                return func(self, *args, **kwargs)
            except Exception as e:
                raise MaicaInputError(f'Input param not acceptable', '500', 'maica_settings_param_rejected') from e
        return wrapper

class ExplainUrl():
    """For convenience."""
    def __init__(self, url):
        parse_result = urlparse(url)
        self.scheme, self.netloc, self.path, self.params, self.query, self.fragment = parse_result
        self.hostname, self.port = parse_result.hostname, parse_result.port
        self.is_url = bool(self.netloc); self.is_local = not self.is_url
        if not self.port:
            match self.scheme:
                case "http":
                    self.port = 80
                case "https":
                    self.port = 443
                case "ftp":
                    self.port = 21
                case "ssh":
                    self.port = 22

@pdataclass
class BilingualText():
    """Should we call it trilingual?"""
    zh: str = ""
    en: Optional[str] = None
    auto: Optional[str] = None

    @model_validator(mode="after")
    def auto_fill(self):
        if self.en is None:
            self.en = self.zh
        if self.auto is None:
            self.auto = self.en

        return self

    def __bool__(self):
        return bool(self.zh or self.en or self.auto)

    def __str__(self):
        return self.zh
    
    def __add__(self, other):
        if isinstance(other, str):
            return self.__class__(
                zh = self.zh + other,
                en = self.en + other,
                auto = self.auto + other,
            )
        else:
            return self.__class__(
                zh = self.zh + other.zh,
                en = self.en + other.en,
                auto = self.auto + other.auto,
            )
    
    def __iadd__(self, other):
        if isinstance(other, str):
            self.zh += other
            self.en += other
            self.auto += other
        else:
            self.zh += other.zh
            self.en += other.en
            self.auto += other.auto
        return self
    
    def to_str(self, target_lang: Literal['zh', 'en', 'auto']='zh') -> str:
        if target_lang == 'zh':
            return self.zh
        elif target_lang == 'en':
            return self.en
        else:
            return self.auto

class PydUpdateMixin(BaseModel):
    """This adds update() method to pydantic models."""
    def update(self, m):
        """Updating from a dict, a pydantic object, or something alike."""
        if isinstance(m, BaseModel):
            m = m.model_dump()

        updated = set()
        for k, v in m.items():
            if k in self.__class__.model_fields:
                setattr(self, k, v)
                updated.add(k)
        return updated

class PydHardResetMixin(BaseModel):
    """This adds reset() method to pydantic models (id/vfc)."""
    def reset(self):
        """Hard reset all id/vfc values to default."""
        _crd_fields = ('_user_id', '_username', '_nickname', '_email')
        for f in _crd_fields:
            if hasattr(self, f):
                setattr(self, f, None)

class PydSoftResetMixin(BaseModel):
    """This adds reset() method to pydantic models (norm)."""
    def reset(self):
        for k, v in self.__class__.model_fields.items():
            setattr(self, k, v.get_default(call_default_factory=True))
        self.model_fields_set.clear()

@dataclass
class Desc():
    """Just a description."""
    desc: str

    def __str__(self):
        return self.desc

class DummyClass():
    """Yes, dummy class."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def default(exp, default, default_list: list=[None]) -> any:
    """If exp is in default list(normally None), use default."""
    return default if exp in default_list else exp

def wrap_ws_formatter(code, status, content, type, **kwargs) -> str:
    if not (
        isinstance(
            content,
            (str, list, dict, bool)
        ) or content is None
    ):
        content = str(content)

    output = {
        "code" : code,
        "status" : status,
        "content" : content,
        "type" : type,
        "timestamp" : time.time(),
    }

    output.update(kwargs)
    return json.dumps(output)

def ellipsis_str(input: Any, limit=80) -> str:
    """It converts anything to str and ellipsis it."""
    text = str(input)
    if len(text) > limit:
        text = text[:limit] + '...'
    return text

def ellipsis_large_str(input: Any, limit=600) -> str:
    """It converts anything large to str and ellipsis it."""
    text = str(input)
    if len(text) > limit:
        text = text[:limit] + '\n... ...'
    return text

def uscore_words_upper(text: str) -> str:
    """Overkill..."""
    def u_upper(c: re.Match):
        return f'{c[1]}{c[2].upper()}'
    return ReUtils.re_sub_capt_status.sub(u_upper, text)

def mstuff_words_upper(text: str) -> str:
    """Even more overkill..."""
    if len(text) == 0:
        return ""
    elif len(text) == 1:
        return text.upper()
    else:
        return text[:2].upper() + text[2:]

async def sleep_forever() -> None:
    """Make a coroutine sleep to the end of the world."""
    future = asyncio.Future()
    await future

def alt_tools(tools: list) -> list:
    """If ALT_TOOLCALL"""
    match G.A.ALT_TOOLCALL:
        case '0':
            return tools
        case '1':
            new_tools = []
            for tool in tools:
                new_tools.append({})
                new_tools[-1]['function'] = tool
                new_tools[-1]['type'] = 'function'
            return new_tools
        
def clean_msgs(msgs: list[dict, ChatCompletionMessage], include: Optional[list[str]]=None, exclude: Optional[list[str]]=None) -> list[dict]:
    """Clean a set of OpenAI msgs."""
    def _convert_msg(msg: Union[dict, ChatCompletionMessage]):
        if isinstance(msg, ChatCompletionMessage):
            msg = msg.model_dump(include=include, exclude=exclude)
        return msg

    return [_convert_msg(i) for i in msgs]

def maica_assert(condition, kwd='param', full_info=None):
    """Normally used for input checkings."""
    if not condition:
        raise MaicaInputWarning(full_info or f"Illegal input {kwd} detected", '405', 'maica_input_param_bad')

def has_valid_content(text: Union[str, list, dict]):
    """If the LLM actually gave anything."""
    if not text:
        return False
    
    try:
        text_json = json.loads(text)
        if isinstance(text_json, (list, dict, tuple, set)):
            return bool(text_json)
    except Exception:...

    text = str(text)
    text_proc = text.lower().replace(' ', '').replace('\n', '')
    if (not text_proc) or text_proc in ['false', 'null', 'none']:
        return False
    else:
        return True

def has_words_in(text: str, *args: str):
    """A rough matching mechanism."""
    for word in args:
        if word in text:
            return True
    return False

def is_word_start(text: str, *args: str):
    """Another rough matching mechanism."""
    for word in args:
        if text.startswith(word):
            return True
    return False

def proceed_common_text(text: str, is_json=False) -> Union[str, list, dict]:
    """Proceeds thinking/nothinking."""
    try:
        answer_post_think = (ReUtils.re_search_post_think.search(text))[1]
    except Exception:
        if has_valid_content(text):
            answer_post_think = text
        else:
            answer_post_think = None
    if answer_post_think and is_json:
        answer_fin = try_load_json(answer_post_think)
    elif answer_post_think:
        answer_fin = clean_text(answer_post_think)
    elif is_json:
        answer_fin = {}
    else:
        answer_fin = ''
    return answer_fin

@overload
async def messenger(websocket=None, status='', info='', code=0, tracker_id='', error: Optional[CommonMaicaException]=None, type='', color='', add_time=True, no_print=False, no_raise=False, **kwargs) -> None: ...

async def messenger(websocket=None, *args, **kwargs) -> None:
    """Together with websocket.send()."""
    ws_tuple = sync_messenger(*args, **kwargs)
    if websocket and ws_tuple:
        await websocket.send(wrap_ws_formatter(*ws_tuple))

def sync_messenger(status='', info='', code=0, tracker_id='', error: Optional[CommonMaicaException]=None, type='', color='', add_time=True, no_print=False, no_raise=False, **kwargs) -> tuple:
    """It could handle most log printing and exception raising jobs pretty automatically."""
    try:
        term_v = os.get_terminal_size().columns
    except:
        term_v = 40
    rep2 = int(term_v / 2)
    rep1 = int(rep2 - 20)

    code = int(code)

    if error:
        status = error.status if not status else status; info = error.message if not info else info; code = error.error_code if code == "0" else code
        no_print = False if not error.print is False else True

    if not type:
        match int(code):
            case 0:
                type = "log"
            case x if 100 <= x < 200 or 1000 <= x:
                type = "carriage"
            case x if 200 <= x < 300:
                type = "debug"
            case x if 300 <= x < 400:
                type = "info"
            case x if 400 <= x < 500:
                type = "warn"
            case x if 500 <= x < 1000:
                type = "error"

    prefix = uscore_words_upper(type)

    if 100 <= int(code) < 200 or type == "plain":
        msg_print = str(info)
        msg_send = info
        
    else:
        msg_print = f"<{prefix}>"
        msg_print = msg_print.ljust(10)
        msg_print += f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]" if add_time else ''; msg_print += f"-[{code}]"
        msg_print = msg_print.ljust(40)
        msg_print += f": {str(info)}" if not str(info).startswith('\n') else f"{'-=' * rep1}{str(info)}"
        msg_print += f" <{tracker_id}>" if tracker_id else ''
        msg_print += "" if not str(info).startswith('\n') else f"\n{'-=' * rep2}"
        msg_send = info
        if type == 'error' and int(G.A.NO_SEND_ERROR):
            msg_send = "A critical exception happened serverside, contact administrator"
        if tracker_id and isinstance(info, str):
            msg_send += f" <{tracker_id}>"

    frametrack_dict = {"error": 99, "warn": 1}
    if type in frametrack_dict:
        stack = inspect.stack()
        stack.pop(0)
        stack.pop(0)

    if (
        not no_print
        and not _silent
    ):
        match type:
            case "plain":
                print((color or '') + msg_print, end='', flush=True)
                lmlogger.buff(msg_print)
                lmlogger.flush()
            case "carriage":
                if 100 <= int(code) < 200:
                    print((color or colorama.Fore.LIGHTGREEN_EX) + msg_print, end='', flush=True)
                    lmlogger.buff(msg_print)
                else:
                    logger.info((color or colorama.Fore.LIGHTGREEN_EX) + msg_print)
            case "debug":
                logger.debug((color or colorama.Fore.LIGHTBLACK_EX) + msg_print)
            case "info":
                logger.info((color or colorama.Fore.GREEN) + msg_print)
            case "log":
                logger.info((color or colorama.Fore.BLUE) + msg_print)
            case "prim_log":
                logger.info((color or colorama.Fore.LIGHTBLUE_EX) + msg_print)
            case "sys":
                logger.info((color or colorama.Fore.MAGENTA) + msg_print)
            case "prim_sys":
                logger.info((color or colorama.Fore.LIGHTMAGENTA_EX) + msg_print)
            case "recv":
                logger.info((color or colorama.Fore.CYAN) + msg_print)
            case "prim_recv":
                logger.info((color or colorama.Fore.LIGHTCYAN_EX) + msg_print)
            case "warn":
                if 'warn' in frametrack_dict:
                    for stack_layer in stack[frametrack_dict['warn']::-1]:
                        logger.warning(color or colorama.Fore.YELLOW + f"• WARN happened when executing {stack_layer.function} at {stack_layer.filename}#{stack_layer.lineno}:")
                logger.warning((color or colorama.Fore.LIGHTYELLOW_EX) + msg_print)
            case "error":
                if 'error' in frametrack_dict:
                    for stack_layer in stack[frametrack_dict['error']::-1]:
                        logger.error((color or colorama.Fore.RED) + f"! ERROR happened when executing {stack_layer.function} at {stack_layer.filename}#{stack_layer.lineno}:")
                logger.error((color or colorama.Fore.LIGHTRED_EX) + msg_print)
    if error and not no_raise:
        raise error
    if error and error.send is False:
        return
    ws_tuple = (code, status, msg_send, type)
    return ws_tuple

def load_env(key) -> str:
    """Load something from .env."""
    result = os.getenv(key)
    return result

async def wrap_run_in_exc(loop, func, *args, **kwargs) -> any:
    """Just wrapped run_in_executer. Convenient!"""
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    return result

def limit_length[T](col: list[T], limit: int) -> list[T]:
    return random.sample(col, limit) if limit < len(col) else col

def get_ua(disguise = False):
    """Gets an UA for web requests."""
    if disguise:
        ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36"
    else:
        ua = f"MaicaDataFetcher/1.0 (dcc@monika.love) httpx/{httpx.__version__}"
    return ua

async def dld_json(url, use_proxy=True, ua_disguise=False, method='get', carriage=None) -> json:
    """Get JSON context from an endpoint."""
    headers = {'User-Agent': get_ua(ua_disguise)}

    @Decos.conn_retryer_factory()
    async def _dld_json(fake_self, url):
        nonlocal headers
        async with httpx.AsyncClient(proxy=(G.A.PROXY_ADDR or None) if use_proxy else None) as client:
            exparams = {"params": carriage} if method == 'get' else {"json": carriage}
            res = (await getattr(client, method)(url, headers=headers, **exparams)).json()
            return res

    try:
        res = await _dld_json(DummyClass(name="dld_json"), url)
    except Exception as e:
        raise MaicaInternetWarning(f"Failed downloading json from {url}: {str(e)}") from e

    return res

def numeric(num: str) -> Union[int, float]:
    try:
        return int(num)
    except ValueError:
        return float(num)

def vali_date(y, m, d) -> tuple[int, int, int]:
    """What a pun!"""
    try:
        datetime.date(int(y), int(m), int(d))
        return int(y), int(m), int(d)
    except ValueError:
        default_date = datetime.datetime.now()
        return default_date.year, default_date.month, default_date.day
    
def is_today(date: datetime.datetime) -> bool:
    """You mean my homework dues today?"""
    return date.date() == datetime.datetime.now().date()

def strip_date(date: datetime.datetime) -> str:
    """Constructs a date query our API accepts."""
    return f'{str(date.year)}-{str(date.month).zfill(2)}-{str(date.day).zfill(2)}'

def refill_date(text: str) -> datetime.datetime:
    """Constructs a datetime object from API response."""
    y, m, d = text.split('-')
    return datetime.datetime(int(y), int(m), int(d))

def add_seq_suffix(seq: int) -> str:
    """For English seq."""
    match int(seq) % 10:
        case 1:
            st = 'st'
        case 2:
            st = 'nd'
        case 3:
            st = 'rd'
        case _:
            st = 'th'
    return f'{str(seq)} {st}'

def clean_text(text: str) -> str:
    """
    Clean a text phrase, mostly for internet search.
    After adapting to the OpenAI reasoning schema, we also use it for LLM outputs.
    """
    try:
        text = ReUtils.re_sub_clear_text.sub(r'\1', text)
        return text
    except Exception:
        return ''

def try_load_json(sj: str) -> Union[dict, list]:
    """I'd basically trust the LLM here, they're far better than the earlier ones."""
    try:
        try:
            clean_sj = (ReUtils.re_search_answer_json.search(sj))[1]
        except Exception:
            clean_sj = sj.strip()
        j = json.loads(clean_sj)
        return j
    except Exception:
        return {}

def try_getattr(o, *names) -> Optional[any]:
    """Just for convenience."""
    res = None
    for name in names:
        res = getattr(o, name, None)
        if res:
            break
    return res

def beautify_time(dt: datetime.time, target_lang: Literal['zh', 'en', 'auto'] = 'zh', include_adj = True):
    """
    Beautifies current time. No date.

    - dt: datetime object, time should be enough
    - target_lang: you know, effectiveless if not include_adj
    - include_adj: include adjective, like dawn or morning or what
    """
    _Bt = BilingualText

    match time:
        case time if time.hour < 4:
            time_range = _Bt('半夜', ' at midnight')
        case time if 4 <= time.hour < 6:
            time_range = _Bt('凌晨', ' before dawn')
        case time if 6 <= time.hour < 8:
            time_range = _Bt('早上', ' at dawn')
        case time if 8 <= time.hour < 11:
            time_range = _Bt('上午', ' in morning')
        case time if 11 <= time.hour < 13:
            time_range = _Bt('中午', ' at noon')
        case time if 13 <= time.hour < 18:
            time_range = _Bt('下午', ' in afternoon')
        case time if 18 <= time.hour < 23:
            time_range = _Bt('晚上', ' at night')
        case time if 23 <= time.hour:
            time_range = _Bt('深夜', ' at midnight')

    if include_adj:
        time_friendly = f"{time_range.zh}{time:%H:%M:%S}" if target_lang == 'zh' else f"{time:%H:%M:%S}{time_range.en}"
    else:
        time_friendly = f"{time:%H:%M:%S}"

    return time_friendly

def beautify_date(dt: datetime.date, target_lang: Literal['zh', 'en', 'auto'] = 'zh', hemisphere: Literal['N', 'S'] = 'N', include_adj = True):
    """
    Beautifies current date. No time.
    
    - dt: datetime object, date should be enough
    - target_lang: you know
    - hemisphere: it affects season, effectiveless if not include_adj
    - include_adj: include adjective, like spring or Monday or what
    """
    _Bt = BilingualText

    sp = _Bt("春季", "spring")
    su = _Bt("夏季", "summer")
    au = _Bt("秋季", "autumn")
    wi = _Bt("冬季", "winter")

    if hemisphere == 'S':
        match dt.month:
            case m if 3 <= m < 6:
                season = au
            case m if 6 <= m < 9:
                season = wi
            case m if 9 <= m < 12:
                season = sp
            case _:
                season = su
        sh = _Bt("(南半球)", "(South hemisphere)")
    else:
        match m:
            case m if 3 <= m < 6:
                season = sp
            case m if 6 <= m < 9:
                season = su
            case m if 9 <= m < 12:
                season = au
            case _:
                season = wi
        sh = ''

    season += sh

    weeklist = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_zh = weeklist[dt.weekday()]

    if include_adj:
        date_friendly = f"{dt.year}年{season.zh}{dt.month}月{dt.day}日, {weekday_zh}" if target_lang == 'zh' else f"{dt:%d %B, %A, %Y} {season.en}"
    else:
        date_friendly = f"{dt.year}年{dt.month}月{dt.day}日" if target_lang == 'zh' else f"{dt:%d %B, %Y}"

    return date_friendly

async def hash_sha256(str) -> str:
    """Get SHA256 for a string."""
    def hash_sync(str):
        return hashlib.new('sha256', str).hexdigest()
    return await asyncio.to_thread(hash_sync, str)

def is_mcore_vl():
    """If mcore is same model with mvista."""
    return bool(G.A.MCORE_ADDR == G.A.MVISTA_ADDR and G.A.MCORE_CHOICE == G.A.MVISTA_CHOICE)

def is_rag_enabled():
    """If this server instance could utilize RAG."""
    return bool(G.A.EMBEDDING_ADDR and G.A.MILVUS_ADDR)

def to_str(obj: str | BilingualText, target_lang: Literal['zh', 'en', 'auto']='zh'):
    """Call to_str if bt, else as-is."""
    if isinstance(obj, BilingualText):
        return obj.to_str(target_lang)
    else:
        return obj

def sysstruct() -> Literal['Windows', 'Linux']:
    sysstruct = platform.system()
    assert sysstruct in ['Windows', 'Linux'], 'Your system not supported'
    return sysstruct

if __name__ == "__main__":
    async def test():
        from maica import init
        init()
        res = await dld_json(f"https://zh.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch=incategory:各时期火山事件&srnamespace=14&srlimit=250&sroffset=0&srprop=", True)
        print(res)

    asyncio.run(test())