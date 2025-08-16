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
from typing import Optional
from dotenv import load_dotenv as __load_dotenv

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

class re_utils():
    re_sub_password_spoiler = re.compile(rf'"password"\s*:\s*"(.*?)"')

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

async def common_context_handler(websocket=None, status='', info='', code='0', traceray_id='', error: Optional[CommonMaicaError]=None, prefix='', type='', color='', add_time=True, no_print=False) -> None:
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

async def get_json(url) -> json:
    """Get JSON context from an endpoint."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
    try:
        for tries in range(0, 3):
            try:
                client = httpx.AsyncClient(proxy=load_env("PROXY_ADDR"))
                res = (await client.get(url, headers=headers)).json()
                break
            except:
                if tries < 2:
                    print('HTTP temporary failure')
                    await asyncio.sleep(0.5)
                else:
                    raise Exception('Http connection failure')
    except:
        raise Exception('Http connection failure')
    finally:
        await client.aclose()
    return res

async def hash_sha256(str) -> str:
    """Get SHA256 for a string."""
    def hash_sync(str):
        return hashlib.new('sha256', str).hexdigest()
    return await wrap_run_in_exc(None, hash_sync, str)

