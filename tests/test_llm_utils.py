import asyncio
from types import SimpleNamespace

from maica.maica_utils import FakeChatCompletion
from maica.maica_utils.llm_utils import llm_request, parse_responses_output


async def collect(iterator):
    return [item async for item in iterator]


def test_non_streaming_fake_response_yields_nested_text() -> None:
    async def scenario() -> None:
        task, _, content, _ = await parse_responses_output(FakeChatCompletion("hello"))
        assert await collect(content) == ["hello"]
        await task

    asyncio.run(scenario())


def test_non_streaming_message_and_tool_call_are_parsed() -> None:
    async def scenario() -> None:
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="message",
                    content=[SimpleNamespace(type="output_text", text="answer")],
                ),
                SimpleNamespace(
                    type="function_call",
                    status="completed",
                    call_id="call-1",
                    name="weather",
                    arguments='{"city":"Wuhan"}',
                ),
            ]
        )
        task, _, content, tools = await parse_responses_output(response)
        assert await collect(content) == ["answer"]
        parsed_tools = await collect(tools)
        assert parsed_tools[0].name == "weather"
        assert parsed_tools[0].arguments == {"city": "Wuhan"}
        await task

    asyncio.run(scenario())


def test_function_argument_deltas_are_not_emitted_as_content() -> None:
    class Stream:
        async def __aiter__(self):
            yield SimpleNamespace(type="response.function_call_arguments.delta", delta='{"x":')
            yield SimpleNamespace(type="response.output_text.delta", delta="visible")

    async def scenario() -> None:
        task, _, content, _ = await parse_responses_output(Stream())
        assert await collect(content) == ["visible"]
        await task

    asyncio.run(scenario())


def test_llm_request_cancels_parser_when_consumer_exits_early() -> None:
    class HangingStream:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()

        async def __aiter__(self):
            self.started.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled.set()
            if False:
                yield None

    async def scenario() -> None:
        stream = HangingStream()

        class Connection:
            async def make_completion(self, **_kwargs):
                return stream

        async with llm_request(Connection(), stream=True):
            await stream.started.wait()

        assert stream.cancelled.is_set()

    asyncio.run(scenario())
