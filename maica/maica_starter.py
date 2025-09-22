import os
import sys
from pathlib import Path
from dotenv import load_dotenv
try:
    from maica import maica_ws
except Exception:
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

import asyncio
import argparse
import colorama

from maica import maica_ws, maica_http, common_schedule, silent as _silent
from maica.maica_utils import *
from maica.initializer import *

from maica.maica_http import pkg_init_maica_http
from maica.maica_nows import pkg_init_maica_nows
from maica.maica_utils import pkg_init_maica_utils
def pkg_init_maica():
    pkg_init_maica_http()
    pkg_init_maica_nows()
    pkg_init_maica_utils()

colorama.init(autoreset=True)
initialized = False

def check_params(envdir: str=None, extra_envdir: list=None, silent=False, **kwargs):
    """This will only run once. Recalling will not take effect, except passing in extra kwargs."""
    global initialized

    def init_parser():
        parser = argparse.ArgumentParser(description="Start MAICA Illuminator deployment or run self-maintenance functions")
        parser.add_argument('-e', '--envdir', help='Include external env file for running deployment, specify every time')
        parser.add_argument('-s', '--silent', action="store_true", help='Run without logging (unrecommended for deployment)')
        excluse_1 = parser.add_mutually_exclusive_group()
        excluse_1.add_argument('-k', '--keys', choices=['path', 'export', 'import'], nargs='?', const='path', help='Get path of RSA keys, or export/import to/from current directory')
        excluse_1.add_argument('-d', '--databases', choices=['path', 'export', 'import'], nargs='?', const='path', help='Get path of databases, or export/import to/from current directory')
        excluse_1.add_argument('-t', '--templates', choices=['print', 'create'], nargs='?', const='print', help='Print config templates or create them in current directory')
        return parser
    
    parser = init_parser()
    args = parser.parse_args()
    envdir = envdir or args.envdir
    silent = silent or args.silent
    operate_keys = args.keys
    operate_databases = args.databases
    operate_templates = args.templates

    _silent(silent)

    def dest_env(envdir: str=None, extra_envdir: list=None):
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

        realpath = get_inner_path('env_example')
        sync_messenger(info=f'[maica-env] Loading env example {realpath} to guarantee basic functions...', type=MsgType.DEBUG)
        if os.path.isfile(realpath):
            load_dotenv(dotenv_path=realpath)
        else:
            raise Exception('env template lost')

    def get_templates():
        with open(get_inner_path('env_example'), 'r', encoding='utf-8') as env_e:
            env_c = env_e.read()
        return env_c
    
    def separate_line(title: str):
        try:
            terminal_width = os.get_terminal_size().columns
        except:
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

        sync_messenger(info='[maica-cli] Creation succeeded, edit them yourself and then start with "maica -c .env"', type=MsgType.LOG)

    if kwargs:
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

            pkg_init_maica()
            initialized = True
        except Exception as e:
            sync_messenger(info=f'[maica-init] Error: {str(e)}, quitting...', type=MsgType.ERROR)
            exit(1)

def check_env_init():
    """We run this only if called to serve. No env is basically not a problem for working as module."""
    if load_env('MAICA_IS_REAL_ENV') == '1':
        return
    else:
        print('''No real env detected, is this workflow?
If it is, at least the imports and grammar are good if you see this.
If not:
    If you're running MAICA for deployment, pass in "--envdir path/to/.env".
    If you're developing with MAICA as dependency, call maica.init() after import.
    Or, you can manually set the necessary env vars.
Quitting...'''
              )
        quit(0)

def check_data_init():
    if not check_marking():
        generate_rsa_keys()
        asyncio.run(create_tables())
        create_marking()
        sync_messenger(info="MAICA Illuminator initialization finished", type=MsgType.PRIM_SYS)
    else:
        sync_messenger(info="Initiated marking detected, skipping initialization", type=MsgType.DEBUG)

def check_warns():
    if load_env('MAICA_DB_ADDR') == 'sqlite':
        sync_messenger(info='\nMAICA using SQLite database detected\nWhile MAICA Illuminator is fully compatible with SQLite, it can be a significant drawback of performance under heavy workload\nIf this is a public service instance, it\'s strongly recommended to use MySQL/MariaDB instead', type=MsgType.DEBUG)
    if not load_env('MAICA_PROXY_ADDR'):
        sync_messenger(info='\nInternet proxy absence detected\nMAICA Illuminator needs to access Google and Wikipedia for full functionalities, so you\'ll possibly need a proxy for those\nYou can ignore this message safely if you have direct access to those or have a global proxy set already', type=MsgType.DEBUG)
    if load_env('MAICA_DEV_STATUS') != 'serving':
        sync_messenger(info='\nServer status not serving detected\nWith this announcement taking effect, standard clients will stop further communications with MAICA Illuminator respectively\nYou should set DEV_STATUS to \'serving\' whenever the instance is ready to serve', type=MsgType.DEBUG)
    if (load_env('MAICA_MCORE_NODE') and load_env('MAICA_MCORE_USER') and load_env('MAICA_MCORE_PWD')) or (load_env('MAICA_MFOCUS_NODE') and load_env('MAICA_MFOCUS_USER') and load_env('MAICA_MFOCUS_PWD')):
        sync_messenger(info='\nOne or more NVwatch nodes detected\nNVwatch of MAICA Illuminator will try to collect nvidia-smi outputs through SSH, which can fail the process if SSH not avaliable\nIf SSH of nodes are not accessable or not wanted to be used, delete X_NODE, X_USER, X_PWD accordingly', type=MsgType.DEBUG)

async def start_all():

    auth_pool, maica_pool = await asyncio.gather(ConnUtils.auth_pool(), ConnUtils.maica_pool())
    kwargs = {"auth_pool": auth_pool, "maica_pool": maica_pool}
    task_ws = asyncio.create_task(maica_ws.prepare_thread(**kwargs))
    task_http = asyncio.create_task(maica_http.prepare_thread(**kwargs))
    task_schedule = asyncio.create_task(common_schedule.schedule_rotate_cache(**kwargs))

    res = await asyncio.wait([
        task_ws,
        task_http,
        task_schedule,
    ], return_when=asyncio.FIRST_COMPLETED)
    await messenger(info="First quit collected, quitting other tasks...", type=MsgType.DEBUG)
    for pending in res[1]:
        pending.cancel()
        await pending
    await messenger(info="All quits collected, doing final cleanup...", type=MsgType.DEBUG)
    await asyncio.gather(auth_pool.close(), maica_pool.close(), return_exceptions=True)
    await messenger(info="Everything done, bye", type=MsgType.DEBUG)
    quit()

def full_start():
    check_params()
    check_env_init()
    check_data_init()
    check_warns()
    asyncio.run(start_all())

if __name__ == "__main__":
    full_start()