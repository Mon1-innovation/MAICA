import asyncio

from packaging.version import parse

from maica.initializer.migrations import base
from maica.initializer.migrations import migration_7
from maica.maica_utils import DatabaseUtils, MsgType


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


def test_prompt_override_migration_warns_about_effective_legacy_values(monkeypatch) -> None:
    messages = []
    values = {key: "legacy prompt" for key in migration_7.PROMPT_KEYS}
    values["MAICA_PROMPT_EC"] = "Current {monika_nickname} prompt"
    values["MAICA_PROMPT_EW"] = "Escaped {{monika_nickname}} prompt"

    monkeypatch.setattr(migration_7, "load_env", values.get)
    monkeypatch.setattr(migration_7, "sync_messenger", lambda **kwargs: messages.append(kwargs))

    asyncio.run(migration_7.migrate())

    assert messages[0]["type"] == MsgType.WARN
    assert "MAICA_PROMPT_ZC" in messages[0]["info"]
    assert "MAICA_PROMPT_EC" not in messages[0]["info"]
    assert "MAICA_PROMPT_EW" in messages[0]["info"]
    assert "No environment file was changed" in messages[0]["info"]


def test_prompt_override_migration_skips_warning_for_current_values(monkeypatch) -> None:
    messages = []
    values = {
        key: "Current {monika_nickname} prompt"
        for key in migration_7.PROMPT_KEYS
    }

    monkeypatch.setattr(migration_7, "load_env", values.get)
    monkeypatch.setattr(migration_7, "sync_messenger", lambda **kwargs: messages.append(kwargs))

    asyncio.run(migration_7.migrate())

    assert messages == [{
        "info": "[migration-7] Effective prompt configuration supports Monika nicknames, skipping warning",
        "type": MsgType.DEBUG,
    }]
