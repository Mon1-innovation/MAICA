"""
Some annoying migration stuff here.
"""
import asyncio
import importlib
from typing import *
from packaging.version import parse
from collections.abc import Callable
from maica.maica_utils import *
from maica.initializer import create_marking

available_list: list[tuple[str, Callable]]

def pkg_init_migrations():
    global available_list
    available_list = []

    for prio in range(0, 100):
        modname = f".migration_{prio}"
        try:
            mig_module = importlib.import_module(modname, "maica.initializer.migrations")
            mig_v = parse(mig_module.upper_version); migrate = mig_module.migrate
            available_list.append((mig_v, migrate))
        except:...

def migrate(version):
    migrated = False

    last_version_parsed = parse(version)
    curr_version_parsed = parse(load_env('MAICA_CURR_VERSION'))
    for mig_item in available_list:
        if curr_version_parsed >= mig_item[0] > last_version_parsed:
            try:
                sync_messenger(info=f'Running migration upper-version {str(mig_item[0])}...', type=MsgType.DEBUG)
                asyncio.run(mig_item[1]())
                sync_messenger(info=f'Finished migration upper-version {str(mig_item[0])}', type=MsgType.DEBUG)
                migrated = True
            except CommonMaicaException as ce:
                if ce.is_critical:
                    raise ce
                else:
                    sync_messenger(error=ce, no_raise=True)
                    migrated = True

    return migrated
