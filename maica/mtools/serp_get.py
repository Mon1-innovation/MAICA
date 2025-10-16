import re
import json
import asyncio
import traceback
import functools

from maica.maica_utils import *
from . import providers

async def internet_search(fsc: FullSocketsContainer, query, original_query):
    target_lang = fsc.maica_settings.basic.target_lang

    for tries in range(0, 3):
        try:
            results_sync = await (providers.get_asearch())(query, target_lang)
            assert len(results_sync), 'Search result is empty'
            break
        except Exception as e:
            if tries < 2:
                await messenger(info=f'Search engine temporary failure, retrying {str(tries + 1)} time(s)')
                await asyncio.sleep(0.5)
            else:
                raise MaicaInternetWarning(f'Cannot get search result after {str(tries + 1)} times', '408') from e

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
    messages = apply_postfix(messages, thinking=False)
    completion_args = {
        "messages": messages,
    }

    resp = await fsc.mfocus_conn.make_completion(**completion_args)
    resp_content, resp_reasoning = resp.choices[0].message.content, getattr(resp.choices[0].message, 'reasoning_content')
    resp_content, resp_reasoning = clean_text(resp_content), clean_text(resp_reasoning)
    if not has_valid_content(resp_content):
        resp_content = None
    if not has_valid_content(resp_reasoning):
        resp_reasoning = None            
    await messenger(None, 'mfocus_internet_search', f"\nMFocus toolchain searching internet, response is:\nR: {resp_reasoning}\nA: {resp_content}\nEnd of MFocus toolchain searching internet", '201')
    
    answer_post_think = proceed_agent_response(resp_content)
    return answer_post_think, answer_post_think

if __name__ == '__main__':
    async def test():
        fsc = FullSocketsContainer()
        fsc.mfocus_conn = await ConnUtils.mfocus_conn()
        print(await internet_search(fsc, "使用不同的语言会改变人的思考方式吗", "话说，莫妮卡，你觉得使用不同的语言会改变人的思考方式吗"))
    from maica import init
    init()
    asyncio.run(test())
