import re
import traceback
import functools
from loadenv import load_env
from googlesearch import search
from openai import AsyncOpenAI # type: ignore

async def internet_search_limb(query, original_query, esc_aggressive=True):
    success = True
    exception = None
    try:
    # Here goes the search module
    # Highly unstable I would say
    # Fuck google
        searched_aiolist = search(query, advanced=True, proxy=load_env("PROXY_ADDR"))
        results = []
        async for searched_item in searched_aiolist:
            results.append({"title": searched_item.title, "text": searched_item.description})
    except:
        traceback.print_exc()
        success = False
        exception = "Search failed"
        slt_default = slt_humane = ''
        return success, exception, slt_default, slt_humane
    slt_full = []
    slt_default = []
    slt_humane = ''
    rank = 0
    for item in results:
        rank += 1
        title = item['title']
        title = title.replace('\n',' ')
        text = re.sub(r'.*?(?=[\u4e00-\u9fa5])', '', item['text'], 1, re.I)
        text = text.replace('\n',' ')
        slt_full.append({'rank': rank, 'title': title, 'text': text})
        if rank <= 5:
            slt_default.append({'rank': rank, 'title': title, 'text': text})
        if rank <= 3:
            slt_humane += f'信息{rank}\n标题:{title}\n内容:{text}\n'
    slt_full = str(slt_full)
    print(slt_full)
    slt_default = str(slt_default).strip('[').strip(']')
    if not esc_aggressive:
        return True, None, slt_default, slt_humane
    try:
        async with AsyncOpenAI(
            api_key='EMPTY',
            base_url=load_env('MFOCUS_ADDR'),
            ) as client:
            model_list = await client.models.list()
            model_type = model_list.data[0].id
            print(f'MFocus enet addressing model, response is:\n{model_type}\nEnd of MFocus enet addressing model')
            system_init = """你是一个人工智能助手, 你的任务是整理信息. 你接下来会收到一个问题和一些来自搜索引擎的信息.
请你将这些信息整理为一条内容总结, 用以回答问题. 请不要编造信息, 并以单行自然语言的形式, 使用信息中的语言返回.
如果你最终没有找到有意义, 可以回答问题的信息, 请返回none.
使用以下格式回答:
Thought: 简要地思考以上信息关于何种内容, 与内容是否存在相关性.
Try: 尝试将你的总结以单行自然语言的形式返回.
Thought Again: 再次思考上面输出的信息. 如果其中存在广告, 无意义, 无知识性, 无时效性或与问题无关的内容, 则将其去除.
Answer: 最终将信息以单行自然语言的形式返回. 如果没有找到任何有用信息, 则返回none.
Begin!
"""
            messages = [{'role': 'system', 'content': system_init}]
            messages.append({'role': 'user', 'content': f'query: {original_query}; information: {slt_full}'})
            completion_args = {
                "model": model_type,
                "messages": messages,
                "temperature": 0.1,
                "top_p": 0.6,
                "presence_penalty": -0.5,
                "frequency_penalty": 0.5,
                "seed": 42
            }
            resp = await client.chat.completions.create(**completion_args)
            response = resp.choices[0].message.content
        print(f"MFocus enet searching internet, response is:\n{response}\nEnd of MFocus enet searching internet")
        answer_re = re.search(r'Answer\s*:\s*(.*)', response, re.I)
        if answer_re:
            if not re.match('none', answer_re[1], re.I):
                slt_humane = slt_default = answer_re[1]
            else:
                slt_humane = ''; slt_default = 'None'
        # If corrupted we proceed anyway
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        exception = excepted
        slt_default = slt_humane = ''
    return success, exception, slt_default, slt_humane

if __name__ == '__main__':
    import asyncio
    import time
    searched = asyncio.run(internet_search_limb('24奥运会','你知道24年奥运会在哪里吗', esc_aggressive=True))
    print(searched)
