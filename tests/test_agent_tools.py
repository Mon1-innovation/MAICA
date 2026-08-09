import datetime
from types import SimpleNamespace

from pydantic import TypeAdapter, ValidationError

from maica.maica_utils import MeterTrigger, TypeTrigger
from maica.mfocus.agent_modules import AgentTools


def test_event_reparse_uses_acquisition_date_when_combining_results() -> None:
    reference_date = datetime.date(2099, 1, 1)

    first = AgentTools.AgentEvents(
        [((reference_date - datetime.timedelta(days=1), 1), [SimpleNamespace(name="活动", ename="Event")])]
    )
    first.target_lang = "en"
    first.reference_date = reference_date - datetime.timedelta(days=1)

    second = AgentTools.AgentEvents(
        [((reference_date, 1), [SimpleNamespace(name="今天", ename="Today Event")])]
    )
    second.target_lang = "en"
    second.reference_date = reference_date

    combined = first + second

    assert combined.reference_date == reference_date
    assert combined.agent_reparse() == "31 December, 2098 is Event; Today is Today Event."


def test_tool_schema_has_single_property_layer_and_keeps_zero_bound() -> None:
    trigger = MeterTrigger.model_validate(
        {
            "template": "common_meter_template",
            "name": "change_distance",
            "exprop": {
                "item_name": {"zh": "距离", "en": "distance"},
                "value_limits": [0, 2.5],
                "curr_value": 0,
            },
        }
    )
    schema = trigger.to_tool().to_json_schema("en")
    value_schema = schema["parameters"]["properties"]["value"]
    assert value_schema["type"] == ["number", "null"]
    assert value_schema["minimum"] == 0
    assert "value" not in value_schema


def test_invalid_trigger_name_and_reversed_limits_are_rejected() -> None:
    adapter = TypeAdapter(TypeTrigger)
    for name, limits in (("bad name", [0, 1]), ("valid_name", [2, 1])):
        try:
            adapter.validate_python(
                {
                    "template": "common_meter_template",
                    "name": name,
                    "exprop": {
                        "item_name": {"zh": "距离", "en": "distance"},
                        "value_limits": limits,
                    },
                }
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("invalid trigger was accepted")
