import re
import json
import asyncio
import traceback
import functools

from maica.maica_utils import *
from . import providers

async def internet_search(fsc: FullSocketsContainer, query, original_query):
    target_lang = fsc.maica_settings.basic.target_lang

    @Decos.conn_retryer_factory()
    async def _search(fake_self, query, target_lang):
        results_sync = await (providers.get_asearch())(query, target_lang)
        assert len(results_sync), 'Search result is empty'
        return results_sync

    results_sync = await _search(DummyClass(name="serp"), query, target_lang)

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

    await messenger(info=f'MFocus got {rank} information lines from search engine', type=MsgType.INFO)

    results_full_str = str(results_full).strip('[').strip(']')
    results_short_str = str(results_short).strip('[').strip(']')
    if not fsc.maica_settings.extra.esc_aggressive:
        return results_short_str, results_humane

    system_init = """你是一个人工智能助手, 你接下来会收到一个问题和一些来自互联网的信息.
以单行不换行的自然语言的形式, 简洁地整理提供相关的信息, 长度不要超过一个自然句. 如果你最终认为提供的信息与问题相关性不足, 返回false.
Begin!""" if target_lang == 'zh' else """You are a helpful assistant, now you will recieve a question and some information from the Internet.
Conclude related information briefly in a single line of natural language, and do not exceed the length of a natural sentence. If you think the provided information is not related enough to the question, return false.
Begin!"""

    messages = [{'role': 'system', 'content': system_init}]
    messages.append({'role': 'user', 'content': f'question: {query}; information: {results_full_str}'})
    # messages = apply_postfix(messages, thinking=False)
    completion_args = {
        "messages": messages,
    }

    conn = fsc.mnerve_conn or fsc.mfocus_conn

    resp = await conn.make_completion(**completion_args)
    resp_content, resp_reasoning = resp.choices[0].message.content, getattr(resp.choices[0].message, 'reasoning_content', None)
    resp_content, resp_reasoning = proceed_common_text(resp_content), proceed_common_text(resp_reasoning)
        
    await messenger(None, 'mfocus_internet_search', f"\nMFocus toolchain searching internet, response is:\nR: {resp_reasoning}\nA: {resp_content}\nEnd of MFocus toolchain searching internet", '201')
    
    answer_post_think = proceed_common_text(resp_content)
    if answer_post_think:
        return answer_post_think, f"参考资料: {answer_post_think}" if target_lang == 'zh' else f"References: {answer_post_think}"
    else:
        return None, None

if __name__ == '__main__':
    async def test():
        fsc = FullSocketsContainer()
        fsc.maica_settings.basic.target_lang = 'zh'
        # fsc.maica_settings.extra.esc_aggressive = False
        fsc.mnerve_conn = await ConnUtils.mnerve_conn()
        print(await internet_search(fsc, "花谱上海演唱会取消", "花谱上海演唱会取消了，难过"))
    from maica import init
    init()
    asyncio.run(test())
