from sqlalchemy import inspect, text
from maica.maica_utils import *
from .base import register_migration

upper_version = "1.1.007.post3"

async def migrate():

    try:
        async with DatabaseUtils.engine_data.begin() as conn:
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
            if "crop_archived" in tables:
                sync_messenger(info="[migration-1] crop_archived already exists, skipping", type=MsgType.DEBUG)
            elif "cchop_archived" not in tables:
                raise RuntimeError("Neither cchop_archived nor crop_archived exists")
            elif conn.dialect.name == "mysql":
                await conn.execute(text('RENAME TABLE cchop_archived TO crop_archived'))
            else:
                await conn.execute(text('ALTER TABLE cchop_archived RENAME TO crop_archived'))
    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t rename table cchop_archived to crop_archived: {str(e)}, consider doing a manual double-check') from e

register_migration(upper_version, migrate)
