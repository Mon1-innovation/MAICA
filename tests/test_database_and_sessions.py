import asyncio
import time

import bcrypt
import pytest
import sqlalchemy
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from maica.maica_utils import (
    DatabaseUtils,
    FullSocketsContainer,
    G,
    MaicaInputWarning,
    MaicaSession,
    MaicaSessionItem,
    SqlBaseData,
    SqlCropArchived,
    SqlMsCache,
    SqlBaseAuth,
    SqlUser,
    RealtimeSocketsContainer,
    SessionPersistent,
    crypto_object,
    online_dict,
    sqla_create_or_update,
)
from maica.maica_utils import session_mgr, stream_buffer
from maica.maica_utils.database_utils import ReadOnlySession
from maica.maica_utils.users_utils import FscUsersFuncMixin
from maica.initializer.migrations import migration_4, migration_5, migration_6


def test_create_or_update_flushes_insert_and_updates_existing_row() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SqlBaseData.metadata.create_all)
            async with session_factory() as dbs, dbs.begin():
                await sqla_create_or_update(
                    dbs,
                    SqlMsCache,
                    {"hash": "abc"},
                    {"user_id": 1, "content": "first"},
                )
            async with session_factory() as dbs, dbs.begin():
                await sqla_create_or_update(
                    dbs,
                    SqlMsCache,
                    {"hash": "abc"},
                    {"user_id": 1, "content": "second"},
                )
            async with session_factory() as dbs:
                rows = (await dbs.scalars(sqlalchemy.select(SqlMsCache))).all()
                assert len(rows) == 1
                assert rows[0].user_id == 1
                assert rows[0].content == "second"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_partial_archive_can_create_its_first_row() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        old_factory = DatabaseUtils.SessionData
        DatabaseUtils.SessionData = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SqlBaseData.metadata.create_all)

            fsc = FullSocketsContainer()
            verification = fsc.maica_settings.verification
            verification.user_id = 1
            verification.username = "tester"
            verification.nickname = None
            verification.email = "tester@example.com"

            session = MaicaSession(1, fsc)
            session.extend([
                MaicaSessionItem("system", "prompt"),
                MaicaSessionItem("user", "hello", target_lang="en"),
                MaicaSessionItem("assistant", "hi", target_lang="en"),
            ])
            await session.init_db()
            await session.to_partial_archive()
            session.append(MaicaSessionItem("user", "again", target_lang="en"))
            session.append(MaicaSessionItem("assistant", "welcome back", target_lang="en"))
            await session.to_partial_archive()

            async with DatabaseUtils.SessionData() as dbs:
                archive = await dbs.scalar(sqlalchemy.select(SqlCropArchived))
                assert archive is not None
                assert "hello" in archive.content
                assert "again" in archive.content
        finally:
            DatabaseUtils.SessionData = old_factory
            await engine.dispose()

    asyncio.run(scenario())


def test_db_bound_object_loads_blank_text_as_empty_content() -> None:
    persistent = SessionPersistent()
    persistent.load("   ")
    assert persistent.content == {}


def test_persistent_info_respects_temp_and_persistent_boundaries() -> None:
    fsc = FullSocketsContainer()
    fsc.maica_settings.basic.target_lang = "en"
    persistent = SessionPersistent(fsc=fsc)

    persistent.content = {
        "mas_playername": "Persistent Player",
        "mas_monikaname": "Persistent Nickname",
        "mas_player_bday": [2000, 1, 2],
        "mas_affection": 100,
    }
    temporary_only = "\n".join(persistent.form_info(where="temp"))
    assert "Persistent Player" not in temporary_only
    assert "Persistent Nickname" not in temporary_only
    assert "2000" not in temporary_only
    assert "new lovers" not in temporary_only

    persistent.content = {}
    persistent.content_temp = {
        "mas_playername": "Temporary Player",
        "mas_monikaname": "Temporary Nickname",
        "mas_player_bday": [2001, 2, 3],
        "mas_affection": 200,
    }
    persistent_only = "\n".join(persistent.form_info(where="pers"))
    assert "Temporary Player" not in persistent_only
    assert "Temporary Nickname" not in persistent_only
    assert "2001" not in persistent_only
    assert "harmonious lovers" not in persistent_only


def test_temp_info_limit_does_not_count_persistent_basic_fields() -> None:
    fsc = FullSocketsContainer()
    persistent = SessionPersistent(fsc=fsc)
    persistent.content = {"mas_playername": "Persistent Player"}
    persistent.content_temp = {
        "mas_player_additions": [f"Temporary item {index}" for index in range(27)]
    }

    persistent.validate()
    assert len(persistent.form_info(where="temp")) == 32


def test_monika_nickname_rejects_non_string_values() -> None:
    fsc = FullSocketsContainer()
    persistent = SessionPersistent(fsc=fsc)
    persistent.content_temp = {"mas_monikaname": 123}

    with pytest.raises(MaicaInputWarning, match="mas_monikaname must be a string"):
        _ = persistent.mname


def test_dbo_acquire_binds_fsc_only_while_holding_lock() -> None:
    async def scenario() -> None:
        def make_fsc() -> FullSocketsContainer:
            fsc = FullSocketsContainer()
            fsc.maica_settings.verification.user_id = 1
            fsc.maica_settings.temp.chat_session = 0
            return fsc

        session_mgr._sessions_index["session_triggers"].clear()
        first_fsc = make_fsc()
        second_fsc = make_fsc()
        second_seen: list[bool] = []
        waiter = None

        async def second_request() -> None:
            async with session_mgr.acquire_dbo("trigger", second_fsc) as trigger:
                second_seen.append(trigger.fsc is second_fsc)
                trigger._check_ess()

        try:
            async with session_mgr.acquire_dbo("trigger", first_fsc) as trigger:
                waiter = asyncio.create_task(second_request())
                await asyncio.sleep(0)
                assert trigger.fsc is first_fsc

            await waiter
            assert second_seen == [True]
        finally:
            if waiter is not None and not waiter.done():
                await waiter
            session_mgr._sessions_index["session_triggers"].clear()

    asyncio.run(scenario())


def test_session_and_buffer_gc_remove_only_stale_unlocked_entries() -> None:
    class Destroyable:
        def __init__(self) -> None:
            self.lock = asyncio.Lock()
            self.is_destroyed = False

        def destroy(self) -> None:
            self.is_destroyed = True

    session_mgr._sessions_index["maica_sessions"].clear()
    stale = Destroyable()
    session_mgr._sessions_index["maica_sessions"][(1, 1)] = [stale, 1.0]
    assert session_mgr.dbos_gc(time.time()) == [("maica_sessions", (1, 1))]
    assert stale.is_destroyed

    stream_buffer._buffers_index.clear()
    stream_buffer._buffers_index[1] = [stream_buffer.StreamBuffer(), 1.0]
    assert stream_buffer.buffers_gc(time.time()) == [1]


def test_current_schema_migration_is_idempotent_on_sqlite() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        old_engine = DatabaseUtils.engine_data
        old_milvus = G.A.MILVUS_ADDR
        DatabaseUtils.engine_data = engine
        G.A.MILVUS_ADDR = ""
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SqlBaseData.metadata.create_all)
            await migration_4.migrate()
            await migration_4.migrate()
            await migration_5.migrate()
            await migration_5.migrate()
            await migration_6.migrate()
            await migration_6.migrate()
        finally:
            DatabaseUtils.engine_data = old_engine
            G.A.MILVUS_ADDR = old_milvus
            await engine.dispose()

    asyncio.run(scenario())


def test_mspire_prompt_migration_adds_nullable_column_without_touching_rows() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        old_engine = DatabaseUtils.engine_data
        DatabaseUtils.engine_data = engine
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    sqlalchemy.text(
                        """
                        CREATE TABLE ms_cache (
                            spire_id INTEGER PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            hash VARCHAR(255) NOT NULL,
                            content TEXT,
                            timestamp DATETIME
                        )
                        """
                    )
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO ms_cache (spire_id, user_id, hash, content) "
                        "VALUES (1, 7, 'legacy-hash', 'legacy-content')"
                    )
                )

            await migration_6.migrate()
            await migration_6.migrate()

            async with engine.connect() as conn:
                columns = await conn.run_sync(
                    lambda sync_conn: sqlalchemy.inspect(sync_conn).get_columns("ms_cache")
                )
                assert [column["name"] for column in columns].count("prompt") == 1
                row = (
                    await conn.execute(
                        sqlalchemy.text(
                            "SELECT hash, content, prompt FROM ms_cache WHERE spire_id = 1"
                        )
                    )
                ).one()
                assert tuple(row) == ("legacy-hash", "legacy-content", None)
        finally:
            DatabaseUtils.engine_data = old_engine
            await engine.dispose()

    asyncio.run(scenario())


def test_new_websocket_login_atomically_replaces_stale_session() -> None:
    class FakeWebSocket:
        def __init__(self, lock):
            self.lock = lock
            self.closed = False
            self.sent = []

        async def send(self, payload):
            self.sent.append(payload)

        async def close(self, *_args):
            self.closed = True
            if self.lock.locked():
                self.lock.release()

    async def scenario() -> None:
        auth_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        data_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        old_auth, old_data = DatabaseUtils.SessionAuth, DatabaseUtils.SessionData
        old_public, old_private = crypto_object.public_key, crypto_object.private_key
        try:
            async with auth_engine.begin() as conn:
                await conn.run_sync(SqlBaseAuth.metadata.create_all)
            async with data_engine.begin() as conn:
                await conn.run_sync(SqlBaseData.metadata.create_all)

            setup_auth = async_sessionmaker(auth_engine, expire_on_commit=False)
            async with setup_auth() as dbs, dbs.begin():
                dbs.add(
                    SqlUser(
                        id=1,
                        username="tester",
                        nickname=None,
                        email="tester@example.com",
                        is_email_confirmed=True,
                        password=bcrypt.hashpw(b"secret", bcrypt.gensalt(rounds=4)).decode(),
                        suspended_until=None,
                    )
                )

            DatabaseUtils.SessionAuth = async_sessionmaker(
                auth_engine,
                class_=ReadOnlySession,
                expire_on_commit=False,
            )
            DatabaseUtils.SessionData = async_sessionmaker(data_engine, expire_on_commit=False)
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            crypto_object.private_key = private_key
            crypto_object.public_key = private_key.public_key()
            G.A.F2B_COUNT = "20"
            G.A.F2B_TIME = "600"
            G.A.KICK_STALE_CONNS = "1"
            token = await FscUsersFuncMixin.TokenCridential(
                username="tester",
                password="secret",
            ).generate_token()

            first_lock = asyncio.Lock()
            await first_lock.acquire()
            first_ws = FakeWebSocket(first_lock)
            first_rsc = RealtimeSocketsContainer(session_lock=first_lock)
            first_rsc.websocket = first_ws
            first = FullSocketsContainer(rsc=first_rsc)
            await first.login(token)

            second_lock = asyncio.Lock()
            await second_lock.acquire()
            second_ws = FakeWebSocket(second_lock)
            second_rsc = RealtimeSocketsContainer(session_lock=second_lock)
            second_rsc.websocket = second_ws
            second = FullSocketsContainer(rsc=second_rsc)
            await second.login(token)

            assert online_dict[1][0] is second
            assert first_ws.closed
            second_lock.release()
        finally:
            online_dict.clear()
            DatabaseUtils.SessionAuth, DatabaseUtils.SessionData = old_auth, old_data
            crypto_object.public_key, crypto_object.private_key = old_public, old_private
            await auth_engine.dispose()
            await data_engine.dispose()

    asyncio.run(scenario())
