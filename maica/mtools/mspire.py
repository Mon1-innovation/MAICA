import re
import json
import traceback
from . import wiki_scraping
from openai import AsyncOpenAI
from maica.maica_utils import *

async def make_inspire(title_in=None, target_lang='zh'):
    success = True
    exception = None
    try:
        title, summary = await wiki_scraping.get_page(title_in, target_lang)
        if not summary or summary.isspace():
            raise Exception('MSpire got no return')
        if target_lang == 'zh':
            prompt = f"利用提供的以下信息, 主动阐明话题并简单地聊聊{re.sub('_', '', title)}:\n\n{summary}\n\n你不必在输出中包含内容的全部信息, 但应当融入自己的理解与思考. 你的回答应当有开头招呼, 表现为由你自主发起话题, 并使用自然有感情的聊天语气. 你应当从你自己的角度思考, 不应盲从信息中的评价和判断."
        else:
            prompt = f"Summarize the topic and talk about {re.sub('_', '', title)} briefly with me using provided informations below: {summary}\nYou don't have to include all information provided, but you should combine your own thinking and understanding into your response. Your reply should contain a greeting and brief introduction, act as you started the conversation with this topic, and always use natural emotional tone. You should think from your own perspective, avoid blindly following the judgements from the information."
        #message = json.dumps({"role": "user", "content": prompt}, ensure_ascii=False)
        hash_identity = await hash_sha256(prompt.encode())
        #print(hash_identity)
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        exception = excepted
        prompt = None
        hash_identity = None
    #print(summary)
    return success, exception, prompt, hash_identity


if __name__ == '__main__':
   import asyncio
   print(asyncio.run(make_inspire(target_lang='zh')))