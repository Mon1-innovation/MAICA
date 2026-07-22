import asyncio

from packaging.version import parse

from maica.initializer.migrations import base
from maica.maica_utils import DatabaseUtils


def test_migrations_share_one_loop_and_dispose_pools_before_it_closes(monkeypatch) -> None:
    migration_loops = []
    disposal_loops = []

    class FakeEngine:
        async def dispose(self) -> None:
            disposal_loops.append(asyncio.get_running_loop())

    async def first_migration() -> None:
        migration_loops.append(asyncio.get_running_loop())

    async def second_migration() -> None:
        migration_loops.append(asyncio.get_running_loop())

    monkeypatch.setattr(
        base,
        "available_list",
        [
            (parse("1.1.0"), first_migration),
            (parse("1.2.0"), second_migration),
        ],
    )
    monkeypatch.setattr(base, "load_env", lambda _key: "1.2.0")
    monkeypatch.setattr(base, "sync_messenger", lambda **_kwargs: None)
    monkeypatch.setattr(DatabaseUtils, "engine_auth", FakeEngine())
    monkeypatch.setattr(DatabaseUtils, "engine_data", FakeEngine())

    assert base.migrate("1.0.0") is True
    assert len(migration_loops) == 2
    assert migration_loops[0] is migration_loops[1]
    assert disposal_loops == [migration_loops[0], migration_loops[0]]
    assert migration_loops[0].is_closed()
