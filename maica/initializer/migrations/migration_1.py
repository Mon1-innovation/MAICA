from sqlalchemy import text
from maica.maica_utils import *
from .base import register_migration

upper_version = "1.1.007.post3"

async def migrate():

    try:
        async with DatabaseUtils.engine_data.begin() as conn:
            if conn.dialect.name == "mysql":
                await conn.execute(text('RENAME TABLE cchop_archived TO crop_archived'))
            else:
                await conn.execute(text('ALTER TABLE cchop_archived RENAME TO crop_archived'))
    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t rename table cchop_archived to crop_archived: {str(e)}, maybe manually done already?') from e

register_migration(upper_version, migrate)
