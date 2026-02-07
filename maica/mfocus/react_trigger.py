import asyncio
import json

from openai.types.chat import ChatCompletionMessage
from typing import *
from maica.mtrigger.mtrigger_sfe import MtPersistentManager
from maica.maica_utils import *

async def react_detect(query: str, fsc: FullSocketsContainer, choice_list: list) -> Union[str, bool, None]:
    system_init = f"""你是一个人工智能助手, 你接下来会收到一条输入和一系列可用选项.
用户可以请求'游戏内操作', 你需要判断用户是否提出了此类请求, 以及请求是否可被完成. 可用文字应对的请求不属于游戏内操作.
若用户没有提出游戏内操作请求, 则输出null. 若用户提出了游戏内操作请求, 则输出相应的选项表示请求可完成, 否则输出false表示不可完成. 以json形式输出, 你的输出应形如{{"choice": 结果(str, false或null)}}.
Begin!""" if fsc.maica_settings.basic.target_lang == 'zh' else f"""You are a helpful assistant, now you will recieve a query and a list of avaliable choices.
User can request for 'ingame actions', you have to determine if user requested for any and if they could be satisfied. Requests that can be answered in text are not considered.
Return null if the query contains no ingame action request. Otherwise, return the corresponding choice to indicate satisfiable, or return false if not satisfiable. Output in json format as {{"choice": result(choice, false or null)}}.
Begin!"""
    messages = [
        {"role": "system", "content": system_init},
        {"role": "user", "content": f"query: {query}; choices: {json.dumps(choice_list)}"}
    ]

    completion_args = {
        "messages": messages,
        "response_format": {"type": "json_object"},
    }

    resp = await (fsc.mnerve_conn or fsc.mfocus_conn).make_completion(**completion_args)
    resp_content, resp_reasoning = resp.choices[0].message.content, getattr(resp.choices[0].message, 'reasoning_content', None)
    resp_json = proceed_common_text(resp_content, is_json=True)

    sync_messenger(info=f"Finished reaction detection: {resp_json}", type=MsgType.DEBUG)
    return resp_json.get('choice')