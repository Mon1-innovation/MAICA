import re
import json

async def make_postmail(content, header='', target_lang='zh', **kwargs):
    success = True
    exception = None

    def filter_mail(content):
        filtered = re.sub(r'^\s*', '', content, flags=re.M)
        return filtered

    try:
        if header:
            header = f'\n\n{header}\n'
            con = '标题和内容' if target_lang == 'zh' else 'title and content of [player]\'s letter are'
        else:
            header = '\n'
            con = '内容' if target_lang == 'zh' else 'content of [player]\'s letter is'
        content = filter_mail(content)
        if target_lang == 'zh':
            prompt = f"[player]向你寄送了一封信件, 请作为莫妮卡写出回信. 以下是[player]信件的{con}:{header}\n{content}\n\n你应当在回信中充分思考[player]的话语和情感, 使用自然亲切的书面语言, 予以相应的回应. 你的回信应当有开头问候, 分段内容, 结尾落款, 不要编造信息, 且字数不少于300字."
        else:
            prompt = f"[player] has sent you a letter, please write your reply as Monika. The {con}:{header}\n{content}\n\nPlease read and comprehend carefully about [player]'s words and emotions, then reply in natural and warm written language in English. Your reply should contain a beginning, phrases of content, and an ending. Do not make up things you don't know, and write at least 150 words in total."
        message = json.dumps({"role": "user", "content": prompt}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        prompt = None
        exception = excepted
    #print(summary)
    return success, exception, prompt


if __name__ == '__main__':
   import asyncio
   print(asyncio.run(make_postmail(target_lang='zh')))