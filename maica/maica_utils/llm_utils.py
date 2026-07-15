"""
Import layer 3.1
Some convenience things, many minor LLM usages will need them.
"""

import asyncio
import orjson

from typing import *
from pydantic import BaseModel, Field, model_validator
from dataclasses import dataclass
from contextlib import asynccontextmanager
from openai import AsyncStream
from openai.types.responses import Response, ResponseStreamEvent
from .connection_utils import AiConnectionManager
from .maica_utils import *

class ToolCall(BaseModel):
    type: str = "function_call"
    call_id: str
    name: str
    arguments: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def auto_compat(cls, data: Any):
        if isinstance(data, dict):
            if data.get("input") and not data.get("arguments"):
                data["arguments"] = data["input"]
            if data.get("function") and not data.get("name"):
                data["name"] = data["function"]

            if isinstance(data.get("arguments"), str):
                data["arguments"] = orjson.loads(data["arguments"])

        return data

async def parse_responses_output(
    resp: Response | AsyncStream[ResponseStreamEvent],
) -> Tuple[
    asyncio.Task,
    AsyncIterator[str],
    AsyncIterator[str],
    AsyncIterator[ToolCall],
]:
    """
    Returns:
        reasoning_stream: async iterator[str]
        content_stream: async iterator[str]
        tool_call_stream: async iterator[dict]
    """

    reasoning_q: asyncio.Queue[str | None] = asyncio.Queue()
    content_q: asyncio.Queue[str | None] = asyncio.Queue()
    tool_q: asyncio.Queue[dict | None] = asyncio.Queue()

    _tool_calls_ids: set[str] = set()

    def get_value(item, key, default=None):
        return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)

    def handle_item(item: Response | ResponseStreamEvent | dict):
        t = get_value(item, "type")

        # Non-streaming Responses wrap text parts inside a message item.
        if t == "message":
            for content_item in get_value(item, "content", []) or []:
                handle_item(content_item)
            return

        # Some streaming events wrap their actual item/part one level deeper.
        nested = get_value(item, "item") or get_value(item, "part")
        if nested is not None and nested is not item:
            handle_item(nested)

        # reasoning
        if t and "reasoning" in t:
            text = get_value(item, "text") or get_value(item, "delta", "")
            if text:
                reasoning_q.put_nowait(text)

        # content
        elif t in ("output_text", "text") or (t and "output_text" in t):
            text = get_value(item, "text") or get_value(item, "delta", "")
            if text:
                content_q.put_nowait(text)

        # tool call
        elif t in ("tool_call", "function_call", "function"):
            if get_value(item, "status") not in ("completed", None):
                # This is likely "in_progress", so we ignore it since the complete result will contain everything
                return

            else:
                if isinstance(item, BaseModel):
                    item = item.model_dump()
                elif not isinstance(item, dict):
                    item = {
                        key: get_value(item, key)
                        for key in ("type", "call_id", "name", "arguments")
                    }
                tool_call = ToolCall.model_validate(item)
                
                if tool_call.call_id not in _tool_calls_ids:
                    _tool_calls_ids.add(tool_call.call_id)
                    tool_q.put_nowait(tool_call)

        else:
            delta = get_value(item, "delta")
            if isinstance(delta, str) and not (t and "function_call" in t):
                content_q.put_nowait(delta)

    async def runner():
        try:
            # streaming
            if hasattr(resp, "__aiter__"):
                async for event in resp:
                    item = getattr(event, "item", event)
                    handle_item(item)
            # non-streaming
            else:
                outputs = get_value(resp, "output", []) or []
                for item in outputs:
                    handle_item(item)

        finally:
            # close streams
            await reasoning_q.put(None)
            await content_q.put(None)
            await tool_q.put(None)

    task = asyncio.create_task(runner())

    async def reasoning_stream() -> AsyncIterator[str]:
        while True:
            item = await reasoning_q.get()
            if item is None:
                break
            yield item

    async def content_stream() -> AsyncIterator[str]:
        while True:
            item = await content_q.get()
            if item is None:
                break
            yield item

    async def tool_stream() -> AsyncIterator[ToolCall]:
        while True:
            item = await tool_q.get()
            if item is None:
                break
            yield item

    return task, reasoning_stream(), content_stream(), tool_stream()

@asynccontextmanager
async def llm_request(conn: AiConnectionManager, *args, **kwargs):
    """
    Send request to LLM and retrieves parsed results.
    """    
    resp = await conn.make_completion(*args, **kwargs)
    task = None
    try:
        task, a_reasoning, a_content, a_tool_calls = await parse_responses_output(resp)
        yield (task, a_reasoning, a_content, a_tool_calls, )
    finally:
        if task:
            await task
