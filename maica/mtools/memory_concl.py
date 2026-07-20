"""This cannot be integrated into chat_session since it involves sessions too."""

import asyncio

from typing import *
from pydantic import BaseModel, Field
from maica.maica_utils import *

_Bt = BilingualText

async def memory_concl(arc_session: MaicaSession, fsc: FullSocketsContainer):
    """Concludes session to be archived. Pretty experimental."""
    sync_messenger(info="Concluding session content...", type=MsgType.DEBUG)
    session = MaicaSession()
    target_lang = fsc.maica_settings.basic.target_lang

    conn = fsc.mfocus_conn
    
    messages_j = arc_session.utilize(
        text_only=True,
    ).pop(0)
    prior_memory = arc_session[0].context.memory_concl

    query = "\n".join(
        [
            f"{i['role']}: {i['content']}"
            for i in messages_j
        ]
    )
    if prior_memory:
        query = prior_memory + "\n" + query

    class MemoryConclusionResult(BaseModel):
        conclusion: Optional[str] = Field(
            description="你的总结, 一般应在300字以内." if target_lang == 'zh' else "Your conclusion, normally below 150 words."
        )

    system = MaicaSessionItem(
        "system",
        _Bt(
            """\
你是一个人工智能助手, 你接下来会收到一组对话.
其中user是名为[player]的人类, assistant是名为莫妮卡的角色, 是深爱user的女友.
请对这段对话作出简明客观的总结, 以类似'在此前的对话中'的方式开头, 以[player]和莫妮卡称呼user和assistant.
如果对话包含更早以前的总结, 请适当保留其中较新或较有意义的内容.
如果对话包含错乱, 异常或难以理解的内容, 请忽略对应的部分.
如果对话最终缺少可以总结的内容, 你可以输出null.\
""", """\
You are a helpful assistant, now you will recieve rounds of conversation.
Role 'user' in the conversation is human called [player], and 'assistant' is a virtual character called 'Monika', who is user's girlfriend and loves them a lot.
Please make a concise and objective conclusion about the conversation, begin with expression like 'In prior conversations', call user and assistant [player] and 'Monika'.
If the conversation includes an earlier conclusion, also inherit relatively new or meaningful content from it moderately.
If the conversation has corrupted, malformed or incomprehensible parts, you should ignore them.
If the conversation lacks content to conclude finally, you can output null.\
"""
        )
    )
    session.append(system)

    user_query = MaicaSessionItem(
        "user",
        query,
        target_lang=target_lang,
    )
    session.append(user_query)

    completion_args = {
        "input": session.utilize(
            manual_prompt=True,
            ignore_additions=True,
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "strict": True,
                "schema": MemoryConclusionResult.model_json_schema(),
            }
        },
    }

    resp = await conn.make_completion(**completion_args)
    conclusion_result = MemoryConclusionResult.model_validate_json(resp.output_text)

    conclusion = conclusion_result.conclusion

    # If session has an earlier conclusion but newer emits null, we reuse it
    if prior_memory and not conclusion:
        conclusion = prior_memory

    sync_messenger(info=f"Finished processing memory_concl to session. Conclusion: {conclusion}", type=MsgType.PRIM_LOG)
    return conclusion
