"""
Some annoying migration stuff here.
"""

from maica.maica_utils import *

from maica.initializer.migrations.base import get_migrations, migrate, migrate_async, available_list
from . import _activator

def pkg_init_migrations():
    global available_list
    available_list.extend(get_migrations())
    sync_messenger(info=f'[maica-mig] {len(available_list)} migrations found', type=MsgType.DEBUG)

__all__ = ['migrate', 'migrate_async']
