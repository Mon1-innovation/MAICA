import asyncio

from typing import *
from packaging.version import parse, Version
from collections.abc import Callable
from maica.maica_utils import *

_migrations = []
available_list: list[tuple[Version, Callable]] = []

def register_migration(upper_version: str, migrate_func):
    _migrations.append((parse(upper_version), migrate_func))

def get_migrations():
    return sorted(_migrations, key=lambda x: x[0])

async def migrate_async(version):
    migrated = False

    last_version_parsed = parse(version)
    curr_version = load_env('MAICA_CURR_VERSION')
    curr_version_parsed = parse(curr_version)
    if last_version_parsed > curr_version_parsed:
        raise CriticalMaicaError(
            f"Database version {version} is newer than backend version {curr_version}; downgrade is unsafe"
        )

    sync_messenger(info=f'[maica-mig] Last initialized version {version}, current version {curr_version}', type=MsgType.DEBUG)

    for mig_item in available_list:
        if curr_version_parsed >= mig_item[0] > last_version_parsed:
            try:
                sync_messenger(info=f'Running migration upper-version {str(mig_item[0])}...', type=MsgType.PRIM_LOG)
                await mig_item[1]()
                sync_messenger(info=f'Finished migration upper-version {str(mig_item[0])}', type=MsgType.PRIM_LOG)
                migrated = True
            except CommonMaicaException as ce:
                sync_messenger(error=ce)
                raise CriticalMaicaError(
                    f"Migration {mig_item[0]} failed; version marker was not advanced"
                ) from ce
    if migrated:
        sync_messenger(info='[maica-mig] Migration finished, continuing launch procedure...', type=MsgType.LOG)
    else:
        sync_messenger(info='[maica-mig] No migration applied, continuing launch procedure...', type=MsgType.DEBUG)

    return migrated


def migrate(version):
    async def run():
        try:
            return await migrate_async(version)
        finally:
            # AsyncEngine pools must be disposed on the loop that used them.
            # Runtime code can then reconnect safely on its own event loop.
            await dispose_database_engines()

    return asyncio.run(run())
