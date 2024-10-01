import re
import json
import datetime
import traceback
import asyncio
import nest_asyncio
from openai import AsyncOpenAI, OpenAI # type: ignore
from loadenv import load_env

async def waste_some_time():
    client = AsyncOpenAI(
        api_key='EMPTY',
        base_url=load_env('MFOCUS_ADDR'),
    )
    client2 = OpenAI(
        api_key='EMPTY',
        base_url=load_env('MFOCUS_ADDR'),
    )
    l1 = client2.models.list()
    l2 = await client.models.list()
    print(l1)
    print(l2)
    model_type = l2.data[0].id
    messages = []
    messages.append({'role': 'user', 'content': "Explain what's global economy"})
    completion_args = {
        "model": model_type,
        "messages": messages,
        "stop": ['Observation:'],
        "temperature": 0.1,
        "top_p": 0.6,
        "presence_penalty": -0.5,
        "frequency_penalty": 0.5,
        "seed": 42
    }
    resp = await client.chat.completions.create(**completion_args)
    return resp.choices[0].message.content
