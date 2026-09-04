import pytest

from maica.maica_utils import GenCorrectionModel, MaicaResponseWarning


class StringResult(GenCorrectionModel):
    result: str


class OptionalStringResult(GenCorrectionModel):
    result: str | None


class IntegerResult(GenCorrectionModel):
    result: int


class MultiFieldResult(GenCorrectionModel):
    result: str
    reason: str


class DefaultIntegerResult(GenCorrectionModel):
    result: int

    _default_resp = {"result": 0}


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("plain text", "plain text"),
        ('"JSON string"', "JSON string"),
        ("```\nfenced text\n```", "fenced text"),
    ],
)
def test_single_string_field_accepts_plain_llm_output(
    output: str,
    expected: str,
) -> None:
    assert StringResult.model_validate_json(output).result == expected


def test_single_optional_string_field_accepts_plain_llm_output() -> None:
    assert OptionalStringResult.model_validate_json("plain text").result == "plain text"


@pytest.mark.parametrize("model", [IntegerResult, MultiFieldResult])
def test_plain_llm_output_without_default_raises_response_warning(
    model: type[GenCorrectionModel],
) -> None:
    with pytest.raises(MaicaResponseWarning, match="LLM output is not a JSON object"):
        model.model_validate_json("plain text")


def test_plain_llm_output_uses_default_response_for_non_string_shape() -> None:
    result = DefaultIntegerResult.model_validate_json("plain text")

    assert result.result == 0
