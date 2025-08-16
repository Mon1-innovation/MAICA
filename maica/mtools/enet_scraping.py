import re
import traceback
import functools
from maica_utils import *
from googlesearch import asearch
from openai import AsyncOpenAI # type: ignore

async def internet_search(query, original_query, esc_aggressive=True, target_lang='zh'):
    success = True
    exception = None
    for tries in range(0, 3):
        try:
        # Here goes the search module
        # Highly unstable I would say
        # Fuck google
            searched_aiolist = asearch(query, advanced=True, proxy=load_env("PROXY_ADDR"))
            results = []
            async for searched_item in searched_aiolist:
                results.append({"title": searched_item.title, "text": searched_item.description})
        except:
            if tries < 2:
                print('Search temporary failure')
                await asyncio.sleep(0.5)
            else:
                print('Search connection failure')
                #traceback.print_exc()
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
            system_init = """你是一个人工智能助手, 你接下来会收到一个问题和一些来自互联网的信息.
以单行不换行的自然语言的形式, 回答用户的原始问题, 并整理提供相关的信息. 如果你最终认为提供的信息不足以作答, 仅回答None.
Begin!""" if target_lang == 'zh' else """You are a helpful assistant, now you will recieve a question and some information from the Internet.
Answer the question in a single line of natural sentence, and conclude and offer related information briefly. If you think the provided information is not enough finally, answer None.
Begin!"""
            messages = [{'role': 'system', 'content': system_init}]
            messages.append({'role': 'user', 'content': f'question: {original_query}; information: {slt_full}'})
            # messages[-1]['content'] += '/think'
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
                        await asyncio.sleep(0.5)
                    else:
                        raise Exception('Model connection failure')

        print(f"MFocus enet searching internet, response is:\n{response}\nEnd of MFocus enet searching internet")
        answer_re = re.search(r'</think>[\s\n]*(.*)', response, re.I|re.S)
        if answer_re:
            if not re.match(r'\s*none', answer_re[1], re.I):
                slt_humane = slt_default = re.sub(r'\n+', '; ', re.sub(r'\*+', '', answer_re[1], 0, re.I), 0, re.I|re.S)
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
    searched = asyncio.run(internet_search('24奥运会','Where did 2024 Olympics take place?', esc_aggressive=True, target_lang='en'))
    print(searched)
