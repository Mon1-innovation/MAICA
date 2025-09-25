import asyncio
import httpx
import functools
import hashlib
import os
import re
import json
import inspect
import colorama
import time
import datetime
import random
import traceback
from typing import *
from urllib.parse import urlparse
from .locater import *
"""Import layer 1"""

colorama.init(autoreset=True)
_silent = False

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
    def __init__(self, message=None, error_code='500', status='maica_unidentified_error', send=None, print=None):
        super().__init__(message, error_code, status, send, print)
    
class CommonMaicaWarning(CommonMaicaException):
    """This is a common MAICA warning."""
    def __init__(self, message=None, error_code='400', status='maica_unidentified_warning', send=None, print=None):
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

class MaicaConnectionWarning(CommonMaicaWarning):
    """This suggests the connection is not behaving normal."""

class MaicaInternetWarning(CommonMaicaWarning):
    """This suggests the backend request action is not behaving normal."""

class FscPlain():
    """Loop importing prevention."""
    class RealtimeSocketsContainer():
        """For no-setting usage."""
        def __init__(self, websocket=None, traceray_id=''):
            self.websocket, self.traceray_id = websocket, traceray_id
    
    def __init__(self, websocket=None, traceray_id='', maica_settings=None, auth_pool=None, maica_pool=None, mcore_conn=None, mfocus_conn=None):
        self.rsc = self.RealtimeSocketsContainer(websocket, traceray_id)
        self.maica_settings = maica_settings() if not maica_settings else maica_settings
        self.auth_pool = auth_pool
        self.maica_pool = maica_pool
        self.mcore_conn = mcore_conn
        self.mfocus_conn = mfocus_conn

class AsyncCreator():
    """Inherit this for async init."""
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

class ReUtils():
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
    re_findall_square_brackets = re.compile(r'\[(.*?)\]')
    re_sub_sqlite_escape = re.compile(r'%s')

class Decos():
    def escape_sqlite_expression(func):
        """Used to transform a MySQL expression to SQLite one."""
        @functools.wraps(func)
        def wrapper(self, expression, *args, **kwargs):
            expression_new = ReUtils.re_sub_sqlite_escape.sub('?', expression)
            return func(self, expression_new, *args, **kwargs)
        return wrapper

    def report_data_error(func):
        """Raises when the requested action cannot be done because of corrupted data."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not str(e):
                    e = 'Assertion'
                raise MaicaInputWarning(f'Acquired persistent not acceptable:{str(e)}', '405', 'maica_agent_persistent_bad')
        return wrapper

    def report_reading_error(func):
        """Raises when the requested variable cannot be read before assignment."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not str(e):
                    e = 'Assertion'
                raise MaicaInputError(f'Access before necessary assignment: {str(e)}', '500', 'maica_settings_read_rejected')
        return wrapper

    def report_limit_warning(func):
        """Raises when the input param coming from user is out of bound."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not str(e):
                    e = 'Assertion'
                raise MaicaInputWarning(f'Input param not acceptable: {str(e)}', '422', 'maica_settings_param_rejected')
        return wrapper

    def report_limit_error(func):
        """Raises when the input param coming from program is out of bound."""
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                assert not getattr(self, '_lock', None)
                return func(self, *args, **kwargs)
            except Exception as e:
                if not str(e):
                    e = 'Assertion'
                raise MaicaInputError(f'Input param not acceptable: {str(e)}', '500', 'maica_settings_param_rejected')
        return wrapper

def default(exp, default, default_list: list=[None]) -> any:
    """If exp is in default list(normally None), use default."""
    return default if exp in default_list else exp

def wrap_ws_formatter(code, status, content, type, deformation=False, **kwargs) -> str:
    if not isinstance(content, (str, list, dict, None)):
        content = str(content)
    output = {
        "code" : code,
        "status" : status,
        "content" : content,
        "type" : type,
        "timestamp" : time.time(),
    }
    output.update(kwargs)
    return json.dumps(output, ensure_ascii=deformation)

def ellipsis_str(input: any, limit=80) -> str:
    """It converts anything to str and ellipsis it."""
    text = str(input)
    if len(text) > limit:
        text = text[:limit] + '...'
    return text

def fuzzy_match(pattern: str, text):
    """Mostly used in agent things."""
    if pattern == text:
        return True
    
    # So they only compile once. Better than nothing
    compiled_expression: Optional[Pattern] = getattr(ReUtils, f're_match_{pattern}')
    if compiled_expression:
        return compiled_expression.match(text)
    else:
        expression = pattern.replace('_', r'.*')
        return re.match(expression, text, re.I | re.S)

def words_upper(text: str) -> str:
    """Overkill..."""
    def u_upper(c: re.Match):
        return f'{c[1]}{c[2].upper()}'
    return ReUtils.re_sub_capt_status.sub(u_upper, text)

async def sleep_forever() -> None:
    """Make a coroutine sleep to the end of the world."""
    future = asyncio.Future()
    await future

def alt_tools(tools: list) -> list:
    """If ALT_TOOLCALL"""
    match load_env('MAICA_ALT_TOOLCALL'):
        case '0':
            return tools
        case '1':
            new_tools = []
            for tool in tools:
                new_tools.append({})
                new_tools[-1]['function'] = tool
                new_tools[-1]['type'] = 'function'
            return new_tools

def maica_assert(condition, kwd='param'):
    """Normally used for input checkings."""
    if not condition:
        raise MaicaInputWarning(f"Illegal input {kwd} detected", '405', 'maica_input_param_bad')

def has_valid_content(text: Union[str, list, dict]):
    """If the LLM actually gave anything."""
    text = str(text)
    text_proc = text.lower().strip()
    if (not text_proc) or text_proc in ['false', 'null', 'none']:
        return False
    else:
        return True

def proceed_agent_response(text: str, is_json=False) -> Union[str, list, dict]:
    """Proceeds thinking/nothinking."""
    try:
        answer_post_think = (ReUtils.re_search_post_think.search(text))[1]
    except Exception:
        if has_valid_content(text):
            answer_post_think = text
        else:
            answer_post_think = None
    if answer_post_think and not ReUtils.re_search_answer_none.search(answer_post_think) and is_json:
        try:
            answer_fin = (ReUtils.re_search_answer_json.search(answer_post_think))[1]
            answer_fin_json = json.loads(answer_fin)
            return answer_fin_json
        except Exception:
            answer_fin = None
    else:
        answer_fin = answer_post_think
    return answer_fin

@overload
async def messenger(websocket=None, status='', info='', code='0', traceray_id='', error: Optional[CommonMaicaException]=None, prefix='', type='', color='', add_time=True, no_print=False, no_raise=False) -> None: ...

async def messenger(websocket=None, *args, **kwargs) -> None:
    """Together with websocket.send()."""
    ws_tuple = sync_messenger(*args, **kwargs)
    if websocket and ws_tuple:
        await websocket.send(wrap_ws_formatter(*ws_tuple))

def sync_messenger(status='', info='', code='0', traceray_id='', error: Optional[CommonMaicaException]=None, prefix='', type='', color='', add_time=True, no_print=False, no_raise=False) -> list:
    """It could handle most log printing and exception raising jobs pretty automatically."""
    try:
        term_v = os.get_terminal_size().columns
    except:
        term_v = 40
    rep2 = int(term_v / 2)
    rep1 = int(rep2 - 20)

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

    if type and not prefix and not 100 <= int(code) < 200:
        prefix = words_upper(type)

    # This is especially for streaming output
    if not prefix and type == "carriage":
        msg_print = str(info)
        msg_send = info

    elif type == "plain":
        msg_print = str(info)
        msg_send = info
        
    else:
        msg_print = f"<{prefix}>"
        msg_print = msg_print.ljust(10)
        msg_print += f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]" if add_time else ''; msg_print += f"-[{str(code)}]" if code else ''
        msg_print = msg_print.ljust(40)
        msg_print += f": {str(info)}" if not str(info).startswith('\n') else f"{'-=' * rep1}{str(info)}\n{'-=' * rep2}"
        msg_print += f"; traceray ID {traceray_id}" if traceray_id else ''
        msg_send = info
        if type == 'error' and load_env('MAICA_NO_SEND_ERROR') == '1':
            msg_send = "A critical exception happened serverside, contact administrator"
        if traceray_id and isinstance(info, str):
            msg_send += f" -- your traceray ID is {traceray_id}"

    frametrack_dict = {"error": 99}
    if not load_env('MAICA_PRINT_VERBOSE') == "0":
        frametrack_dict['warn'] = 0
    if type in frametrack_dict:
        stack = inspect.stack()
        stack.pop(0)

    if (not no_print) and (not _silent):
        match type:
            case "plain":
                print((color or '') + msg_print, end='')
            case "carriage":
                if 100 <= int(code) < 200:
                    print((color or colorama.Fore.LIGHTGREEN_EX) + msg_print, end='', flush=True)
                else:
                    print((color or colorama.Fore.LIGHTGREEN_EX) + msg_print)
            case "debug":
                if not load_env('MAICA_PRINT_VERBOSE') == "0":
                    print((color or colorama.Fore.LIGHTBLACK_EX) + msg_print)
            case "info":
                print((color or colorama.Fore.GREEN) + msg_print)
            case "log":
                print((color or colorama.Fore.BLUE) + msg_print)
            case "prim_log":
                print((color or colorama.Fore.LIGHTBLUE_EX) + msg_print)
            case "sys":
                print((color or colorama.Fore.MAGENTA) + msg_print)
            case "prim_sys":
                print((color or colorama.Fore.LIGHTMAGENTA_EX) + msg_print)
            case "recv":
                print((color or colorama.Fore.CYAN) + msg_print)
            case "prim_recv":
                print((color or colorama.Fore.LIGHTCYAN_EX) + msg_print)
            case "warn":
                if 'warn' in frametrack_dict:
                    for stack_layer in stack[frametrack_dict['warn']::-1]:
                        print(color or colorama.Fore.YELLOW + f"• WARN happened when executing {stack_layer.function} at {stack_layer.filename}#{stack_layer.lineno}:")
                print((color or colorama.Fore.LIGHTYELLOW_EX) + msg_print)
            case "error":
                if 'error' in frametrack_dict:
                    for stack_layer in stack[frametrack_dict['error']::-1]:
                        print((color or colorama.Fore.RED) + f"! ERROR happened when executing {stack_layer.function} at {stack_layer.filename}#{stack_layer.lineno}:")
                print((color or colorama.Fore.LIGHTRED_EX) + msg_print)
    if error and not no_raise:
        raise error
    if error and not error.send:
        return
    return code, status, msg_send, type

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

def limit_length(col: list, limit: int) -> list:
    return random.sample(col, limit) if limit < len(col) else col

async def get_json(url) -> json:
    """Get JSON context from an endpoint."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
    try:
        for tries in range(0, 3):
            try:
                client = httpx.AsyncClient(proxy=load_env('MAICA_PROXY_ADDR'))
                res = (await client.get(url, headers=headers)).json()
                break
            except Exception as e:
                if tries < 2:
                    print('HTTP temporary failure')
                    await asyncio.sleep(0.5)
                else:
                    raise MaicaInternetWarning(f'HTTP connection failure: {str(e)}', '408')
    except Exception as e:
        raise e
    finally:
        await client.aclose()
    return res

def get_host(url: str) -> bool:
    """Try to get hostname from url."""
    try:
        url_parsed = urlparse(url)
        return url_parsed.hostname
    except Exception:
        return False

def vali_url(url: str) -> bool:
    """urllib is dumb. It doesn't recognize ip addr so we make it brutal."""
    return '.' in url

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
    """Clean a text phrase, mostly for internet search."""
    text = text.strip()
    text = text.replace('\n', ' ')
    return text

def try_load_json(sj: str) -> dict:
    """I'd basically trust the LLM here, they're far better than the earlier ones."""
    if not has_valid_content(sj):
        return {}
    try:
        return json.loads(sj)
    except Exception:
        return {}

async def hash_sha256(str) -> str:
    """Get SHA256 for a string."""
    def hash_sync(str):
        return hashlib.new('sha256', str).hexdigest()
    return await wrap_run_in_exc(None, hash_sync, str)
