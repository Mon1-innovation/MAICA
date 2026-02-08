import asyncio
import os
from typing import *
from maica.maica_utils import *
from .base import register_migration

upper_version = "1.2.003"

async def migrate():

    auth_pool = await ConnUtils.auth_pool(ro=False)
    try:
        if auth_pool.db_type == 'mysql':
            result = await auth_pool.query_get("select count(*) from information_schema.columns where table_name = 'users' and column_name = 'suspended_until'")
            exist = result[0]
            if not exist:
                sync_messenger(info='Column does not exist, creating...', type=MsgType.DEBUG)
                await auth_pool.query_modify('alter table `users` add column `suspended_until` datetime DEFAULT NULL')
            else:
                sync_messenger(info='Column already exists', type=MsgType.DEBUG)
        else:
            result = await auth_pool.query_get(
                "SELECT name FROM pragma_table_info('users') WHERE name='suspended_until'"
            )
            if not result:
                sync_messenger(info='Column does not exist, creating...', type=MsgType.DEBUG)
                await auth_pool.query_modify(
                    'ALTER TABLE users ADD COLUMN suspended_until TIMESTAMP'
                )
            else:
                sync_messenger(info='Column already exists', type=MsgType.DEBUG)
    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t add column \'suspended_until\' automatically: {str(e)}, consider doing a manual double-check') from e
    finally:
        await auth_pool.close()

register_migration(upper_version, migrate)