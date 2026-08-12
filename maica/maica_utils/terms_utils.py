"""Read-only integration with the FoF Terms tables in the Flarum database."""
from __future__ import annotations

import datetime
import re
from collections.abc import Iterable

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession

from .maica_utils import MaicaDbError


_TERM_ID = re.compile(r"[0-9]+")
_POLICIES_TABLE = "fof_terms_policies"
_POLICY_USER_TABLE = "fof_terms_policy_user"


def parse_tos_ids(raw: str | None) -> tuple[int, ...]:
    """Parse the configured FoF policy IDs; zero and empty input disable checks."""
    if raw is None or not raw.strip():
        return ()

    result: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if not _TERM_ID.fullmatch(item):
            raise ValueError("MAICA_TOS_IDS must contain comma-separated non-negative integers")
        policy_id = int(item)
        if policy_id:
            result.add(policy_id)

    return tuple(sorted(result))


def _as_datetime(value: object) -> datetime.datetime | None:
    if value is None or isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise MaicaDbError(f"Invalid FoF Terms timestamp: {value!r}") from None
    raise MaicaDbError(f"Invalid FoF Terms timestamp type: {type(value).__name__}")


async def check_terms_acceptance(
    session: AsyncSession,
    user_id: int,
    policy_ids: Iterable[int],
) -> tuple[int, ...]:
    """Return configured policy IDs that the user must still accept.

    The configured IDs are intentionally treated as required by MAICA, regardless
    of FoF's optional flag or postpone permission.  Missing tables and policies
    are deployment/database errors, not user authentication warnings.
    """
    ids = tuple(sorted(set(policy_ids)))
    if not ids:
        return ()

    statement = sqlalchemy.text(
        f"""
        SELECT p.id, p.terms_updated_at, pu.accepted_at, pu.is_accepted
        FROM {_POLICIES_TABLE} AS p
        LEFT JOIN {_POLICY_USER_TABLE} AS pu
          ON pu.policy_id = p.id AND pu.user_id = :user_id
        WHERE p.id IN :policy_ids
        """
    ).bindparams(sqlalchemy.bindparam("policy_ids", expanding=True))

    try:
        rows = (
            await session.execute(statement, {"user_id": user_id, "policy_ids": list(ids)})
        ).mappings().all()
    except sqlalchemy.exc.SQLAlchemyError as exc:
        raise MaicaDbError(
            "FoF Terms tables are missing or unavailable in AUTH_DB"
        ) from exc

    rows_by_id = {int(row["id"]): row for row in rows}
    missing_policies = sorted(set(ids) - rows_by_id.keys())
    if missing_policies:
        raise MaicaDbError(
            f"FoF Terms policy IDs do not exist: {', '.join(map(str, missing_policies))}"
        )

    unaccepted: list[int] = []
    for policy_id in ids:
        row = rows_by_id[policy_id]
        accepted_at = _as_datetime(row["accepted_at"])
        updated_at = _as_datetime(row["terms_updated_at"])
        is_accepted = bool(row["is_accepted"])
        if not is_accepted or accepted_at is None or (
            updated_at is not None and updated_at > accepted_at
        ):
            unaccepted.append(policy_id)

    return tuple(unaccepted)
