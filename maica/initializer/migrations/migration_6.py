"""Add the original MSpire prompt to the SQL cache."""

import asyncio

from sqlalchemy import inspect, text

from maica.maica_utils import *
from .base import register_migration

target_version = "1.3.003.post3"


async def migrate():
    try:
        async with DatabaseUtils.engine_data.begin() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_columns("ms_cache")
            )
            if any(column["name"] == "prompt" for column in columns):
                sync_messenger(
                    info="[migration-6] ms_cache.prompt already exists, skipping",
                    type=MsgType.DEBUG,
                )
                return

            if conn.dialect.name == "mysql":
                ddl = "ALTER TABLE `ms_cache` ADD COLUMN `prompt` TEXT NULL AFTER `hash`"
            else:
                ddl = "ALTER TABLE ms_cache ADD COLUMN prompt TEXT"
            await conn.execute(text(ddl))
    except Exception as exc:
        raise MaicaDbWarning(
            f"Couldn't add prompt column to ms_cache: {exc}, consider doing a manual double-check"
        ) from exc


register_migration(target_version, migrate)


if __name__ == "__main__":
    from maica import init

    init()
    asyncio.run(migrate())
