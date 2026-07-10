from sqlalchemy import text
from maica.maica_utils import *
from .base import register_migration

upper_version = "1.2.000.rc2"

async def migrate():

    try:
        async with DatabaseUtils.engine_data.begin() as conn:
            if conn.dialect.name == 'mysql':
                await conn.execute(text('ALTER TABLE `account_status` CHANGE `status` `status` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL'))
                await conn.execute(text('ALTER TABLE `account_status` CHANGE `preferences` `preferences` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL'))
                await conn.execute(text('ALTER TABLE `ms_cache` CHANGE `hash` `hash` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL'))
                await conn.execute(text('ALTER TABLE `ms_cache` CHANGE `content` `content` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL'))
            await conn.run_sync(SqlMvMeta.__table__.create, checkfirst=True)

    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t alter lines LONGTEXT to TEXT and add table mv_meta: {str(e)}, maybe manually done already?') from e
        
register_migration(upper_version, migrate)
