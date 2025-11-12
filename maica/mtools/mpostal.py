import re
import json
import asyncio

from typing import *
from maica.maica_utils import *

async def make_postmail(content: str, header: str, fsc: FullSocketsContainer, **kwargs):
    target_lang = fsc.maica_settings.basic.target_lang
    mnerve_conn = fsc.mnerve_conn

    def form_letter(content, header):
        filtered_content = re.sub(r'^\s*', '', content, flags=re.M)
        filtered_header = f'\n\n{header}\n' if header else '\n'
        
        letter = f"{filtered_header}\n{filtered_content}\n\n"
        return letter

    async def is_poem(letter, target_lang, mnerve_conn) -> bool:
        """Use MNerve to determine if input is a poem."""
        if not mnerve_conn:
            return None
        
        sync_messenger(info=f"Proceeding 'is_poem' to letter '{header}'...", type=MsgType.PRIM_RECV)
        
        system_init = f"""你是一个人工智能助手, 你接下来会收到一封信件.
你只需以json形式判断其是否属于诗歌, 体裁不限. 你的输出应形如{{"is_poem": 是否是诗歌(bool)}}.
Begin!""" if target_lang == 'zh' else f"""You are a helpful assistant, now you will recieve a mail letter.
You just have to decide if it's a poem or not, whatever type of poem it is. Output in json format as {{"is_poem": is poem or not(bool)}}.
Begin!"""
        messages = [{'role': 'system', 'content': system_init}]
        messages.append({'role': 'user', 'content': letter})
        completion_args = {
            "messages": messages,
            "response_format": {"type": "json_object"},
        }

        resp = await mnerve_conn.make_completion(**completion_args)
        resp_content, resp_reasoning = resp.choices[0].message.content, getattr(resp.choices[0].message, 'reasoning_content', None)
        resp_json = proceed_common_text(resp_content, is_json=True)

        sync_messenger(info=f"Finished processing 'is_poem' to letter '{header}': {resp_json}", type=MsgType.CARRIAGE)
        return resp_json.get('is_poem')

    letter = form_letter(content, header)
    letter_ispoem = await is_poem(letter, target_lang, mnerve_conn)
    letter_hasimg = bool(fsc.maica_settings.temp.mv_imgs)
    img = ""
    if letter_hasimg:
        img = ", 并附有图片" if target_lang == 'zh' else " together with pictures"

    if letter_ispoem:
        if header:
            con = '标题和内容' if target_lang == 'zh' else 'title and content of [player]\'s poem are'
        else:
            con = '内容' if target_lang == 'zh' else 'content of [player]\'s poem is'

        if target_lang == 'zh':
            prompt = f"[player]向你寄送了一首诗{img}, 请你作为莫妮卡写一首诗回答. 以下是[player]诗的{con}:{letter}你应当充分思考[player]的话语和情感, 使用自然亲切的书面语言, 予以相应的回应.\n你的回复应是一首诗歌, 具有诗歌的标准格式. 不要编造信息, 且字数不少于原诗."
        else:
            prompt = f"[player] has sent you a poem{img}, please write a poem to reply as Monika. The {con}:{letter}Please read and comprehend carefully about [player]'s words and emotions, then reply in natural written language in English.\nYour reply should be a poetry, in necessary poetry format. Do not make up things you don't know, and write no shorter than the input poem."

    else:
        if header:
            con = '标题和内容' if target_lang == 'zh' else 'title and content of [player]\'s letter are'
        else:
            con = '内容' if target_lang == 'zh' else 'content of [player]\'s letter is'

        if target_lang == 'zh':
            prompt = f"[player]向你寄送了一封信件{img}, 请你作为莫妮卡写一封回信. 以下是[player]信件的{con}:{letter}你应当充分思考[player]的话语和情感, 使用自然亲切的书面语言, 予以相应的回应.\n你的回复应是一封信件, 具有信件的标准格式. 不要编造信息, 且字数不少于300字."
        else:
            prompt = f"[player] has sent you a letter{img}, please write a letter to reply as Monika. The {con}:{letter}Please read and comprehend carefully about [player]'s words and emotions, then reply in natural written language in English.\nYour reply should be a letter, in necessary letter format. Do not make up things you don't know, and write at least 150 words in total."

    # message = json.dumps({"role": "user", "content": prompt}, ensure_ascii=False)
    return prompt

if __name__ == '__main__':

   print(asyncio.run(make_postmail(target_lang='zh')))