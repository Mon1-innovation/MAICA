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

    results_list = []
    try:
        res_m = await _search(DummyClass(name="serp"), query, target_lang)

        for index, res_i in enumerate(res_m.results):
            source = f"({res_i.source}) " if res_i.source else ""
            results_list.append(
                f"{index + 1}. {source}{res_i.title}: {res_i.description}"
            )

        sync_messenger(info=f'MFocus got {len(res_m.results)} information lines from search engine', type=MsgType.INFO)

    except Exception as e:
        res_m = None
        await messenger(fsc.websocket, "mfocus_serp_failed", f"MFocus serp failed: {str(e)}", 408, fsc.tracker_id)

    # Early return if llm conc not required
    if not results_list:
        text = ''

    elif not fsc.maica_settings.extra.esearch_llm_concl:
        text = '; '.join(results_list[:5])
    
    else:
        class EnetSearchConcl(BaseModel):
            conclusion: Optional[str] = Field(
                description="你总结出的内容, 应是一个单行自然句." if target_lang == 'zh' else "Your conclusion, should be a single line of nature sentence."
            )

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
            "text": {
                "format": {
                    "type": "json_schema",
                    "strict": True,
                    "schema": EnetSearchConcl.model_json_schema(),
                }
            },
        }

        resp = await conn.make_completion(**completion_args)
        selection_result = EnetSearchConcl.model_validate_json(resp.output_text)

        text = selection_result.conclusion

    if not text:
        text = "未搜索到相关信息." if target_lang == 'zh' else "No relevant information found."

    return text, res_m

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
