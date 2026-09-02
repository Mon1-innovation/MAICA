"""Warn about prompt overrides that predate Monika nickname support."""

from maica.maica_utils import *
from .base import register_migration

target_version = "1.3.004"

PROMPT_KEYS = (
    "MAICA_PROMPT_ZC",
    "MAICA_PROMPT_ZW",
    "MAICA_PROMPT_EC",
    "MAICA_PROMPT_EW",
    "MAICA_PROMPT_AC",
    "MAICA_PROMPT_AW",
)


def _supports_monika_nickname(prompt: str | None) -> bool:
    if not prompt:
        return False
    return replace_prompt_placeholders(
        prompt,
        {"monika_nickname": ""},
    ) != prompt


async def migrate():
    outdated_keys = [
        key for key in PROMPT_KEYS
        if not _supports_monika_nickname(load_env(key))
    ]
    if not outdated_keys:
        sync_messenger(
            info=(
                "[migration-7] Effective prompt configuration supports Monika nicknames, skipping warning"
            ),
            type=MsgType.DEBUG,
        )
        return

    sync_messenger(
        info=(
            "\nEffective prompt configuration predates Monika nickname support.\n"
            "The following keys do not contain {monika_nickname}:\n"
            f"{', '.join(outdated_keys)}\n"
            "Review every environment source used by this deployment (process environment, --envdir, and extra env files); either remove unneeded overrides so env_basis defaults apply, or add the placeholder manually.\n"
            "No environment file was changed."
        ),
        type=MsgType.WARN,
    )


register_migration(target_version, migrate)
