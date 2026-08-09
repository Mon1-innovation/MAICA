from maica.maica_utils.chat_session import _replace_prompt_placeholders


def test_prompt_placeholder_replacement_preserves_braces_in_values() -> None:
    dynamic_info = '{"items": ["one", "two"]}'

    result = _replace_prompt_placeholders(
        "Known: {known_info}; malformed: {known_info; literal: [x]",
        {"known_info": dynamic_info},
    )

    assert result == f"Known: {dynamic_info}; malformed: {{known_info; literal: [x]"


def test_prompt_placeholder_replacement_supports_multiple_passes() -> None:
    first_pass = _replace_prompt_placeholders(
        "Context: {known_info}",
        {"known_info": "From {player_name}"},
    )

    assert _replace_prompt_placeholders(first_pass, {"player_name": "Alice"}) == "Context: From Alice"


def test_prompt_placeholder_replacement_preserves_escaped_braces() -> None:
    assert _replace_prompt_placeholders("Literal: {{known_info}}", {"known_info": "value"}) == "Literal: {{known_info}}"
