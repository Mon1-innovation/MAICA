"""
This handles LLM involving MFocus procedures.
"""

import asyncio

from typing import *
from dataclasses import dataclass
from maica.mtools import providers, llm_request
from maica.maica_utils import *

_JSCType = Literal["string", "number", "integer", "object", "array", "boolean", "null"]
JSCType = List[_JSCType] | _JSCType
        
_Bt = BilingualText
_Wtp = WrappedOpenAIToolProperty 
_Wt = WrappedOpenAITool
_Wtn = WrappedOpenAIToolNamespace

class MfLLMRouter():
    """
    MFocus only works single-round, so maybe not required to implement multiple query rounds.
    We will make it if possible anyway.
    Tool calls loop however, must be considered.
    """
    def _reset_tools(self):
        self.tools = []

    def _reset_session(self):
        self.mf_session = MaicaSession()
        self.mf_session.default_target_lang = self.fsc.maica_settings.basic.target_lang

    def __init__(self, fsc: FullSocketsContainer):
        self.fsc = fsc
        self._reset_tools()
        self._reset_session()

    @property
    def _mfocus_impl_mvista(self) -> bool:
        """If MVista tool should be used."""
        return (
            not is_mcore_vl()
            and bool(self.settings.temp.mv_imgs)
        )

    def _construct_tools(self):
        """This should only be used in the initial query construction."""
        # Commonly appliable tools first
        time_acquire = _Wt(
            name="time_acquire",
            description=_Bt(
                "调用该工具以获取当前时间.",
                "Call this tool to get the current time."
            ),
        )
        date_acquire = _Wt(
            name="date_acquire",
            description=_Bt(
                "调用该工具以获取当前日期, 季节和年份.",
                "Call this tool to get the current date, season and year."
            )
        )
        weather_acquire = _Wt(
            name="weather_acquire",
            description=_Bt(
                "调用该工具以查询指定地区的天气.",
                "Call this tool to query the weather in designated area."
            ),
            requiredParams=[
                _Wtp(
                    name="location",
                    type=["string", "null"],
                    description=_Bt(
                        "需要查询天气的地理位置, 如'湖北武汉'. 留空以使用用户当前的地理位置.",
                        "The location for which you want to query the weather, e.g., 'Los Angeles'. Leave empty for user's current location."
                    )
                )
            ]
        )
        event_acquire = _Wt(
            name="event_acquire",
            description=_Bt(
                "调用该工具以查询指定日期的节日或事件.",
                "Call this tool to query the event or holiday of a given date."
            ),
            requiredParams=[
                _Wtp(
                    name="datetime",
                    type=["string", "null"],
                    description=_Bt(
                        "需要查询事件的具体日期, 如'2003-06-26'. 留空以使用今天的日期.",
                        "The date for which you want to query the event, e.g., '2003-06-26'. Leave empty for today's date."
                    )
                )
            ]
        )

        # Then here comes conditional tools
        persistent_acquire = _Wt(
            name="persistent_acquire",
            description=_Bt(
                "调用该工具以查询你角色的记忆.",
                "Call this tool to query the memory of your character."
            ),
            requiredParams=[
                _Wtp(
                    name="query",
                    type="string",
                    description=_Bt(
                        "需要查询的内容, 如'莫妮卡喜欢吃什么', '用户的所在地区'等.",
                        "The question you want to query, e.g., 'What does Monika like to eat', 'What region user lives in', etc."
                    )
                )
            ]
        )
        search_internet = _Wt(
            name="search_internet",
            description=_Bt(
                "调用该工具以搜索互联网.",
                "Call this tool to search a question on the Internet."
            ),
            requiredParams=[
                _Wtp(
                    name="query",
                    type="string",
                    description=_Bt(
                        "需要搜索的内容, 应当是简洁明确的关键词.",
                        "The question you want to search, should be concise and clear keywords."
                    )
                )
            ]
        )
        vista_acquire = _Wt(
            name="vista_acquire",
            description=_Bt(
                "用户上传了一到数张图片, 调用该工具以查看其内容.",
                "User has uploaded one or several images, call this tool to get their contents."
            ),
            requiredParams=[
                _Wtp(
                    name="query",
                    type=["string", "null"],
                    description=_Bt(
                        "需要从图片中提取的信息, 如'图中人物的衣服颜色'. 留空以获取图片内容概括.",
                        "The information you want to extract from the image, e.g., 'Color of man on the picture's clothes'. Leave empty for a brief summary."
                    )
                )
            ]
        )

        # Perhaps we should deprecate this since it was for DAA2-like ability models, but not now
        conclude_information = _Wt(
            name="conclude_information",
            description=_Bt(
                "此工具用于总结信息. 若你已调用了所有其它必要的工具, 或不需要调用任何其它工具, 则在准备作答前调用此工具.",
                "This tool is for information concluding. Call this tool when you've finished calling every other necessary tool, or if you don't need any other tool, and are ready to answer."
            ),
            requiredParams=[
                _Wtp(
                    name="conclusion",
                    type=["string", "null"],
                    description=_Bt(
                        "总结你获取的信息和对应的推理, 并整理成一到数个简洁的句子, 如'现在是上午九点, 因此适合吃早餐; 且天气凉爽, 因此适合户外活动'. 留空以表示没有值得总结的信息."
                        "Conclude information you acquired and corresponding reasoning, into one or several concise and clear sentences, e.g., 'It's 9:00 in the morning, suitable for breakfast; The weather is cool, good for exercising'. Leave empty if no information worths concluding."
                    )
                )
            ]
        )
        agent_finished = _Wt(
            name="agent_finished",
            description=_Bt(
                "此工具用于表示工具调用完成. 若你已调用了所有其它必要的工具, 或不需要调用任何其它工具, 则在准备作答前调用此工具.",
                "This tool indicates tool calling has finished. Call this tool when you've finished calling every other necessary tool, or if you don't need any other tool, and are ready to answer."
            )
        )

        # Then we make the namespaces.
        # Or should we? Perhaps not since they divide the tools and model cannot see though it.
        # We don't use them.
        t1_tools = _Wtn(
            name="local_tools",
            description=_Bt(
                "本地类工具, 相对常用, 应优先考虑.",
                "Local tools, relatively commonly used, consider at higher priority."
            ),
            tools=[]
        )
        t2_tools = _Wtn(
            name="internet_tools",
            description=_Bt(
                "联网类工具, 在需要时使用.",
                "Internet tools, use when you need to."
            ),
            tools=[]
        )

        # Then we make the tools collection.
        tools: List[Union[WrappedOpenAITool, WrappedOpenAIToolNamespace]] = []
        tools.extend([time_acquire, date_acquire, weather_acquire, event_acquire])

        if self.fsc.maica_settings.extra.mf_constant_pers < 2:
            tools.append(persistent_acquire)

        if providers.get_asearch():
            tools.append(search_internet)

        if self._mfocus_impl_mvista:
            tools.append(vista_acquire)

        if self.fsc.maica_settings.extra.mf_llm_concl:
            tools.append(conclude_information)
        else:
            tools.append(agent_finished)

        # Finally to json schema
        tools_jsc = [i.to_json_schema(self.fsc.maica_settings.basic.target_lang) for i in tools]
        self.tools = tools_jsc
    
    def _construct_messages(self, query):
        """The query construction. Following tools' handling goes to another handler."""
        # Just to save some typing
        target_lang = self.fsc.maica_settings.basic.target_lang

        if self._mfocus_impl_mvista:
            image_word = " [图片]" if self.settings.basic.target_lang == 'zh' else " [Image]"
            query += image_word

        if not len(self.mf_session):

            if self.fsc.maica_settings.extra.mf_llm_concl:
                taskend_word = "作出总结" if target_lang == 'zh' else "draw a conclusion"
            else:
                taskend_word = "表示任务完成" if target_lang == 'zh' else "indicate task finished"

            system = MaicaSessionItem(
                "system",
                _Bt(
f"""\
你是一个人工智能助手, 你的任务是调用工具, 以作为角色"莫妮卡"回答用户的问题.
最终你应该通过调用工具的方式{taskend_word}. 如果该问题不需要工具, 你可以直接{taskend_word}.\
""",
f"""\
You are a helpful assistant, your task is using tools to respond user's query as charcater "Monika".
Finally you should {taskend_word} with a corresponding tool. If the message does not require tools to answer, you can {taskend_word} directly.\
"""
                ),
            )
            self.mf_session.append(system)

        query_item = MaicaSessionItem(
            "user",
            query,
        )
        self.mf_session.append(query_item)

    async def _query_response(self, query):
        """Now that we have tools and messages, we can finally launch completion."""
        self._construct_tools()
        self._construct_messages(query)

        completion_args = {
            "messages": self.mf_session.utilize(),
            "tools": self.tools,
            "response_format": {"type": "text"},
        }

        a_reasoning, a_content, a_tool_calls = await llm_request(**completion_args)

        async def tool_response(tool_name, arguments):
            """Tool router and caller."""