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
from typing import *
from dotenv import load_dotenv as __load_dotenv
"""Import layer 1"""

colorama.init(autoreset=True)

class CommonMaicaException(Exception):
    """This is a common MAICA exception."""
    def __init__(self, message=None, error_code=None):
        super().__init__(message)
        self.message, self.error_code = message, error_code
    def __str__(self):
        return str(self.error_code) + " - " + super().__str__()
    def is_critical(self):
        return int(self.error_code) >= 500
    def is_breaking(self):
        return True
    
class CommonMaicaError(CommonMaicaException):
    """This is a common MAICA error."""
    def __init__(self, message=None, error_code='500'):
        super().__init__(message, error_code)
    
class CommonMaicaWarning(CommonMaicaException):
    """This is a common MAICA warning."""
    def __init__(self, message=None, error_code='400'):
        super().__init__(message, error_code)
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

class FSCPlain():
    """Loop importing prevention"""
    class RealtimeSocketsContainer():
        """For no-setting usage."""
        def __init__(self, websocket, traceray_id):
            self.websocket, self.traceray_id = websocket, traceray_id
    
    def __init__(self, websocket=None, traceray_id='', maica_settings=None, auth_pool=None, maica_pool=None, mcore_conn=None, mfocus_conn=None):
        self.rsc = self.RealtimeSocketsContainer(websocket, traceray_id)
        self.maica_settings = maica_settings() if not maica_settings else maica_settings
        self.auth_pool = auth_pool
        self.maica_pool = maica_pool
        self.mcore_conn = mcore_conn
        self.mfocus_conn = mfocus_conn

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

def default(exp, default, default_list: list=[None]) -> any:
    """If exp is in default list(normally None), use default."""
    return default if exp in default_list else exp

def wrap_ws_formatter(code, status, content, type, deformation=False, **kwargs) -> str:
    output = {
        "code" : code,
        "status" : status,
        "content" : content,
        "type" : type,
        "time_ms" : int(round(time.time() * 1000))
    }
    output.update(kwargs)
    return json.dumps(output, ensure_ascii=deformation)

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

async def messenger(websocket=None, status='', info='', code='0', traceray_id='', error: Optional[CommonMaicaError]=None, prefix='', type='', color='', add_time=True, no_print=False) -> None:
    """It could handle most log printing, websocket sending and exception raising jobs pretty automatically."""
    if error:
        info = error.message if not info else info; code = error.error_code if code == "0" else code
    if type and not prefix and not 100 <= int(code) < 200:
        prefix = type.capitalize()

    match int(code):
        case 0:
            prefix_t = "Log"; type_t = "log"
        case x if 100 <= x < 200:
            prefix_t = ""; type_t = "carriage"
        case x if 200 <= x < 300:
            prefix_t = "Debug"; type_t = "debug"
        case x if 300 <= x < 400 or 1000 <= x:
            prefix_t = "Info"; type_t = "info"
        case x if 400 <= x < 500:
            prefix_t = "Warn"; type_t = "warn"
        case x if 500 <= x < 1000:
            prefix_t = "Error"; type_t = "error"

    prefix = prefix_t if not prefix else prefix; type = type_t if not type else type
    if type and not prefix and not 100 <= int(code) < 200:
        prefix = type.capitalize()
    # This is especially for streaming output
    if not prefix and type == "carriage":
        msg_print = msg_send = info
    elif type == "plain":
        msg_print = msg_send = info
    else:
        msg_print = f"<WS_{prefix}>"; msg_print += f"-[{time.strftime('%Y-%m-%d %H:%M:%S')}]" if add_time else ''; msg_print += f"-[{str(code)}]" if code else ''; msg_print += f": {str(info)}"; msg_print += f"; traceray ID {traceray_id}" if traceray_id else ''
        msg_send = f"{str(info)}"; msg_send += f" -- your traceray ID is {traceray_id}" if traceray_id else ''
    if websocket:
        await websocket.send(wrap_ws_formatter(code=code, status=status, content=msg_send, type=type))
    frametrack_list = ["error"]; frametrack_list.append("warn")
    if type in frametrack_list:
        stack = inspect.stack()
        stack.pop(0)
    if not no_print:
        match type:
            case "plain":
                print((color or '') + msg_print, end='')
            case "carriage":
                if not prefix:
                    print((color or colorama.Fore.LIGHTGREEN_EX) + msg_print, end='', flush=True)
                else:
                    print((color or colorama.Fore.GREEN) + msg_print)
            case "debug":
                if load_env("PRINT_VERBOSE") == "1":
                    print((color or colorama.Fore.LIGHTBLACK_EX) + msg_print)
            case "info":
                print((color or '') + msg_print)
            case "log":
                print((color or colorama.Fore.BLUE) + msg_print)
            case "warn":
                if load_env("PRINT_VERBOSE") == "1" and prefix.lower() in frametrack_list:
                    print(color or colorama.Fore.YELLOW + f"WARN happened when executing {stack[0].function} at {stack[0].filename}#{stack[0].lineno}:")
                print((color or colorama.Fore.LIGHTYELLOW_EX) + msg_print)
            case "error":
                if load_env("PRINT_VERBOSE") == "1" and prefix.lower() in frametrack_list:
                    print((color or colorama.Fore.RED) + f"ERROR happened when executing {stack[0].function} at {stack[0].filename}#{stack[0].lineno}:")
                print((color or colorama.Fore.LIGHTRED_EX) + msg_print)
    if error:
        raise error
    return

def load_env(key) -> str:
    """Load something from .env."""
    __load_dotenv()
    result = os.getenv(key)
    if not result:
        raise ValueError("Environment variables are missing.")
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
                client = httpx.AsyncClient(proxy=load_env("PROXY_ADDR"))
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

def try_load_json(j: str) -> dict:
    """I'd basically trust the LLM here, they're far better than the earlier ones."""
    if not j or j.lower() in ['none', 'false']:
        return {}
    try:
        return json.loads(j)
    except Exception:
        return {}

async def hash_sha256(str) -> str:
    """Get SHA256 for a string."""
    def hash_sync(str):
        return hashlib.new('sha256', str).hexdigest()
    return await wrap_run_in_exc(None, hash_sync, str)

