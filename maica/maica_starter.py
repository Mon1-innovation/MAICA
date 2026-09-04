import os
import argparse
import asyncio
import json
import colorama
import signal
from typing import *
from dotenv import load_dotenv
from packaging.version import parse

try:
    import mtts
    from mtts.mtts_utils import locater as mtts_locater
    mtts_installed = True
except ImportError:
    mtts_installed = False

from maica import maica_ws, maica_http, common_schedule, silent as _silent
from maica.maica_utils import *
from maica.initializer import *
from maica.initializer import pkg_init_initializer
from maica.maica_http import pkg_init_maica_http
from maica.maica_utils import pkg_init_maica_utils
from maica.mtools import pkg_init_mtools

_CHAT_CONNS_LIST = [
    'vector_pool',
    'mcore_conn',
    'mfocus_conn',
    'mvista_conn',
    'mnerve_conn',
    'embedding_conn',
    'reranking_conn',
]
_TTS_CONNS_LIST = []

def pkg_init_maica():
    pkg_init_initializer()
    """Prio 0"""
    pkg_init_maica_utils()
    """Prio 1"""
    pkg_init_maica_http()
    pkg_init_mtools()
    make_folders = ["fs_storage/mv_img"]
    if mtts_installed:
        mtts.mtts_http.pkg_init_mtts_http()
        make_folders.append("fs_storage/mtts")
    for f in make_folders:
        fr = get_inner_path(f)
        os.makedirs(fr, exist_ok=True)

colorama.init(autoreset=True)
initialized = False
data_initialized = False
start_target: Literal['chat', 'tts', 'all'] = 'chat'
validate_only = False

def check_params(envdir: str=None, extra_envdir: list=None, silent=False, parse_cli=True, **kwargs):
    """This will only run once. Recalling will not take effect, except passing in extra kwargs."""
    global initialized, start_target, validate_only

    def init_parser():
        parser = argparse.ArgumentParser(description="Start MAICA Illuminator deployment or run self-maintenance functions")
        parser.add_argument('target', choices=['chat', 'tts', 'all'], nargs='?', default='chat', help='Start maica chat server or mtts server, default chat')
        parser.add_argument('-e', '--envdir', help='Include external env file for running deployment, specify every time')
        parser.add_argument('-s', '--silent', action="store_true", help='Run without logging (unrecommended for deployment)')
        parser.add_argument('--test', action="store_true", help='Run announcing test status')
        parser.add_argument(
            '--validate-config',
            action="store_true",
            help='Validate configuration without initializing databases or external connections',
        )
        excluse_1 = parser.add_mutually_exclusive_group()
        excluse_1.add_argument('-k', '--keys', choices=['path', 'export', 'import'], nargs='?', const='path', help='Get path of RSA keys, or export/import to/from current directory')
        excluse_1.add_argument('-d', '--databases', choices=['path', 'export', 'import'], nargs='?', const='path', help='Get path of databases, or export/import to/from current directory')
        excluse_1.add_argument('-t', '--templates', choices=['print', 'create'], nargs='?', const='print', help='Print config templates or create them in current directory')
        return parser
    
    parser = init_parser()
    args = parser.parse_args(None if parse_cli else [])
    start_target = args.target
    envdir = envdir or args.envdir
    silent = silent or args.silent
    test = args.test
    validate_only = args.validate_config
    operate_keys = args.keys
    operate_databases = args.databases
    operate_templates = args.templates

    if test:
        kwargs.update({"MAICA_DEV_STATUS": "testing"})

    _silent(silent)

    def dest_env(envdir: str=None, extra_envdir: list=None):
        """This part we load all static env vars."""
        if not envdir:
            realpath = get_inner_path('.env')
            sync_messenger(info=f'[maica-env] No env file designated, defaulting to {realpath}...', type=MsgType.DEBUG)
            envdir = realpath
            if not os.path.isfile(envdir):
                realpath = os.path.abspath('.env')
                sync_messenger(info=f'[maica-env] {envdir} is not a file, trying {realpath}...', type=MsgType.DEBUG)
        else:
            realpath = os.path.abspath(envdir)

        if os.path.isfile(realpath):
            sync_messenger(info=f'[maica-env] Loading env file {realpath}...', type=MsgType.DEBUG)
            load_dotenv(dotenv_path=realpath)
        else:
            sync_messenger(info=f'[maica-env] {realpath} is not a file, skipping real env file...', type=MsgType.WARN)

        if extra_envdir:
            for edir in extra_envdir:
                realpath = os.path.abspath(edir)
                if os.path.isfile(realpath):
                    sync_messenger(info=f'[maica-env] Loading extra env file {realpath}...', type=MsgType.DEBUG)
                    load_dotenv(dotenv_path=realpath)

        if mtts_installed:
            realpath = mtts_locater.get_inner_path('mtts_env_basis')
            sync_messenger(info=f'[maica-env] Loading mtts basis {realpath} to guarantee basic functions...', type=MsgType.DEBUG)
            if os.path.isfile(realpath):
                load_dotenv(dotenv_path=realpath)
            else:
                raise Exception('env basis lost')

        realpath = get_inner_path('env_basis')
        sync_messenger(info=f'[maica-env] Loading maica basis {realpath} to guarantee basic functions...', type=MsgType.DEBUG)
        if os.path.isfile(realpath):
            load_dotenv(dotenv_path=realpath)
        else:
            raise Exception('env basis lost')

    def get_templates():
        with open(get_inner_path('env_basis'), 'r', encoding='utf-8') as env_e:
            env_c = env_e.readlines()
        line_num = 0
        first_block_ends = False
        for line in env_c:
            line_num += 1
            # So we can add a placeholding mark each line, and it still considers it one codeblock
            if len(line) <= 1:
                first_block_ends = True
            if first_block_ends and len(line) > 1:
                break
        env_c = env_c[line_num - 1:]

        # These could change with updates and normally not necessary to customize
        # So we should comment them out by default to prevent neutualizing new feats
        mute_by_default = (
            'MAICA_PROMPT_',
        )
        for index, line in enumerate(env_c):
            for m in mute_by_default:
                if line.startswith(m):
                    env_c[index] = "#" + line

        env_c = ''.join(env_c)
        return env_c
    
    def separate_line(title: str):
        try:
            terminal_width = os.get_terminal_size().columns
        except OSError:
            terminal_width = 40
        line = title.center(terminal_width, '/')
        return line
    
    def print_templates():
        env_c = get_templates()
        print(colorama.Fore.BLUE + separate_line('Begin .env template'))
        print(env_c)
        print(colorama.Fore.BLUE + separate_line('End .env template'))

    def print_path(*files: list, common: str="keys"):
        print(colorama.Fore.BLUE + separate_line(f'Begin {common} paths'))
        for file in files:
            print(get_inner_path(file))
        print(colorama.Fore.BLUE + separate_line(f'End {common} paths'))

    def create_templates():
        env_c = get_templates()
        env_p = os.path.abspath('./.env')
        if os.path.exists(env_p):
            sync_messenger(info=f'[maica-cli] Config {env_p} already exists, skipping creation...', type=MsgType.WARN)
        else:
            with open(env_p, 'w', encoding='utf-8') as env_f:
                sync_messenger(info=f'[maica-cli] Generating {env_p}...', type=MsgType.DEBUG)
                env_f.write(env_c)

        sync_messenger(info='[maica-cli] Creation succeeded, edit it and then start with "maica -e .env"', type=MsgType.LOG)

    if kwargs:
        # Load extra env vars
        for k, v in kwargs.items():
            os.environ[k] = v
        sync_messenger(info=f'[maica-env] Added {len(kwargs)} vars to environ.', type=MsgType.DEBUG)

    if not initialized:
        try:
            if operate_keys:
                match operate_keys:
                    case 'path':
                        print_path('pub.key', 'prv.key')
                    case 'export':
                        export_keys('.')
                    case 'import':
                        import_keys('.')
                exit()

            if operate_templates:
                print_templates() if operate_templates == 'print' else create_templates()
                exit()

            dest_env(envdir, extra_envdir)

            if operate_databases:
                match operate_databases:
                    case 'path':
                        if load_env('MAICA_DB_ADDR') == "sqlite":
                            print_path(load_env('MAICA_AUTH_DB'), load_env('MAICA_DATA_DB'), common='databases')
                        else:
                            sync_messenger(info='[maica-cli] MAICA using served databases!', type=MsgType.WARN)
                    case _:
                        sync_messenger(info='\n[maica-cli] Function yet not supported, do it manually.\nNever ask why we made this.', type=MsgType.LOG)
                exit()

            initialized = True
        except Exception as e:
            sync_messenger(info=f'[maica-init] Error: {str(e)}, quitting...', type=MsgType.ERROR)
            if parse_cli:
                raise SystemExit(1) from e
            raise

def check_data_init(exit_on_unconfigured=True):
    global initialized, data_initialized
    if data_initialized:
        return
    if not int(load_env('MAICA_IS_REAL_ENV')):
        print('''\
No real env detected, is this workflow?
If it is, at least the imports and grammar are good if you see this.
If not:
    If you're running MAICA for deployment, pass in "--envdir path/to/.env".
    If you're developing with MAICA as dependency, call maica.init(envdir='path/to/.env') after import.
    If you really want to use without manual configuration, call maica.init(ignore_envc=True) after import.
    Or, you can manually set the necessary env vars.
Quitting...\
'''
        )
        # Allow a library caller to correct the configuration and retry init().
        initialized = False
        if exit_on_unconfigured:
            raise SystemExit(0)
        raise RuntimeError("MAICA requires a configured environment")

    missing = [
        key
        for key in ("MAICA_DB_ADDR", "MAICA_AUTH_DB", "MAICA_DATA_DB")
        if not load_env(key)
    ]
    if missing:
        initialized = False
        raise RuntimeError(f"Missing required database settings: {', '.join(missing)}")
    if (
        load_env("MAICA_DB_ADDR") == "sqlite"
        and os.path.abspath(load_env("MAICA_AUTH_DB"))
        == os.path.abspath(load_env("MAICA_DATA_DB"))
    ):
        initialized = False
        raise RuntimeError("MAICA_AUTH_DB and MAICA_DATA_DB must be different SQLite files")

    try:
        if (
            int(load_env("MAICA_F2B_COUNT")) <= 0
            or float(load_env("MAICA_F2B_TIME")) < 0
            or float(load_env("MAICA_AUTH_TIMEOUT")) <= 0
        ):
            raise ValueError
    except (TypeError, ValueError) as exc:
        initialized = False
        raise RuntimeError(
            "MAICA_F2B_COUNT and MAICA_AUTH_TIMEOUT must be positive, and MAICA_F2B_TIME non-negative"
        ) from exc

    last_version = check_marking()
    is_fresh = parse(last_version) <= parse("1.0.000")
    if is_fresh:
        generate_rsa_keys()
        pkg_init_maica()

        async def initialize_database():
            try:
                await create_tables()
                return await migrate_async(last_version)
            finally:
                # Keep table creation and migrations on one loop, then make
                # the global engines safe for the runtime loop to reuse.
                await dispose_database_engines()

        migrated = asyncio.run(initialize_database())

        sync_messenger(info="[maica-init] MAICA Illuminator initialization finished", type=MsgType.PRIM_SYS)
    else:
        pkg_init_maica()
        sync_messenger(info="[maica-init] Initiated marking detected, checking migrations...", type=MsgType.DEBUG)
        migrated = migrate(last_version)
    if is_fresh or migrated:
        create_marking()
    data_initialized = True


def validate_config():
    """Validate deterministic configuration syntax without external I/O."""
    from maica.maica_utils.ws_config import _parse_vision_host_rules

    errors = []

    def value(key):
        return load_env(f"MAICA_{key}")

    for key in ("DB_ADDR", "AUTH_DB", "DATA_DB"):
        if not value(key):
            errors.append(f"MAICA_{key} is required")
    if start_target != "tts":
        for key in ("MCORE_ADDR", "MFOCUS_ADDR"):
            if not value(key):
                errors.append(f"MAICA_{key} is required for the {start_target} target")

    if (
        value("DB_ADDR") == "sqlite"
        and value("AUTH_DB")
        and value("DATA_DB")
        and os.path.abspath(value("AUTH_DB")) == os.path.abspath(value("DATA_DB"))
    ):
        errors.append("MAICA_AUTH_DB and MAICA_DATA_DB must be different SQLite files")

    binary_keys = (
        "IS_REAL_ENV", "CALC_TOKENS", "ALT_TOOLCALL", "BASIC_MFOCUS",
        "FULL_RESTFUL", "KICK_STALE_CONNS",
        "RESPONSES_SERP", "NO_SEND_ERROR", "MCORE_GENERIC",
        "DEBUG_WARNS", "WRITE_NVW", "NVW_INSECURE_SSH", "TRUST_XFF",
    )
    for key in binary_keys:
        if value(key) not in {"0", "1"}:
            errors.append(f"MAICA_{key} must be 0 or 1")
    if value("IS_REAL_ENV") != "1":
        errors.append("MAICA_IS_REAL_ENV must be 1 for deployment")

    integer_ranges = {
        "WS_PORT": (1, 65535),
        "HTTP_PORT": (1, 65535),
        "OPENAI_TIMEOUT": (0, None),
        "EMBEDDING_DIMS": (1, None),
        "F2B_COUNT": (1, None),
        "KEEP_MVISTA": (0, None),
        "GC_SESSIONS": (0, None),
        "ROTATE_MSCACHE": (0, None),
        "ROTATE_MVISTA": (0, None),
        "ROTATE_VECTOR": (0, None),
        "SESSION_MAX_LENGTH": (1, None),
        "CENSOR_MSPIRE": (0, None),
        "CENSOR_QUERY": (0, None),
    }
    for key, (minimum, maximum) in integer_ranges.items():
        try:
            parsed = int(value(key))
            if parsed < minimum or (maximum is not None and parsed > maximum):
                raise ValueError
        except (TypeError, ValueError):
            expected = f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
            errors.append(f"MAICA_{key} must be an integer {expected}")

    for key, minimum, inclusive in (
        ("F2B_TIME", 0.0, True),
        ("AUTH_TIMEOUT", 0.0, False),
    ):
        try:
            parsed = float(value(key))
            if parsed < minimum or (parsed == minimum and not inclusive):
                raise ValueError
        except (TypeError, ValueError):
            operator = ">=" if inclusive else ">"
            errors.append(f"MAICA_{key} must be a number {operator} {minimum:g}")

    for key in (
        "MCORE_EXTRA", "MFOCUS_EXTRA", "MVISTA_EXTRA", "MNERVE_EXTRA",
        "EMBEDDING_EXTRA", "RERANKING_EXTRA", "TP_APIS", "SERVERS_LIST",
    ):
        try:
            parsed = json.loads(value(key))
            if not isinstance(parsed, dict):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"MAICA_{key} must be a JSON object")

    try:
        _parse_vision_host_rules(value("MVISTA_TRUSTED"))
    except ValueError as exc:
        errors.append(str(exc))

    try:
        parse_tos_ids(value("TOS_IDS"))
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        raise RuntimeError("Invalid configuration:\n- " + "\n- ".join(errors))

def check_warns():
    if load_env('MAICA_DB_ADDR') == 'sqlite':
        sync_messenger(info='\nMAICA using SQLite database detected\nWhile MAICA Illuminator is fully compatible with SQLite, it can be a significant drawback of performance under heavy workload\nIf this is a public service instance, it\'s strongly recommended to use MySQL/MariaDB instead', type=MsgType.DEBUG)
    if not load_env('MAICA_PROXY_ADDR'):
        sync_messenger(info='\nInternet proxy absence detected\nMAICA Illuminator needs to access Google and Wikipedia for full functionalities, so you\'ll possibly need a proxy for those\nYou can ignore this message safely if you have direct access to those or have a global proxy set already', type=MsgType.DEBUG)
    if load_env('MAICA_DEV_STATUS') != 'serving':
        sync_messenger(info='\nServer status not serving detected\nWith this announcement taking effect, standard clients will stop further communications with MAICA Illuminator respectively\nYou should set DEV_STATUS to \'serving\' whenever the instance is ready to serve', type=MsgType.DEBUG)
    if (load_env('MAICA_MCORE_NODE') and load_env('MAICA_MCORE_USER') and load_env('MAICA_MCORE_PWD')) or (load_env('MAICA_MFOCUS_NODE') and load_env('MAICA_MFOCUS_USER') and load_env('MAICA_MFOCUS_PWD')):
        sync_messenger(info='\nOne or more NVwatch nodes detected\nNVwatch of MAICA Illuminator will try to collect nvidia-smi outputs through SSH, which can fail the process if SSH not avaliable\nIf SSH of nodes are not accessable or not wanted to be used, delete X_NODE, X_USER, X_PWD accordingly', type=MsgType.DEBUG)

async def start_all(
    start_target: Literal['chat', 'tts', 'all']='chat',
    shutdown_trigger=None,
):
    if start_target not in {'chat', 'tts', 'all'}:
        raise ValueError(f"Unknown start target: {start_target}")

    root_csc_items = []
    try:
        connection_names = _CHAT_CONNS_LIST if start_target != 'tts' else _TTS_CONNS_LIST
        root_csc_items = await _create_root_connections(connection_names)
        root_csc_kwargs = dict(zip(connection_names, root_csc_items))

        if start_target == 'chat':
            await maica_start_all(**root_csc_kwargs, shutdown_trigger=shutdown_trigger)
        elif start_target == 'tts':
            await mtts_start_all(**root_csc_kwargs)
        else:
            await _wait_for_first(
                [
                    asyncio.create_task(
                        maica_start_all(
                            **root_csc_kwargs,
                            shutdown_trigger=shutdown_trigger,
                        )
                    ),
                    asyncio.create_task(mtts_start_all(**root_csc_kwargs)),
                ],
            )
    finally:
        sync_messenger(info="Doing final connection cleanup...", type=MsgType.DEBUG)
        await asyncio.gather(
            *(conn.close() for conn in root_csc_items if conn),
            return_exceptions=True,
        )

    sync_messenger(info="Everything done, bye", type=MsgType.DEBUG)


async def _create_root_connections(connection_names):
    tasks = [
        asyncio.create_task(getattr(ConnUtils, name)())
        for name in connection_names
    ]
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        connections = [
            task.result()
            for task in tasks
            if not task.cancelled() and task.exception() is None and task.result()
        ]
        await asyncio.gather(
            *(connection.close() for connection in connections),
            return_exceptions=True,
        )
        raise

    errors = [result for result in results if isinstance(result, BaseException)]
    if errors:
        connections = [
            result for result in results
            if result and not isinstance(result, BaseException)
        ]
        await asyncio.gather(
            *(connection.close() for connection in connections),
            return_exceptions=True,
        )
        raise errors[0]

    return results


async def _wait_for_first(tasks):
    """Wait until one service exits, then cancel and await every sibling."""
    done = set()
    pending = set(tasks)
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    # Propagate failures instead of turning a crashed server into a clean exit.
    await asyncio.gather(*done)

async def maica_start_all(shutdown_trigger=None, **kwargs):

    task_ws = asyncio.create_task(maica_ws.prepare_thread(**kwargs))
    task_http = asyncio.create_task(
        maica_http.prepare_thread(
            **kwargs,
            shutdown_trigger=shutdown_trigger,
        )
    )
    task_schedule = asyncio.create_task(common_schedule.prepare_thread(**kwargs, involve_chat=True, involve_tts=False))

    await _wait_for_first([task_ws, task_http, task_schedule])

async def mtts_start_all(**kwargs):

    if not mtts_installed:
        sync_messenger(info="Install with mi-mtts or .[mtts] to implement", type=MsgType.ERROR)
        return

    task_tts = asyncio.create_task(mtts.prepare_thread(**kwargs))
    task_schedule = asyncio.create_task(common_schedule.prepare_thread(**kwargs, involve_chat=False, involve_tts=True))

    await _wait_for_first([task_tts, task_schedule])


async def _start_with_sigterm(target):
    """Translate SIGTERM into task cancellation so every service can clean up."""
    loop = asyncio.get_running_loop()
    shutdown_requested = asyncio.Event()
    service_task = asyncio.create_task(
        start_all(target, shutdown_trigger=shutdown_requested.wait)
    )
    shutdown_task = asyncio.create_task(shutdown_requested.wait())
    loop_handler_installed = False
    previous_handler = None

    def request_shutdown():
        if not shutdown_requested.is_set():
            shutdown_requested.set()

    try:
        try:
            loop.add_signal_handler(signal.SIGTERM, request_shutdown)
            loop_handler_installed = True
        except (NotImplementedError, RuntimeError):
            # ProactorEventLoop on Windows doesn't implement add_signal_handler.
            try:
                previous_handler = signal.getsignal(signal.SIGTERM)
                signal.signal(
                    signal.SIGTERM,
                    lambda *_args: loop.call_soon_threadsafe(request_shutdown),
                )
            except (AttributeError, OSError, ValueError):
                previous_handler = None

        done, _ = await asyncio.wait(
            (service_task, shutdown_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if shutdown_task in done:
            sync_messenger(info="\n", type=MsgType.PLAIN)
            sync_messenger(info="SIGTERM received, shutting down services...", type=MsgType.PRIM_SYS)
            service_task.cancel()
        else:
            # Preserve failures when a service exits without a shutdown signal.
            await service_task
    finally:
        for task in (service_task, shutdown_task):
            if not task.done():
                task.cancel()

        await asyncio.gather(service_task, shutdown_task, return_exceptions=True)

        if loop_handler_installed:
            loop.remove_signal_handler(signal.SIGTERM)
            
        elif previous_handler is not None:
            signal.signal(signal.SIGTERM, previous_handler)

def full_start():
    check_params()
    if validate_only:
        validate_config()
        print("MAICA configuration is valid")
        return
    check_data_init()
    check_warns()
    asyncio.run(_start_with_sigterm(start_target))

if __name__ == "__main__":
    full_start()
