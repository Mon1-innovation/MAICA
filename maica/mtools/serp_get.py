import asyncio
import traceback

from typing import *
from pydantic import BaseModel, Field

from maica.maica_utils import *
from . import providers

_Bt = BilingualText

async def internet_search(fsc: FullSocketsContainer, query):
    session = MaicaSession()
    target_lang = fsc.maica_settings.basic.target_lang
    conn = fsc.mnerve_conn or fsc.mfocus_conn

    @Decos.conn_retryer_factory()
    async def _search(fake_self, query, target_lang):
        res_m = await (providers.get_asearch())(query, target_lang)
        if not res_m.results:
            raise MaicaInternetWarning('Search result is empty')
        return res_m

    class EnetSearchConcl(GenCorrectionModel):
        conclusion: Optional[str] = Field(
            description="你总结出的内容, 应是一个单行自然句." if target_lang == 'zh' else "Your conclusion, should be a single line of nature sentence."
        )
    completion_args = None
    results_list = []

    # Traditional serp impl
    if not int(G.A.RESPONSES_SERP):

        try:
            res_m = await _search(DummyClass(name="serp"), query, target_lang)

            for index, res_i in enumerate(res_m.results):
                source = f"({res_i.source}) " if res_i.source else ""
                results_list.append(
                    f"{source}{res_i.title}: {res_i.description}"
                )

            sync_messenger(info=f'MFocus got {len(res_m.results)} information lines from search engine', type=MsgType.INFO)

        except Exception as e:
            await messenger(fsc.websocket, "mfocus_serp_failed", f"MFocus serp failed: {str(e)}", 408, fsc.tracker_id)
    
        if not fsc.maica_settings.extra.esearch_llm_concl:
            results_list = results_list[:5]

        elif results_list:
            system = MaicaSessionItem(
                "system",
                _Bt("""\
你是一个人工智能助手, 你接下来会收到一些来自互联网的信息和一个问题.
你应将信息中与问题相关的部分整理总结成一个自然句, 保持内容简洁有效, 并将其输出.
如果没有任何信息与问题相关, 你可以输出null.\
""",
"""\
You are a helpful assistant, now you will recieve some information from the Internet and a question.
Conclude information related with query briefly in a natural sentence, while keeping it concise and useful, then output.
If none of the information is relevant with query, you can output null.\
"""
                )
            )
            session.append(system)

            user_query = MaicaSessionItem(
                "user",
                f'Information: {'; '.join(results_list)}\nQuestion: {query}',
                target_lang=target_lang,
            )
            session.append(user_query)

            completion_args = {
                "input": session.utilize(
                    manual_prompt=True,
                    ignore_additions=True,
                ),
                "text": pyd_to_openai(EnetSearchConcl)
            }

    # Responses web_search impl
    else:

        system = MaicaSessionItem(
            "system",
            _Bt("""\
你是一个人工智能助手, 你接下来会收到一个问题.
你应调用工具搜索互联网, 将结果整理总结成一个自然句, 保持内容简洁有效, 并将其输出.
如果没有任何结果与问题相关, 你可以输出null.\
""",
"""\
You are a helpful assistant, now you will recieve a question.
Search Internet with tool and conclude the results briefly in a natural sentence, keep it concise and useful, then output.
If none of the results is relevant with query, you can output null.\
"""
            )
        )
        session.append(system)

        user_query = MaicaSessionItem(
            "user",
            f'Question: {query}',
            target_lang=target_lang,
        )
        session.append(user_query)

        completion_args = {
            "input": session.utilize(
                manual_prompt=True,
                ignore_additions=True,
            ),
            "tools": [{"type": "web_search"}],
            "text": pyd_to_openai(EnetSearchConcl)
        }

    if completion_args:
        resp = await conn.make_completion(**completion_args)
        selection_result = EnetSearchConcl.model_validate_json(resp.output_text)

        text = selection_result.conclusion
        if text:
            results_list = [text]

    return results_list

if __name__ == '__main__':
    async def test():
        fsc = FullSocketsContainer()
        fsc.maica_settings.basic.target_lang = 'zh'
        # fsc.maica_settings.extra.esearch_llm_concl = False
        fsc.mnerve_conn = await ConnUtils.mnerve_conn()
        print(await internet_search(fsc, "花谱上海演唱会取消"))
    from maica import init
    init()
    asyncio.run(test())
