import asyncio
import re
from typing import *
from enum import StrEnum
from pydantic import BaseModel, Field
from maica.maica_utils import *

emotion_etz = {
    "smile": "微笑",
    "happy": "开心",
    "worry": "担心",
    "grin": "笑",
    "think": "思考",
    "angry": "生气",
    "blush": "脸红",
    "gaze": "凝视",
    "upset": "沉重",
    "daydreaming": "憧憬",
    "surprise": "惊喜",
    "awkward": "尴尬",
    "meaningful": "意味深长",
    "unexpected": "惊讶",
    "relaxed": "轻松",
    "shy": "害羞",
    "eagering": "急切",
    "proud": "得意",
    "dissatisfied": "不满",
    "serious": "严肃",
    "touched": "感动",
    "excited": "激动",
    "love": "宠爱",
    "wink": "眨眼",
    "sad": "伤心",
    "disgust": "厌恶",
    "fear": "害怕",
    "kawaii": "可爱",
    "smiling": "微笑",
    "worrying": "担心",
    "grinning": "笑",
    "thinking": "思考",
    "gazing": "凝视",
    "surprised": "惊喜",
    "relaxing": "轻松",
    "eager": "急切",
    "winking": "眨眼",
    "disgusting": "厌恶",
    "fearing": "害怕"
}
emotion_zte = {
    "微笑": "smile",
    "开心": "happy",
    "担心": "worry",
    "笑": "grin",
    "思考": "think",
    "生气": "angry",
    "脸红": "blush",
    "凝视": "gaze",
    "沉重": "upset",
    "憧憬": "daydreaming",
    "惊喜": "surprise",
    "尴尬": "awkward",
    "意味深长": "meaningful",
    "惊讶": "unexpected",
    "轻松": "relaxed",
    "害羞": "shy",
    "急切": "eagering",
    "得意": "proud",
    "不满": "dissatisfied",
    "严肃": "serious",
    "感动": "touched",
    "激动": "excited",
    "宠爱": "love",
    "眨眼": "wink",
    "伤心": "sad",
    "厌恶": "disgust",
    "害怕": "fear",
    "可爱": "kawaii"
}

# Valid lists
elist = list(emotion_etz.keys())
zlist = list(emotion_zte.keys())

# Remove duplications from en
# And remove misleading emos
elist_ai = [
    i for i
    in set(emotion_zte.values())
    if not i in ('kawaii', )
]
zlist_ai = [
    i for i
    in emotion_zte.keys()
    if not i in ('可爱', )
]

_Bt = BilingualText

def emo_proc(emo: str, target_lang: Literal['zh', 'en', 'auto']='zh'):

    # Basic cleaning first
    emo_clean = emo.strip().strip('[').strip(']').lower()

    if len(emo_clean.encode()) >= 16:
        # This might be a sentence or what
        res = emo_clean; cfd = 0.6

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
            res = f'[{_res}]'; cfd = 0.9

        # If previous matches all failed, return fallback
        else:
            res = '[微笑]' if target_lang == 'zh' else '[smile]'; cfd = 0.1

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

    res = detection_result.result; cfd = detection_result.confidence

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
            and not signature.strip('[').strip(']') in (zlist if target_lang == 'zh' else elist)
        ):

            realword = await emo_proc_auto(signature, fsc)[0]
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