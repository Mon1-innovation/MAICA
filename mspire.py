import re
import json
import traceback
import wiki_scraping
from openai import AsyncOpenAI

def make_inspire(title_in=None, target_lang='zh'):
    success = True
    exception = None
    try:
        title, summary = wiki_scraping.get_page(title_in, target_lang)
        if not summary or summary.isspace():
            raise Exception('MSpire got no return')
        if target_lang == 'zh':
            prompt = f"利用提供的以下信息, 主动和我简单地聊聊{re.sub('_', '', title)}: {summary} 你应当在输出中融入自己的理解与思考."
        else:
            prompt = f"Talk about {re.sub('_', '', title)} briefly with me using provided informations below: {summary} You should combine your own thinking and understanding into your outputs."
        message = json.dumps({"role": "user", "content": prompt}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        exception = excepted
    #print(summary)
    return success, exception, prompt


if __name__ == '__main__':
   print(make_inspire(target_lang='zh')[2])