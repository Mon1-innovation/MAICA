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

from maica import maica_ws, maica_http, common_schedule
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

    def printer(*args, **kwargs):
        nonlocal silent
        if not silent:
            sync_messenger(*args, **kwargs)

    def init_parser():
        parser = argparse.ArgumentParser(description="Start MAICA Illuminator deployment")
        parser.add_argument('-e', '--envdir', help='Include external env file for running deployment, specify every time')
        parser.add_argument('-t', '--templates', choices=['print', 'create'], nargs='?', const='print', help='Print config templates or create them in current directory')
        return parser
    
    parser = init_parser()
    args = parser.parse_args()
    envdir = envdir or args.envdir
    templates = args.templates

    def dest_env(envdir, extra_envdir):
        if envdir:
            realpath = os.path.abspath(envdir)
            if not os.path.isfile(realpath):
                printer(info=f'envdir {realpath} is not a file, trying {os.path.join(realpath, ".env")}...', type=MsgType.WARN)
                realpath = os.path.join(realpath, '.env')
                if not os.path.isfile(realpath):
                    raise Exception('designated env file not exist')
            printer(info=f'Loading env file {realpath}...', type=MsgType.DEBUG)
            load_dotenv(dotenv_path=realpath)

            if extra_envdir:
                for edir in extra_envdir:
                    realpath = os.path.abspath(edir)
                    if os.path.isfile(realpath):
                        printer(info=f'Loading extra env file {realpath}...', type=MsgType.DEBUG)
                        load_dotenv(dotenv_path=realpath)

        else:
            realpath = get_inner_path('.env')
            printer(info=f'No env file designated, trying to load {realpath}...', type=MsgType.DEBUG)
            if os.path.isfile(realpath):
                load_dotenv(dotenv_path=realpath)
            else:
                printer(info=f'{realpath} is not a file, skipping real env file...', type=MsgType.WARN)
        
        realpath = get_inner_path('env_example')
        printer(info=f'Loading env example {realpath} to guarantee basic functions...', type=MsgType.DEBUG)
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
        exit(0)

    def create_templates():
        env_c = get_templates()
        env_p = os.path.abspath('./.env')
        if os.path.exists(env_p):
            printer(info=f'Config {env_p} already exists, skipping creation...', type=MsgType.WARN)
        else:
            with open(env_p, 'w', encoding='utf-8') as env_f:
                printer(info=f'Generating {env_p}...', type=MsgType.DEBUG)
                env_f.write(env_c)

        printer(info='Creation succeeded, edit them yourself and then start with "maica -c .env"', type=MsgType.INFO)
        exit(0)

    if kwargs:
        for k, v in kwargs.items():
            os.environ[k] = v
        printer(info=f'Added {len(kwargs)} vars to environ.', type=MsgType.DEBUG)

    if not initialized:
        try:
            if templates:
                print_templates() if templates == 'print' else create_templates()
            dest_env(envdir, extra_envdir)
            pkg_init_maica()
            initialized = True
        except Exception as e:
            printer(info=f'Error: {str(e)}, quitting...', type=MsgType.ERROR)
            exit(1)

def check_basic_init():
    """We run this only if called to serve. No env is basically not a problem for working as module."""
    if load_env('IS_REAL_ENV') == '1':
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

def check_init():
    if not check_marking():
        generate_rsa_keys()
        asyncio.run(create_tables())
        create_marking()
        sync_messenger(info="MAICA Illuminator initiation finished", type=MsgType.PRIM_SYS)
    else:
        sync_messenger(info="Initiated marking detected, skipping initiation", type=MsgType.DEBUG)

async def start_all():
    if load_env('DB_ADDR') == 'sqlite':
        await messenger(info='\nMAICA using SQLite database detected\nWhile MAICA Illuminator is fully compatible with SQLite, it can be a significant drawback of performance under heavy workload\nIf this is a public service instance, it\'s strongly recommended to use MySQL/MariaDB instead', type=MsgType.DEBUG)
    if not load_env('PROXY_ADDR'):
        await messenger(info='\nInternet proxy absence detected\nMAICA Illuminator needs to access Google and Wikipedia for full functionalities, so you\'ll possibly need a proxy for those\nYou can ignore this message safely if you have direct access to those or have a global proxy set already', type=MsgType.DEBUG)
    if load_env('DEV_STATUS') != 'serving':
        await messenger(info='\nServer status not serving detected\nWith this announcement taking effect, standard clients will stop further communications with MAICA Illuminator respectively\nYou should set DEV_STATUS to \'serving\' whenever the instance is ready to serve', type=MsgType.DEBUG)
    if (load_env('MCORE_NODE') and load_env('MCORE_USER') and load_env('MCORE_PWD')) or (load_env('MFOCUS_NODE') and load_env('MFOCUS_USER') and load_env('MFOCUS_PWD')):
        await messenger(info='\nOne or more NVwatch nodes detected\nNVwatch of MAICA Illuminator will try to collect nvidia-smi outputs through SSH, which can fail the process if SSH not avaliable\nIf SSH of nodes are not accessable or not wanted to be used, delete X_NODE, X_USER, X_PWD accordingly', type=MsgType.DEBUG)

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
    check_basic_init()
    check_init()
    asyncio.run(start_all())

if __name__ == "__main__":
    full_start()