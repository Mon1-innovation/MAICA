"""
This handles LLM involving MFocus procedures.
"""

import asyncio

from typing import *
from .agent_modules import AgentTools
from maica.mtools import providers
from maica.maica_utils import *

_JSCType = Literal["string", "number", "integer", "object", "array", "boolean", "null"]
JSCType = List[_JSCType] | _JSCType
        
_Bt = BilingualText
_Wtp = WrappedOpenAIToolProperty 
_Wt = WrappedOpenAITool
_Wtn = WrappedOpenAIToolNamespace

class MfPipeliner():
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

    def reset(self):
        self._reset_tools()
        self._reset_session()

    def __init__(
            self,
            org_session: MaicaSession,
            fsc: FullSocketsContainer,
            sp: SessionPersistent,

        ):
        self.org_session = org_session
        self.fsc = fsc
        self.sp = sp
        self.reset()

    @property
    def _mfocus_impl_mvista(self) -> bool:
        """If MVista tool should be used."""
        return (
            not is_mcore_vl()
            and bool(self.fsc.maica_settings.temp.mvista.mv_imgs)
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
                    name="dt_str",
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
                    name="ser_query",
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

        if self.fsc.maica_settings.extra.mf_const_sf_access < 2:
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
    
    def _construct_messages(self):
        """
        The query construction.
        """
        # Just to save some typing
        target_lang = self.fsc.maica_settings.basic.target_lang

        # We're copying session_item to preserve known_info
        session_item: MaicaSessionItem = self.org_session[-1].model_copy()

        if self._mfocus_impl_mvista:
            image_word = " [图片]" if self.settings.basic.target_lang == 'zh' else " [Image]"
            session_item.content += image_word

        if not len(self.mf_session):

            # handle mf_context_rnds
            num_org_rnds = self.fsc.maica_settings.extra.mf_context_rnds
            num_org_items = num_org_rnds * 2

            if num_org_items:
                org_items = self.org_session[-(num_org_items + 1):-1]
            else:
                org_items = []

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

            self.mf_session.extend(org_items)

        self.mf_session.append(session_item)

    async def _query_response(self):
        """
        Now that we have tools and messages, we can finally launch completion.
        
        Returns:
        - str: generated_guidance
        - dict: tools_results
        """
        self._construct_tools()
        self._construct_messages()

        completion_args = {
            "messages": self.mf_session.utilize(
                manual_prompt=True,
                # He needs these informations
                # ignore_additions=True,
            ),
            "tools": self.tools,
            "response_format": {"type": "text"},

            # We force tool calling to make it eventually use a stopping tool
            # This will likely make mf_llm_concl far more stable
            "tool_choice": "required",
        }

        generated_guidance: str = ""
        tools_results: dict[
            str,
            Tuple[str, Any],
        ] = {}
        tools_looped_rnds = 0
        conversation_rnd_end = False

        async def tools_loop(a_tool_calls: AsyncIterator[ToolCall]):
            nonlocal tools_looped_rnds
            tools_looped_rnds += 1

            # Prepare a toolbox
            toolbox = AgentTools(self.fsc, self.sp)

            async def tool_respond(tool_call: ToolCall) -> Union[str, False]:
                """
                Tool router and caller.
                
                Return:
                - False for stopping, str for tool response creating
                """
                nonlocal generated_guidance

                tool_name = tool_call.name
                arguments = tool_call.arguments

                # Some special tools handled explicitly
                match tool_name:
                    case "conclude_information":
                        conclusion = arguments["conclusion"]
                        if conclusion:
                            generated_guidance = conclusion
                        return False
                    
                    case "agent_finished":
                        return False
                    
                    # Common tools here
                    case _:
                        tool = getattr(toolbox, tool_name)

                        # We designed all tools to return Tuple[readable_result, actual_values]
                        # Item should not be added to final results if actual_values bool is false.
                        text, body = await tool(**arguments)

                        # Do not record it for mcore if the tool actually failed
                        if body:

                            # We can theoretically keep all resps, but that's not useful I think.
                            # In case that's really necessary, just use mf_llm_concl
                            tools_results["tool_name"] = (text, body)

                        return text
                    
            async for tool_call in a_tool_calls:

                # Log and send tool call
                await self.fsc.messenger(
                    'maica_mfocus_tool_call',
                    f"MFocus calling tool {tool_call.name}: {tool_call.arguments}, retrieving tool response...",
                    201,
                    type=MsgType.LOG,
                )

                # Create maica compatible item
                maica_tool_call = MaicaSessionItem(
                    preserved=tool_call.model_dump()
                )
                self.mf_session.append(maica_tool_call)

                # Then if we need to respond
                tool_response = await tool_respond(tool_call)

                if not tool_response:
                    conversation_rnd_end = True
                    break

                else:
                    await self.fsc.messenger(
                        'maica_mfocus_tool_resp',
                        f"MFocus tool {tool_call.name} responded: {tool_response}",
                        200,
                        type=MsgType.INFO,
                    )

                # Then create the tool response item
                maica_tool_response = MaicaSessionItem(
                    preserved={
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": tool_response,
                    }
                )
                self.mf_session.append(maica_tool_response)

        await self.fsc.messenger(
            'maica_mfocus_tool_start',
            f"MFocus started, sending first query...",
            200,
        )

        conn = self.fsc.mfocus_conn
        while (
            not conversation_rnd_end
            and not tools_looped_rnds >= 3
            and not (

                # If disable loop, it runs only once
                self.fsc.maica_settings.extra.mf_disable_loop
                and tools_looped_rnds >= 1
            )
        ):

            # Generation
            task, a_reasoning, a_content, a_tool_calls = await llm_request(conn, **completion_args)
            await tools_loop(a_tool_calls)

        await self.fsc.messenger(
            'maica_mfocus_tool_fin',
            f"MFocus ended due to {'stopping tool' if conversation_rnd_end else 'rounds limit'}, generated guidance is {generated_guidance or 'EMPTY'}",
            200,
        )

        return generated_guidance, tools_results
    
    @staticmethod
    def parse_tools_results(tools_results: dict[str, Tuple[str, Any]]):
        def sort_dict(d: dict, seq: list[str]) -> dict:
            """Sorts keys of dict into given list seq."""
            nd = {}
            unlisted_ks = d.keys() - set(seq)
            for k in seq:
                if k in d:
                    nd[k] = d[k]
            for k in unlisted_ks:
                nd[k] = d[k]
            return nd
        
        sorted_tools_results = sort_dict(
            tools_results,
            [
                "time_acquire",
                "date_acquire",
                "weather_acquire",
                "event_acquire",
                "persistent_acquire",
                "search_internet",
                "vista_acquire",
            ]
        )

        cleaned_tools_results = {
            k: v[0]
            for k, v in sorted_tools_results.items()
            if v[0] and v[1]
        }

        return cleaned_tools_results
    
    async def run_mf_pipeline(self):
        """
        This wraps _query_response, since it's designed to be multiple-rounds compatible.
        This wrapping is single-round, fits the actual use case.
        """
        generated_guidance, tools_results = await self._query_response()
        parsed_results = self.parse_tools_results(tools_results)

        self.reset()
        return generated_guidance, parsed_results