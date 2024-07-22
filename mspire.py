import re
import json
import traceback
import wiki_scraping
from openai import OpenAI

def make_inspire(title_in=None, target_lang='zh'):
    success = True
    exception = None
    try:
        title, summary = wiki_scraping.get_page(title_in, target_lang)
        if not summary or summary.isspace():
            raise Exception('MSpire got no return')
        if target_lang == 'zh':
            prompt = f"利用提供的以下信息, 主动和我简单地聊聊{re.sub('_', '', title)}: {summary} 你只应使用自然语言, 以聊天语气对话, 并在每句开始时以方括号中的文字表示情绪."
        else:
            prompt = f"Talk about {re.sub('_', '', title)} briefly with me using provided informations below: {summary} You should only answer in casual natural tone with English, and express your emotion at the beginning of each sentence by wrapping them in square brackets."
        message = json.dumps({"role": "user", "content": prompt}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        exception = excepted
    #print(summary)
    return success, exception, prompt


if __name__ == '__main__':
   print(make_inspire(target_lang='en')[2])