import asyncio
import datetime

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from maica.maica_utils import MaicaDbError, check_terms_acceptance, parse_tos_ids


def test_parse_tos_ids() -> None:
    assert parse_tos_ids(None) == ()
    assert parse_tos_ids("") == ()
    assert parse_tos_ids("0, 2, 1, 2") == (1, 2)
    with pytest.raises(ValueError):
        parse_tos_ids("1,broken")


def test_check_terms_acceptance_matches_fof_terms_state() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.execute(sqlalchemy.text(
                    "CREATE TABLE fof_terms_policies ("
                    "id INTEGER PRIMARY KEY, terms_updated_at DATETIME)"
                ))
                await connection.execute(sqlalchemy.text(
                    "CREATE TABLE fof_terms_policy_user ("
                    "policy_id INTEGER, user_id INTEGER, accepted_at DATETIME, is_accepted BOOLEAN)"
                ))
                await connection.execute(sqlalchemy.text(
                    "INSERT INTO fof_terms_policies VALUES "
                    "(1, '2025-01-01 00:00:00'), (2, NULL), (3, NULL), (4, NULL)"
                ))
                await connection.execute(sqlalchemy.text(
                    "INSERT INTO fof_terms_policy_user VALUES "
                    "(1, 7, '2025-01-02 00:00:00', 1), "
                    "(2, 7, '2025-01-02 00:00:00', 1), "
                    "(3, 7, '2025-01-02 00:00:00', 0)"
                ))

            async with factory() as session:
                assert await check_terms_acceptance(session, 7, ()) == ()
                assert await check_terms_acceptance(session, 7, (2,)) == ()
                assert await check_terms_acceptance(session, 7, (1, 3, 4)) == (3, 4)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_check_terms_acceptance_reports_missing_dependency_or_policy() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                with pytest.raises(MaicaDbError, match="tables are missing"):
                    await check_terms_acceptance(session, 7, (1,))

            async with engine.begin() as connection:
                await connection.execute(sqlalchemy.text(
                    "CREATE TABLE fof_terms_policies (id INTEGER PRIMARY KEY, terms_updated_at DATETIME)"
                ))
                await connection.execute(sqlalchemy.text(
                    "CREATE TABLE fof_terms_policy_user (policy_id INTEGER, user_id INTEGER, accepted_at DATETIME, is_accepted BOOLEAN)"
                ))

            async with factory() as session:
                with pytest.raises(MaicaDbError, match="policy IDs do not exist"):
                    await check_terms_acceptance(session, 7, (99,))
        finally:
            await engine.dispose()

    asyncio.run(scenario())
