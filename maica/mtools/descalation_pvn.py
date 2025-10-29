import asyncio
from openai.types.chat import ChatCompletionMessage
from typing import *
from maica.maica_utils import *

async def detect(rnds: list[dict, ChatCompletionMessage], target_lang: Literal['zh', 'en']='zh', mnerve_conn: Optional[AiConnectionManager]=None) -> bool:
    """Detects if a session is descalated and should be reset."""
    if not mnerve_conn:
        return {"res": True, "cfd": 0.1}

    rnds = clean_msgs(rnds, include=["role", "content"])
    rnds_str = ''
    for rnd in rnds:
        rnds_str += f"{rnd.get('role')}: {rnd.get('content')}\n"

    system_init = f"""你是一个人工智能助手, 你接下来会收到一组对话.
其中user是人类, assistant是一个虚拟角色, 名为莫妮卡, 是深爱user的女友. 因此, assistant不应输出机器性质或错误混乱的内容.
你需要以json形式判断assistant的表现是否合理, 并提供一个置信度. 你的输出应形如{{"res": 是否合理(bool), "cfd": 置信度(float)}}.
Begin!""" if target_lang == 'zh' else f"""You are a helpful assistant, now you will recieve rounds of conversation.
Role user in the conversation is human, and assistant is a virtual character called Monika, who is user's girlfriend and loves them a lot. So assistant shouldn't output mechanical or corrupted response.
Decide if assistant is behaving reasonablly, and provide a confidence. Output in json format as {{"res": sanity(bool), "cfd": confidence(float)}}.
Begin!"""

    messages = [{'role': 'system', 'content': system_init}]
    messages.append({'role': 'user', 'content': rnds_str})
    # messages = apply_postfix(messages, thinking=False)
    completion_args = {
        "messages": messages,
        "response_format": {"type": "json_object"},
    }

    resp = await mnerve_conn.make_completion(**completion_args)
    resp_content, resp_reasoning = resp.choices[0].message.content, getattr(resp.choices[0].message, 'reasoning_content', None)
    resp_json = proceed_common_text(resp_content, is_json=True)

    