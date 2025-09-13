import os
import sys
from pathlib import Path
try:
    from maica import maica_ws
except Exception:
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

import asyncio

from maica import maica_ws, maica_http, common_schedule
from maica.maica_utils import *
from maica.initializer import *

def check_basic_init():
    if load_env('IS_REAL_ENV') != '0':
        return
    else:
        print('''No env detected, is this workflow?
If it is, at least the imports and grammar are good if you see this.
If not, please follow the documents and finish configures before running.
Quitting...'''
              )
        quit(0)

def check_init():
    if not check_marking():
        generate_rsa_keys()
        asyncio.run(create_tables())
        create_marking()
        asyncio.run(messenger(info="MAICA Illuminator initiation finished", type=MsgType.PRIM_SYS))
    else:
        asyncio.run(messenger(info="Initiated marking detected, skipping initiation", type=MsgType.DEBUG))

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

    await asyncio.wait([
        task_ws,
        task_http,
        task_schedule,
    ], return_when=asyncio.FIRST_COMPLETED)

    await messenger(info="All quits collected, doing final cleanup...", type=MsgType.DEBUG)
    await asyncio.gather(auth_pool.close(), maica_pool.close(), return_exceptions=True)
    quit()

def full_start():
    check_basic_init()
    check_init()
    asyncio.run(start_all())

if __name__ == "__main__":
    full_start()