import re
import json
import asyncio
import traceback
import functools
from maica.maica_utils import *
from .mcp.mcp_serp import asearch
from openai import AsyncOpenAI # type: ignore

async def internet_search(fsc: FullSocketsContainer, query, original_query):
    target_lang = fsc.maica_settings.basic.target_lang

    for tries in range(0, 3):
        try:

            results = await asearch(query, target_lang)
            results = json.loads(results)
            results_sync = [{"title": it['title'], "text": it['snippet']} for it in results['searches'][0]['results']]
            assert len(results_sync), 'Search result is empty'
            # async for result_async in results_async:
            #     results_sync.append({"title": result_async.title, "text": result_async.description})
        except Exception:
            if tries < 2:
                await messenger(info=f'Search engine temporary failure, retrying {str(tries + 1)} time(s)')
                await asyncio.sleep(0.5)
            else:
                raise MaicaInternetWarning(f'Cannot get search result after {str(tries + 1)} times', '408')

    results_full = []
    results_short = []
    results_humane = ''
    rank = 0
    for item in results_sync:
        rank += 1
        title, text = clean_text(item['title']), clean_text(item['text'])
        results_full.append({'rank': rank, 'title': title, 'text': text})
        if rank <= 5:
            results_short.append({'rank': rank, 'title': title, 'text': text})
        if rank <= 3:
            humane_text = ReUtils.re_sub_serp_datetime.sub('', text, 1)
            results_humane += f'信息{rank}\n标题:{title}\n内容:{humane_text}\n'

    await messenger(info=f'MFocus got {rank} information lines from search engine', type=MsgType.DEBUG)

    results_full_str = str(results_full).strip('[').strip(']')
    results_short_str = str(results_short).strip('[').strip(']')
    if not fsc.maica_settings.extra.esc_aggressive:
        return results_short_str, results_humane

    system_init = """你是一个人工智能助手, 你接下来会收到一个问题和一些来自互联网的信息.
以单行不换行的自然语言的形式, 简洁地整理提供相关的信息. 如果你最终认为提供的信息与问题相关性不足, 返回false.
Begin!""" if target_lang == 'zh' else """You are a helpful assistant, now you will recieve a question and some information from the Internet.
Conclude related information briefly in a single line of natural sentence. If you think the provided information is not related enough to the question, return false.
Begin!"""

    messages = [{'role': 'system', 'content': system_init}]
    messages.append({'role': 'user', 'content': f'question: {query}; information: {results_full_str}'})
    completion_args = {
        "messages": messages,
    }

    resp = await fsc.mfocus_conn.make_completion(**completion_args)
    response = resp.choices[0].message.content
            
    await messenger(None, 'mfocus_internet_search', f"\nMFocus toolchain searching internet, response is:\n{response}\nEnd of MFocus toolchain searching internet", '201')
    
    answer_post_think = proceed_agent_response(response)
    return answer_post_think, answer_post_think

if __name__ == '__main__':
    async def test():
        fsc = FullSocketsContainer()
        fsc.mfocus_conn = await ConnUtils.mfocus_conn()
        print(await internet_search(fsc, "使用不同的语言会改变人的思考方式吗", "话说，莫妮卡，你觉得使用不同的语言会改变人的思考方式吗"))
    from maica import init
    init()
    asyncio.run(test())
