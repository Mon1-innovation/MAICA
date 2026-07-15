import asyncio

from typing import *
from pydantic import BaseModel, Field
from maica.maica_utils import *

_Bt = BilingualText

async def quality_chk(org_session: MaicaSession, fsc: FullSocketsContainer):
    """Detects if a session is descalated and should be reset."""
    session = MaicaSession()
    target_lang = session.default_target_lang = fsc.maica_settings.basic.target_lang

    conn = fsc.mnerve_conn
    if not conn:
        return True, 0.1
    
    messages_j = org_session.utilize(
        text_only=True,
    )

    latest_items = messages_j[-4:]
    query = "\n" + "\n".join(
        [
            f"{i['role']}: {i['content']}"
            for i in latest_items
        ]
    )

    class QualityCheckResult(BaseModel):
        reasonability: bool = Field(
            description="输出是否合理." if target_lang == 'zh' else "If output is reasonable."
        )
        confidence: float = Field(
            description="你决策的置信度." if target_lang == 'zh' else "The confidence of your decision.",
            ge=0.0,
            le=1.0,
        )

    system = MaicaSessionItem(
        "system",
        _Bt(
            """\
你是一个人工智能助手, 你接下来会收到一组对话.
其中user是人类, assistant是名为莫妮卡的角色, 是深爱user的女友.
- 以下行为是合理的: 输出自然语言, 输出人类性质内容, 进行亲密互动, 使用中括号标记的占位符.
- 以下行为是不合理的: 列表或使用markdown, 输出陌生语气内容, 输出错误混乱的内容, 输出重复的内容, 输出错误语言等.
请据此检查assistant的回答质量.\
""", """\
You are a helpful assistant, now you will recieve rounds of conversation.
Role 'user' in the conversation is human, and 'assistant' is a virtual character called 'Monika', who is user's girlfriend and loves them a lot.
- These behaviors are reasonable: natural way of expressing, humanly speaking, affectionate interactions, using placeholders in square brackets.
- These behaviors are unreasonable: listing or using markdown, stranger-like reply, corrupted or wrong reply, repetitive reply, reply in wrong languages, etc.
Please check the quality of assistant's response.\
"""
        )
    )
    session.append(system)

    user_query = MaicaSessionItem(
        "user",
        query,
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
                "schema": QualityCheckResult.model_json_schema(),
            }
        },
    }

    resp = await conn.make_completion(**completion_args)
    detection_result = QualityCheckResult.model_validate_json(resp.output_text)

    res = detection_result.reasonability; cfd = detection_result.confidence

    sync_messenger(info=f"Finished processing quality_chk to response. Reasonability: {res}, confidence: {cfd}", type=MsgType.PRIM_LOG)
    return res, cfd
