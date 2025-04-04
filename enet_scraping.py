import re
import traceback
import functools
from loadenv import load_env
from googlesearch import asearch
from openai import AsyncOpenAI # type: ignore

async def internet_search(query, original_query, esc_aggressive=True, target_lang='zh'):
    success = True
    exception = None
    try:
    # Here goes the search module
    # Highly unstable I would say
    # Fuck google
        searched_aiolist = asearch(query, advanced=True, proxy=load_env("PROXY_ADDR"))
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
            system_init = """你是一个人工智能助手, 你的任务是分析和检索信息. 你接下来会收到一个问题和一些来自互联网的信息.
请你将这些信息整理为一条内容总结, 用以回答问题. 如果你最终认为没有信息符合条件, 回答None.
注意不要编造信息, 并以单行自然语言的形式, 输出客观可信的总结.
使用以下格式回答:
Thought: 简要地思考以上信息关于何种内容, 与内容是否存在相关性, 以及如何从中选取.
Answer: 将你认为有用的信息整理总结, 并以单行自然语言的形式输出. 如果你最终认为没有信息符合条件, 回答None.
Begin!""" if target_lang == 'zh' else """You are a helpful assistant, your task is sorting and analyzing information. Now you will recieve a question and some information from the Internet.
Please conclude the information into a brief sentence that helps answering the question. If you think no information provided is helpful, return None.
Remember not to make up information not mentioned. Output a single natural sentence that is objective and dependable.
Answer in the following format:
Thought: Think briefly what the information provided are about, how the information is related with the question, and how to make a conclusion.
Answer: Output you conclusion in a single natural sentence. If you think no information provided is helpful at last, answer None.
Begin!"""
            messages = [{'role': 'system', 'content': system_init}]
            messages.append({'role': 'user', 'content': f'question: {original_query}; information: {slt_full}'})
            completion_args = {
                "model": model_type,
                "messages": messages,
                "temperature": 0.2,
                "top_p": 0.6,
                "presence_penalty": -0.5,
                "frequency_penalty": 0.5,
                "seed": 42
            }

            for tries in range(0, 2):
                try:
                    resp = await client.chat.completions.create(**completion_args)
                    response = resp.choices[0].message.content
                except:
                    if tries < 1:
                        print('Model temporary failure')
                        await asyncio.sleep(500)
                    else:
                        raise Exception('Model connection failure')

        print(f"MFocus enet searching internet, response is:\n{response}\nEnd of MFocus enet searching internet")
        answer_re = re.search(r'Answer\s*:\s*(.*)', response, re.I)
        if answer_re:
            if not re.match(r'\s*none', answer_re[1], re.I):
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
    searched = asyncio.run(internet_search('24奥运会','你知道24年奥运会在哪里吗', esc_aggressive=True))
    print(searched)
