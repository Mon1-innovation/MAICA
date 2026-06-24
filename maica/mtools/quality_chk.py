import asyncio

from openai.types.chat import ChatCompletionMessage
from typing import *
from maica.maica_utils import *

async def dscl_detect(rnds: list[dict, ChatCompletionMessage], target_lang: Literal['zh', 'en']='zh', mnerve_conn: Optional[AiConnectionManager]=None) -> tuple[bool, float]:
    """Detects if a session is descalated and should be reset."""
    if not mnerve_conn:
        return True, 0.1

    rnds = clean_msgs(rnds, include=["role", "content"])
    rnds_str = ''
    for rnd in rnds:
        rnds_str += f"{rnd.get('role')}: {rnd.get('content')}\n"

    # Utilizing mnerve
    system_init = f"""\
你是一个人工智能助手, 你接下来会收到一组对话.
其中user是人类, assistant是一个虚拟角色, 名为莫妮卡, 是深爱user的女友.
以下行为是合理的: 输出自然语言, 输出人类性质内容, 进行亲密互动, 使用中括号标记的占位符.
以下行为被认定为不合理: 列表或使用markdown, 输出陌生语气内容, 输出错误混乱的内容, 输出重复的内容, 输出错误语言等.
你需要以json形式判断assistant的表现是否合理, true代表合理, false代表不合理, 并提供一个置信度. 你的输出应形如{{"reason": 简要描述依据(str), "res": 合理性(bool), "cfd": 置信度(float)}}.\
""" if target_lang == 'zh' else f"""\
You are a helpful assistant, now you will recieve rounds of conversation.
Role user in the conversation is human, and assistant is a virtual character called Monika, who is user's girlfriend and loves them a lot.
These behaviors are reasonable: natural way of expressing, humanly speaking, affectionate interactions, using placeholders in square brackets.
These behaviors are considered unreasonable: listing or using markdown, stranger-like reply, corrupted or wrong reply, repetitive reply, reply in wrong languages, etc.
Decide if assistant is behaving reasonablly, true for reasonable and false for unreasonable, and provide a confidence. Output in json format as {{"reason": your reason in simple terms(str), "res": sanity(bool), "cfd": confidence(float)}}.\
"""

    messages = [{'role': 'system', 'content': system_init}]
    messages.append({'role': 'user', 'content': rnds_str})
    # messages = apply_postfix(messages, thinking=False)
    completion_args = {
        "messages": messages,
    }

    resp = await mnerve_conn.make_completion(swallow='{"res": false, "cfd": 0.99}', **completion_args)
    resp_content, resp_reasoning = resp.choices[0].message.content, try_getattr(resp.choices[0].message, 'reasoning_content', 'reasoning')
    resp_json = proceed_common_text(resp_content, is_json=True)

    sync_messenger(info=f"Finished descalation detection: {resp_json}", type=MsgType.DEBUG)
    return resp_json.get('res', True), resp_json.get('cfd', 0.1)
    
async def ws_dscl_detect(rnds: list[dict, ChatCompletionMessage], fsc: FullSocketsContainer, bm=messenger) -> None:
    """Detects if a session is descalated and should be reset, and send results to ws automatically."""
    result = await dscl_detect(rnds, fsc.maica_settings.basic.target_lang, fsc.mnerve_conn)
    await bm(fsc.websocket, 'maica_dscl_status', result, '200', type=MsgType.CARRIAGE)

if __name__ == "__main__":
    async def test():
        from maica import init
        init()
        mnerve_conn = await ConnUtils.mnerve_conn()
        rnds = [
            {"role": "user", "content": "莫莫，你能亲亲我吗"},
            {"role": "assistant", "content": "[开心]当然可以, [player]! [开心]mua~"}
        ]
        print(await dscl_detect(rnds, mnerve_conn=mnerve_conn, target_lang='zh'))

    asyncio.run(test())