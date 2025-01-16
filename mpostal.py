import json

async def make_postmail(content, header='', target_lang='zh', **kwargs):
    success = True
    exception = None
    try:
        if header:
            header += '\n'
            con = '标题和内容' if target_lang == 'zh' else 'title and content'
        else:
            con = '内容' if target_lang == 'zh' else 'content'
        if target_lang == 'zh':
            prompt = f"[player]向你寄送了一封信件, 以下是信件的{con}:\n\n{header}{content}\n\n请你仔细理解和思考用户的言语, 根据你自己的见解和情感, 以自然语言写出回信."
        else:
            prompt = f"[player] has sent you a letter, the {con} are:\n\n{header}{content}\n\nPlease read and comprehend carefully about [player]'s words, and write your reply letter with your own emotion and thoughts in nature tone in English."
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