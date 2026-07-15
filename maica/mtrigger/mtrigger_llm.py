"""
This handles LLM involving MTrigger procedures.
"""

import asyncio

from typing import *
from maica.maica_utils import *

_Bt = BilingualText
_Wt = WrappedOpenAITool

class MtPipeliner():
    """
    MTrigger is far simpler than MFocus, I hope things here will also be simpler.
    We'll copy as much as we can from mf.
    """
    def _reset_tools(self):
        self.tools = []

    def _reset_session(self):
        self.mt_session = MaicaSession()

    def reset(self):
        self._reset_tools()
        self._reset_session()

    def __init__(
            self,
            org_session: MaicaSession,
            fsc: FullSocketsContainer,
            sp: SessionPersistent,
            st: SessionTrigger,

        ):
        self.org_session = org_session
        self.fsc = fsc
        self.sp = sp
        self.st = st
        self.reset()

    def _construct_tools(self):
        curr_aff = self.sp.affection
        tools_jsc = self.st.form_jsc(curr_aff)

        # We should explicitly add a stop tool to fit tool_choice required
        agent_finished = _Wt(
            name="agent_finished",
            description=_Bt(
                "此工具用于表示工具调用完成. 若你已调用了所有其它必要的工具, 或不需要调用任何其它工具, 则在准备作答前调用此工具.",
                "This tool indicates tool calling has finished. Call this tool when you've finished calling every other necessary tool, or if you don't need any other tool, and are ready to answer."
            )
        )
        tools_jsc.append(agent_finished.to_json_schema(self.fsc.maica_settings.basic.target_lang))

        self.tools = tools_jsc

    def _construct_messages(self):
        """
        The query construction.
        """
        # Just to save some typing
        target_lang = self.fsc.maica_settings.basic.target_lang

        if not len(self.mt_session):

            # handle mt_context_rnds
            # mt requires natively one round so +1
            num_org_rnds = self.fsc.maica_settings.extra.mt_context_rnds + 1
            num_org_items = num_org_rnds * 2

            org_items = self.org_session[-num_org_items:]

            taskend_word = "表示任务完成" if target_lang == 'zh' else "indicate task finished"

            system = MaicaSessionItem(
                "system",
                _Bt(
f"""\
你是一个人工智能助手, 你的任务是调用工具, 以作为角色"莫妮卡"执行游戏内操作.
最终你应该通过调用工具的方式{taskend_word}. 如果该问题不需要工具, 你可以直接{taskend_word}.\
""",
f"""\
You are a helpful assistant, your task is using tools to perform in-game actions as charcater "Monika".
Finally you should {taskend_word} with a corresponding tool. If the message does not require tools to answer, you can {taskend_word} directly.\
"""
                ),
            )
            self.mt_session.append(system)

            self.mt_session.extend(org_items)

        # We're creating a new query_item here, since we don't need known_info
        query_item = MaicaSessionItem(
            "user",
            _Bt(
                "<task> 观察以上对话历史记录, 依据上一轮对话调用工具. (除调整好感度和结束任务外)不要调用未经明确指示的工具. 每个工具最多调用一次.",
                "<task> Observe the chat history and make tool calls according to last round of conversation. Do not use tools (except affection and finished) without explicit request. Do not use any tool more than once."
            ),
            target_lang=target_lang,
        )
        self.mt_session.append(query_item)

    async def _query_response(self):
        self._construct_tools()
        self._construct_messages()

        completion_args = {
            "input": self.mt_session.utilize(
                manual_prompt=True,
                # Doesn't make a difference, but just for clarity
                ignore_additions=True,
            ),
            "tools": self.tools,

            # We force tool calling to make it eventually use a stopping tool
            "tool_choice": "required",
        }

        tools_looped_rnds = 0
        conversation_rnd_end = False

        async def tools_loop(a_tool_calls: AsyncIterator[ToolCall]):
            nonlocal tools_looped_rnds, conversation_rnd_end
            tools_looped_rnds += 1

            async def tool_respond(tool_call: ToolCall) -> Union[str, False]:
                """
                Tool router and caller.
                
                Return:
                - False for stopping, str for tool response creating
                """
                tool_name = tool_call.name
                arguments = tool_call.arguments

                # Some special tools handled explicitly
                match tool_name:
                    case "agent_finished":
                        return False
                    
                    # Common triggers here
                    case _:
                        trigger_send = {tool_name: arguments}

                        await self.fsc.messenger('maica_mtrigger_trigger', trigger_send, 200, type=MsgType.CARRIAGE, no_print=True)

                        text = _Bt(
                            "工具已调用并生效.",
                            "Tool called successfully.",
                        ).to_str(self.fsc.maica_settings.basic.target_lang)

                        return text

            async def make_call(tool_call: ToolCall):
                nonlocal conversation_rnd_end

                await self.fsc.messenger(
                    'maica_mtrigger_tool_call',
                    f"MTrigger calling tool {tool_call.name}: {tool_call.arguments}, handling trigger...",
                    201,
                    type=MsgType.PRIM_LOG,
                )

                # Then if we need to respond
                tool_response = await tool_respond(tool_call)

                if not tool_response:
                    conversation_rnd_end = True

                else:

                    # Create maica compatible item
                    maica_tool_call = MaicaSessionItem(
                        preserved=tool_call.model_dump()
                    )
                    self.mt_session.append(maica_tool_call)

                    # Then create the tool response item
                    maica_tool_response = MaicaSessionItem(
                        preserved={
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": tool_response,
                        }
                    )
                    self.mt_session.append(maica_tool_response)

            call_tasks = []
            async for tool_call in a_tool_calls:
                
                call_tasks.append(
                    asyncio.create_task(
                        make_call(tool_call)
                    )
                )

                if conversation_rnd_end:
                    break

            await asyncio.gather(*call_tasks)

        await self.fsc.messenger(
            'maica_mtrigger_tool_start',
            f"MTrigger started, sending first query...",
            200,
        )

        conn = self.fsc.mfocus_conn
        while (
            not conversation_rnd_end
            and not tools_looped_rnds >= 3
            and not (

                # If disable loop, it runs only once
                self.fsc.maica_settings.extra.mt_disable_loop
                and tools_looped_rnds >= 1
            )
        ):

            # Generation
            async with llm_request(conn, **completion_args) as (task, a_reasoning, a_content, a_tool_calls):
                await tools_loop(a_tool_calls)

        await self.fsc.messenger(
            'maica_mtrigger_tool_fin',
            f"MTrigger ended due to {'stopping tool' if conversation_rnd_end else 'rounds limit'}",
            200,
        )

        return

    async def run_mt_pipeline(self):
        """
        This wraps _query_response, since it's designed to be multiple-rounds compatible.
        This wrapping is single-round, fits the actual use case.
        """
        await self._query_response()
        self.reset()
