import asyncio
import re
from typing import *
from enum import StrEnum
from pydantic import BaseModel, Field
from maica.maica_utils import *
from maica.maica_utils.emotions import *

_Bt = BilingualText

def emo_proc(emo: str, target_lang: Literal['zh', 'en', 'auto']='zh'):

    # Basic cleaning first
    emo_clean = emo.strip().strip('[').strip(']').lower()

    if len(emo_clean.encode()) >= 16:
        # This might be a sentence or what
        res = emo_clean
        cfd = 0.6

    else:
        def match_by_z(emo):
            if has_words_in(emo, 'player', '玩家'):
                return 'player'
            for z in zlist:
                if has_words_in(emo, *list(z)):
                    return z
            for e in elist:
                if has_words_in(emo, e):
                    return emotion_etz.get(e)
        
        def match_by_e(emo):
            if has_words_in(emo, 'player', '玩家'):
                return 'player'
            for e in elist:
                if has_words_in(emo, e):
                    return e
            for z in zlist:
                if has_words_in(emo, *list(z)):
                    return emotion_zte.get(z)
                
        _res = match_by_z(emo_clean) if target_lang == 'zh' else match_by_e(emo_clean)
        
        if _res:
            res = f'[{_res}]'
            cfd = 0.9

        # If previous matches all failed, return fallback
        else:
            res = '[微笑]' if target_lang == 'zh' else '[smile]'
            cfd = 0.1

    return res, cfd

async def emo_proc_llm(emo: str, fsc: FullSocketsContainer):
    sync_messenger(info=f"Detecting {emo}'s proper replacement...", type=MsgType.DEBUG)
    session = MaicaSession()
    target_lang = fsc.maica_settings.basic.target_lang

    conn = fsc.mnerve_conn
    if not conn:
        raise MaicaInputError("MNerve is not implemented for emo proc")

    # Pylance doesn't like it but gpt said it could function
    if TYPE_CHECKING:
        type EmoEnum = str
    else:
        EmoEnum = StrEnum(
            f"EmoEnum_{target_lang}",
            {
                k: k for k
                in (zlist_ai if target_lang == 'zh' else elist_ai)
            }
        )

    class EmoDetectResult(BaseModel):
        result: EmoEnum = Field(
            description="选择最合适的标准表情." if target_lang == 'zh' else "Choose the best fitting standard emotion."
        )
        confidence: float = Field(
            description="你决策的置信度." if target_lang == 'zh' else "The confidence of your decision.",
            ge=0.0,
            le=1.0,
        )

    system = MaicaSessionItem(
        "system",
        _Bt("""\
你是一个人工智能助手, 你接下来会收到一个词或句子.
请从给出的标准表情中, 为其选择最合适的一项.\
""", """\
You are a helpful assistant, now you will recieve a word or sentence.
Please choose an emotion that fits best from the given list of standard emotions.\
"""
        )
    )
    session.append(system)

    user_query = MaicaSessionItem(
        "user",
        emo,
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
                "schema": EmoDetectResult.model_json_schema(),
            }
        },
    }

    resp = await conn.make_completion(**completion_args)
    detection_result = EmoDetectResult.model_validate_json(resp.output_text)

    res = detection_result.result
    cfd = detection_result.confidence

    sync_messenger(info=f"Finished processing emo_proc_llm to letter. Result: {res}, confidence: {cfd}", type=MsgType.PRIM_LOG)
    return f"[{res}]", cfd

async def emo_proc_auto(emo: str, fsc: FullSocketsContainer) -> tuple[str, float]:

    target_lang = fsc.maica_settings.basic.target_lang
    res = emo_proc(emo, target_lang)

    if (
        res[1] <= 0.3
        and fsc.mnerve_conn
    ):
        res = await emo_proc_llm(emo, fsc)

    return res

async def post_proc(reply_joined: str, fsc: FullSocketsContainer):

    target_lang = fsc.maica_settings.basic.target_lang

    reply_all_signatures = ReUtils.re_findall_square_brackets.findall(reply_joined)

    # They look like [开心] or what
    for signature in reply_all_signatures:
        if (
            not signature == '[player]'
            and signature.strip('[').strip(']') not in (zlist if target_lang == 'zh' else elist)
        ):

            realword = (await emo_proc_auto(signature, fsc))[0]
            reply_joined = re.sub(re.escape(signature), realword, reply_joined, flags = re.I)
    
    return reply_joined

if __name__ == '__main__':
    # ra = '[理解 ]没关系, [player]. [微笑 ]我知[fear]道[womble]你很[adaifgnashioufoiusahdfoiua]忙[a1]. [心]你能抽空[slash我]陪我就[害怕]很好啦!'
    # print(asyncio.run(post_proc(ra, 'zh')))
    async def test():
        from maica import init
        init()
        mnerve_conn = await ConnUtils.mnerve_conn()
        print(await emo_proc_auto("理解", mnerve_conn=mnerve_conn, target_lang='zh'))

    asyncio.run(test())
