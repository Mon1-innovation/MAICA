from sqlalchemy import inspect, text
from maica.maica_utils import *
from .base import register_migration

upper_version = "1.2.003"

async def migrate():

    try:
        async with DatabaseUtils.engine_auth.begin() as conn:
            columns = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns('users'))
            exist = any(column['name'] == 'suspended_until' for column in columns)
            if not exist:
                sync_messenger(info='Column does not exist, creating...', type=MsgType.DEBUG)
                await conn.execute(text('ALTER TABLE users ADD COLUMN suspended_until DATETIME DEFAULT NULL'))
            else:
                sync_messenger(info='Column already exists', type=MsgType.DEBUG)
    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t add column \'suspended_until\' automatically: {str(e)}, consider doing a manual double-check') from e

register_migration(upper_version, migrate)
