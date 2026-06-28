"""
Some convenience things, many minor LLM usages will need them.
"""

import asyncio
import json

from typing import *
from dataclasses import dataclass
from openai import AsyncStream
from openai.types.responses import Response, ResponseStreamEvent
from maica.maica_utils import *

async def llm_request(conn: AiConnectionManager, *args, **kwargs) -> Tuple[str, str, List[Dict[str, Any]]]:
    """
    Send request to LLM and retrieves simple results.
    Is streaming compatible actually but I don't think we're using it.
    We implement it for possible future convenience anyway.
    """

    async def parse_responses_output(resp: Response | AsyncStream[ResponseStreamEvent]) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Basically gpt wrote this, I don't want to bother myself.
        Parse OpenAI Responses API output (streaming or non-streaming).

        Returns:
            reasoning_text: str
            content_text: str
            tool_calls: list of {id, name, arguments}
        """

        reasoning_parts = []
        content_parts = []
        tool_calls = {}

        def handle_item(item: Response | ResponseStreamEvent):
            """Handle a single output item or streamed delta."""
            t = getattr(item, "type", None)

            if t and "reasoning" in t:
                text = getattr(item, "text", None) or getattr(item, "delta", "")
                if text:
                    reasoning_parts.append(text)

            elif t in ("message", "output_text", "text"):
                text = getattr(item, "text", None) or getattr(item, "delta", "")
                if text:
                    content_parts.append(text)

            elif t in ("tool_call", "function_call", "function"):
                call_id = getattr(item, "id", None)
                name = getattr(item, "name", None) or getattr(item, "function", None)
                args = getattr(item, "arguments", None) or getattr(item, "input", None)

                if call_id not in tool_calls:
                    tool_calls[call_id] = {
                        "type": "function_call",
                        "call_id": call_id,
                        "name": name,
                        "arguments": "",
                    }

                # streaming arguments may come in chunks
                if isinstance(args, str):
                    tool_calls[call_id]["arguments"] += args

            else:
                delta = getattr(item, "delta", None)
                if isinstance(delta, str):
                    content_parts.append(delta)

        if hasattr(resp, "__aiter__") or hasattr(resp, "__iter__"):
            async for event in resp:
                # some SDKs wrap actual data in event.item
                item = getattr(event, "item", event)
                handle_item(item)

        else:
            outputs = getattr(resp, "output", []) or []
            for item in outputs:
                handle_item(item)

        for tool_call in tool_calls.values():
            try:
                if tool_call.get("arguments"):
                    tool_call["arguments"] = json.loads(tool_call.get("arguments"))
            except Exception as e:
                sync_messenger(info=f"Failed to parse tool arguments {tool_call.get("arguments")}: {str(e)}", type=MsgType.WARN)

        return (
            "".join(reasoning_parts).strip(),
            "".join(content_parts).strip(),
            list(tool_calls.values())
        )
    
    resp = await conn.make_completion(*args, **kwargs)
    return await parse_responses_output(resp)