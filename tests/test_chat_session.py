import asyncio
from types import SimpleNamespace

from maica.maica_utils import (
    FullSocketsContainer,
    MaicaSession,
    MaicaSessionItem,
    replace_prompt_placeholders,
)
from maica.mfocus.pre_core_pipeliner import pre_core_pipelines


def test_monika_nickname_pipeline_does_not_require_player_name() -> None:
    async def scenario() -> None:
        fsc = FullSocketsContainer()
        settings = fsc.maica_settings
        settings.basic.enable_mf = False
        settings.basic.enable_mt = False
        settings.extra.mf_const_tools = 0
        settings.extra.mf_const_sf_access = 0
        settings.extra.prompt_monika_nickname = True

        session = MaicaSession()
        session.append(MaicaSessionItem("user", "hello", target_lang="en"))
        persistent = SimpleNamespace(pname=None, mname="Mia")

        await pre_core_pipelines(
            session=session,
            fsc=fsc,
            sp=persistent,
            st=SimpleNamespace(),
        )

        assert session[-1].context.player_name == "[player]"
        assert session[-1].context.monika_nickname == "Mia"

    asyncio.run(scenario())


def test_prompt_placeholder_replacement_preserves_braces_in_values() -> None:
    dynamic_info = '{"items": ["one", "two"]}'

    result = replace_prompt_placeholders(
        "Known: {known_info}; malformed: {known_info; literal: [x]",
        {"known_info": dynamic_info},
    )

    assert result == f"Known: {dynamic_info}; malformed: {{known_info; literal: [x]"


def test_prompt_placeholder_replacement_supports_multiple_passes() -> None:
    first_pass = replace_prompt_placeholders(
        "Context: {known_info}",
        {"known_info": "From {player_name}"},
    )

    assert replace_prompt_placeholders(first_pass, {"player_name": "Alice"}) == "Context: From Alice"


def test_prompt_placeholder_replacement_preserves_escaped_braces() -> None:
    assert replace_prompt_placeholders("Literal: {{known_info}}", {"known_info": "value"}) == "Literal: {{known_info}}"
