import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from maica.maica_utils import FullSocketsContainer, MaicaSession, MaicaSessionItem
from maica.mfocus.agent_modules import AgentTools
from maica.mfocus.mfocus_llm import MfPipeliner
from maica.mtrigger.mtrigger_llm import MtPipeliner


def message(text):
    return {"type": "message", "content": [{"type": "output_text", "text": text}]}


def tool_call(name, arguments="{}"):
    return {
        "type": "function_call", "status": "completed", "call_id": f"call-{name}",
        "name": name, "arguments": arguments,
    }


def make_pipeline(kind, replies, monkeypatch, *, disable_loop=False):
    requests, events = [], []

    async def make_completion(**kwargs):
        requests.append(deepcopy(kwargs))
        reply = replies[min(len(requests) - 1, len(replies) - 1)]
        if kwargs.get("stream"):
            async def stream():
                if isinstance(reply, Exception):
                    raise reply
                for item in reply:
                    if item["type"] == "message":
                        for part in item["content"]:
                            if part["type"] == "output_text":
                                yield {"type": "response.output_text.delta", "delta": part["text"]}
                    yield {"type": "response.output_item.done", "item": item}
                yield {"type": "response.completed", "response": {"output": reply}}
            return stream()
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(output=reply)

    async def messenger(*args, **kwargs):
        events.append(args)

    fsc = FullSocketsContainer()
    fsc.maica_settings.basic.target_lang = "en"
    fsc.maica_settings.extra.mf_disable_loop = disable_loop
    fsc.maica_settings.extra.mt_disable_loop = disable_loop
    fsc.maica_settings.extra.mf_llm_concl = True
    fsc.mfocus_conn = SimpleNamespace(default_reasoning=True, make_completion=make_completion)
    monkeypatch.setattr(fsc, "messenger", messenger)

    session = MaicaSession()
    session.append(MaicaSessionItem("user", "Hello", target_lang="en"))
    if kind == "mfocus":
        async def time_acquire(self, **kwargs):
            return "It is 09:00.", True
        monkeypatch.setattr(AgentTools, "time_acquire", time_acquire)
        pipeline = MfPipeliner(session, fsc, SimpleNamespace())
    else:
        session.append(MaicaSessionItem("assistant", "Hello!", target_lang="en"))
        trigger = {
            "type": "function", "name": "test_action", "description": "Test action",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        }
        st = SimpleNamespace(form_jsc=lambda _: [trigger])
        pipeline = MtPipeliner(session, fsc, SimpleNamespace(affection=50), st)
    return pipeline, requests, events


@pytest.mark.parametrize("kind", ["mfocus", "mtrigger"])
@pytest.mark.parametrize("output", [
    [],
    [message("No tools are needed.")],
    [{"type": "reasoning", "summary": [{"type": "summary_text", "text": "Nothing to do."}]}],
])
def test_agents_stop_after_no_tool_calls(kind, output, monkeypatch):
    pipeline, requests, events = make_pipeline(kind, [output], monkeypatch)

    asyncio.run(pipeline._query_response())

    assert len(requests) == 1
    assert "no_tool_calls" in events[-1][1]


@pytest.mark.parametrize("kind", ["mfocus", "mtrigger"])
@pytest.mark.parametrize("disable_loop", [False, True])
@pytest.mark.parametrize("finish_with_tool", [False, True])
def test_agents_preserve_tool_results_and_termination(kind, disable_loop, finish_with_tool, monkeypatch):
    action = "time_acquire" if kind == "mfocus" else "test_action"
    ending = [tool_call("conclude_information", '{"conclusion":null}')] if kind == "mfocus" else [
        tool_call("agent_finished")
    ]
    replies = [[tool_call(action)], ending if finish_with_tool else [message("Finished.")]]
    pipeline, requests, events = make_pipeline(kind, replies, monkeypatch, disable_loop=disable_loop)

    if kind == "mfocus":
        guidance, results = asyncio.run(pipeline.run_mf_pipeline())
        assert guidance == ""
        assert results == {"time_acquire": "It is 09:00."}
    else:
        asyncio.run(pipeline.run_mt_pipeline())
        actions = [event for event in events if event[0] == "maica_mtrigger_trigger"]
        assert len(actions) == 1
        assert actions[0][1] == {"name": "test_action", "arguments": {}}

    assert len(requests) == (1 if disable_loop else 2)
    if not disable_loop:
        assert any(item.get("type") == "function_call_output" for item in requests[1]["input"])
        assert ("stopping_tool" if finish_with_tool else "no_tool_calls") in events[-1][1]


@pytest.mark.parametrize("kind", ["mfocus", "mtrigger"])
@pytest.mark.parametrize("invalid_arguments", [False, True])
def test_agents_propagate_response_errors(kind, invalid_arguments, monkeypatch):
    reply = [tool_call("agent_finished", "{")] if invalid_arguments else RuntimeError("response failed")
    pipeline, requests, events = make_pipeline(kind, [reply], monkeypatch)

    with pytest.raises(ValueError if invalid_arguments else RuntimeError):
        asyncio.run(pipeline._query_response())

    assert len(requests) == 1
    assert not any(event[0].endswith("_tool_fin") for event in events)
