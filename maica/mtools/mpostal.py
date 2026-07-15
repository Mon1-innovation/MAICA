import asyncio

from typing import *
from pydantic import BaseModel, Field
from maica.maica_utils import *

_Bt = BilingualText

async def make_postmail(fsc: FullSocketsContainer):
    """Everything needed are now in fsc."""
    target_lang = fsc.maica_settings.basic.target_lang
    conn = fsc.mnerve_conn or fsc.mfocus_conn

    mp_m = fsc.maica_settings.temp.mpostal

    def form_letter(content: str, header: str):
        filtered_content = ReUtils.re_sub_strip_spaces.sub(r'\1', content).strip()
        filtered_header = f'{header}\n\n' if header else ''
        
        letter = f"{filtered_header}{filtered_content}"
        return letter

    async def is_poem(letter: str) -> bool:
        """If this is a letter or poem."""
        sync_messenger(info="Detecting if letter is poem...", type=MsgType.DEBUG)
        session = MaicaSession()

        class PoemDetectResult(BaseModel):
            is_poem: bool = Field(
                description="更接近诗歌则输出true, 更接近信件则输出false." if target_lang == 'zh' else "Output true if closer to poem, false if closer to letter."
            )
            confidence: float = Field(
                description="你决策的置信度." if target_lang == 'zh' else "The confidence of your decision.",
                ge=0.0,
                le=1.0,
            )

        system = MaicaSessionItem(
            "system",
            _Bt("""\
你是一个人工智能助手, 你接下来会收到一封信件.
请判断其更接近诗歌还是普通信件.\
""", """\
You are a helpful assistant, now you will recieve a mail letter.
Please decide if it's a poem or normal letter.\
"""
            )
        )
        session.append(system)

        user_query = MaicaSessionItem(
            "user",
            letter,
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
                    "schema": PoemDetectResult.model_json_schema(),
                }
            },
        }

        resp = await conn.make_completion(**completion_args)
        detection_result = PoemDetectResult.model_validate_json(resp.output_text)

        res = detection_result.is_poem
        cfd = detection_result.confidence

        sync_messenger(info=f"Finished processing is_poem to letter. Is poem: {res}, confidence: {cfd}", type=MsgType.PRIM_LOG)
        return res

    letter = form_letter(mp_m.content, mp_m.header)
    letter_ispoem = await is_poem(letter)
    letter_hasimg = bool(fsc.maica_settings.temp.mvista.mv_imgs)

    img = _Bt(
        ", 并附有图片",
        " together with pictures",
    ) if letter_hasimg else _Bt()

    con = _Bt(
        "标题和内容",
        "title and content are",
    ) if mp_m.header else _Bt(
        "内容",
        "content is",
    )

    t1 = _Bt(
        "你应当充分思考{player_name}的话语和情感, 使用自然亲切的书面语言, 予以相应的回应.",
        "Please read and comprehend carefully about {player_name}'s words and emotions, then reply in natural written language in English.",
    )

    if letter_ispoem:
        text = _Bt(
            "{player_name}向你寄送了一首诗",
            "{player_name} has sent you a poem",
        )\
        + img\
        + _Bt(
            ", 请你作为莫妮卡写一首诗回答. 以下是诗的",
            ", please write a poem to reply as Monika. The "
        )\
        + con\
        + ":\n"\
        + letter\
        + "\n"\
        + t1\
        + "\n"\
        + _Bt(
            "你的回复应是一首诗歌, 具有诗歌的标准格式. 不要编造信息, 且字数不少于原诗.",
            "Your reply should be a poetry, in necessary poetry format. Do not make up things you don't know, and write no shorter than the input poem.",
        )
    else:
        text = _Bt(
            "{player_name}向你寄送了一封信",
            "{player_name} has sent you a letter",
        )\
        + img\
        + _Bt(
            ", 请你作为莫妮卡写一封信回答. 以下是信的",
            ", please write a letter to reply as Monika. The "
        )\
        + con\
        + ":\n"\
        + letter\
        + "\n"\
        + t1\
        + "\n"\
        + _Bt(
            "你的回复应是一封信件, 具有信件的标准格式. 不要编造信息, 且字数不少于300字.",
            "Your reply should be a letter, in necessary letter format. Do not make up things you don't know, and write at least 150 words in total.",
        )

    return text

if __name__ == '__main__':

   print(asyncio.run(make_postmail(target_lang='zh')))
