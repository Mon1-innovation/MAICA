import json
import random
import traceback
import asyncio
import websockets
import colorama

from openai.types.chat import ChatCompletion, ChatCompletionMessage
from typing import *
from maica.mfocus.mfocus_sfe import SfPersistentManager
from maica.mtrigger.mtrigger_sfe import MtPersistentManager
from maica.maica_utils import *

class MTriggerManager(AgentContextManager):
    def __init__(self, fsc: FullSocketsContainer, mt_inst: MtPersistentManager, sf_inst: Optional[SfPersistentManager]=None):
        super().__init__(fsc, sf_inst, mt_inst)

    def _construct_tools(self):
        self.tools = []; self._aff_name = None
        trigger_list = self.mt_inst.get_valid_triggers()
        for trigger in trigger_list:
            match trigger.template:
                case 'common_affection_template':
                    current_aff = self.sf_inst.read_from_sf('mas_affection') if self.sf_inst else None
                    if current_aff:
                        current_aff = int(float(current_aff))
                        current_aff_str = f', 当前好感度是{current_aff}' if self.settings.basic.target_lang == 'zh' else f', current affection is {current_aff}'
                    else:
                        current_aff_str = ''
                    description_aff = f"当你认为对用户的好感度应发生变化时调用该工具{current_aff_str}. 例如, 当用户发送夸赞, 关心, 或表现明显的情感时可以调用该工具." if self.settings.basic.target_lang == 'zh' else f"Call this tool to change affection when you think you should{current_aff_str}. For example, you can call this tool when user is complimenting, showing care, or expressing notable emotion."
                    self.tools.append(
                        {
                            "name": trigger.name,
                            "description": description_aff,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "affection": {
                                        "type": "number",
                                        "description": "输出正数以增加好感, 负数以减少好感. 单次最大好感增幅约为3, 一般增幅约为1. 例如, 称赞你的容貌可以增加0.8, 表达爱情的短句可以增加1.5, 表达爱情的长句则可以增加3.0.\n仅当用户故意冒犯时考虑输出负数." if self.settings.basic.target_lang == 'zh' else "Emit positive number to increase affection, negative to decrease affection. The maximum increase should be around 3, while it's normally around 1.\nFor example, a compliment about your beauty could result in plus 0.8, a short sentence expressing love could result in plus 1.5, and a long phrase expressing love could result in plus 3.0.\nYou shouldn't emit a negative value unless user is offending you intensively.",
                                        "example_value": "0.25"
                                    }
                                },
                                "required": [
                                    "affection"
                                ],
                                "optional": [
                                ]
                            }
                        }
                    )
                    self._aff_name = trigger.name
                case 'common_switch_template':
                    item_common_name = trigger.exprop.item_name.zh if self.settings.basic.target_lang == 'zh' else trigger.exprop.item_name.en
                    curr_item = trigger.exprop.curr_item
                    item_list = trigger.exprop.item_list
                    if curr_item:
                        current_choice_str = f', 当前的{item_common_name}是{curr_item}' if self.settings.basic.target_lang == 'zh' else f', current {item_common_name} is {curr_item}'
                    else:
                        current_choice_str = ''
                    description_switch = f'调用该工具以切换{item_common_name}{current_choice_str}.' if self.settings.basic.target_lang == 'zh' else f'Call this tool to switch {item_common_name}{current_choice_str}.'
                    self.tools.append(
                        {
                            "name": trigger.name,
                            "description": description_switch,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "selection": {
                                        "type": "string",
                                        "description": f'根据用户的要求, 从以下{item_common_name}中选出最合适的一项:\n{item_list}\n只选择, 不作改动. 如果没有任何一项符合要求, 则回答false.' if self.settings.basic.target_lang == 'zh' else f"According to user's request, choose a proper {item_common_name} from the following list:\n{item_list}\nMake your choice without modifying any item. If nothing in list matches user's request, return false.",
                                        "example_value": random.choice(item_list)
                                    }
                                },
                                "required": [
                                    "selection"
                                ],
                                "optional": [
                                ]
                            }
                        }
                    )
                    if trigger.exprop.suggestion:
                        self.tools[-1].update(
                            {
                                "parameters": {
                                    "properties": {
                                        "suggestion": {
                                            "type": "string",
                                            "description": f'若你在selection中回答了false, 你可以在此回答列表之外的{item_common_name}, 以满足用户要求.' if self.settings.basic.target_lang == 'zh' else f'If you chose false in the selection section, you can reply a {item_common_name} that\'s not in the list, which can satisfy the user\'s request.'
                                        }
                                    },
                                    "optional": [
                                        "suggestion"
                                    ]
                                }
                            }
                        )
                case 'common_meter_template':
                    meter_name = trigger.exprop.item_name.zh if self.settings.basic.target_lang == 'zh' else trigger.exprop.item_name.en
                    curr_value = trigger.exprop.curr_value
                    lower, upper = trigger.exprop.value_limits
                    if curr_value:
                        current_value_str = f', 当前的{meter_name}值是{curr_value}' if self.settings.basic.target_lang == 'zh' else f', current {meter_name} value is {curr_value}'
                    else:
                        current_value_str = ''
                    description_meter = f'调用该工具以调整{meter_name}{current_value_str}' if self.settings.basic.target_lang == 'zh' else f'Call this tool to adjust {meter_name}{current_value_str}'
                    self.tools.append(
                        {
                            "name": trigger.name,
                            "description": description_meter,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "value": {
                                        "type": "number",
                                        "description": f'根据用户的要求, 在{lower}到{upper}之间为{meter_name}选择一个合适的值. 如果合适的值不存在, 则回答false.' if self.settings.basic.target_lang == 'zh' else f"According to user's request, choose a proper value for {meter_name} in range {lower} to {upper}. If no value in range matches the request, return false.",
                                        "example_value": "0.25"
                                    }
                                },
                                "required": [
                                    "value"
                                ],
                                "optional": [
                                ]
                            }
                        }
                    )
                case 'customized':
                    trigger_name = trigger.exprop.item_name.zh if self.settings.basic.target_lang == 'zh' else trigger.exprop.item_name.en
                    self.tools.append(
                        {
                            "name": trigger.name,
                            "description": f'调用该工具以触发{trigger_name}.' if self.settings.basic.target_lang == 'zh' else f'Call this tool to trigger {trigger_name}.',
                            "parameters": {
                                "type": "object",
                                "properties": {
                                },
                                "required": [
                                ],
                                "optional": [
                                ]
                            }
                        }
                    )

        self.tools.append(
            {
                "name": "agent_finished",
                "description": f"若你已调用了所有其它必要的工具, 或不需要调用任何其它工具, 则在作出最终回答之前调用此工具, 以表示调用完成." if self.settings.basic.target_lang == 'zh' else f"Call this tool after you've finished calling every other necessary tool, or if you don't need any other tool. Call this tool before making final answer, so we know toolcalling has finished.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "required": [
                    ],
                    "optional": [
                    ]
                }
            }
        )

        self.tools = alt_tools(self.tools)

    async def _construct_query(self, user_input=None, tool_input=None, tool_id=None):
        await super()._construct_query(user_input, tool_input, tool_id, 'post')

    async def triggering(self, input, output, bm=messenger) -> None:
        try:

            # Prepare the first query first
            self._construct_tools()
            await self._construct_query()

            # This is a little bit special
            self.serial_messages.extend([{'role': 'user', 'content': input}, {'role': 'assistant', 'content': output}])
            user_instruct_input = f'观察以上对话历史记录, 依据上一轮对话调用工具. 除{self._aff_name + "和" if self._aff_name else ""}agent_finished外的工具只有明确指示才能调用. 每个工具最多调用一次.' if self.settings.basic.target_lang == 'zh' else f'Observe the chat history and make tool calls according to last round of conversation. Tools except {self._aff_name + " and " if self._aff_name else ""} agent_finished can only be used if requested directly. Each tool can only be used once at most.'
            await self._construct_query(user_input=user_instruct_input)

            cycle = 0; ending = False
            all_tool_count = 0
            while cycle <= 3 and not ending:

                # Sanity check
                cycle += 1

                resp_content, resp_reasoning, resp_tools = await self._send_query(thinking=True)
                resp_content, resp_reasoning = proceed_common_text(resp_content), proceed_common_text(resp_reasoning)

                await bm(self.websocket, 'maica_mtrigger_toolchain', f'\nMTrigger toolchain {cycle} round responded, response is:\nR: {resp_reasoning}\nA: {resp_content}\nAnalyzing response...', code='200')
                tool_seq = 0
                if resp_tools:
                    for resp_tool in resp_tools:

                        # Tool parallel support
                        tool_seq += 1; all_tool_count += 1
                        tool_id, tool_type, tool_func_name, tool_func_args = resp_tool.id, resp_tool.type, resp_tool.function.name, resp_tool.function.arguments
                        await bm(self.websocket, 'maica_mtrigger_parallel_tool', f'\nCalling parallel tool {tool_seq}/{len(resp_tools)}:\n{resp_tool}\nSending trigger...', '200', type=MsgType.INFO, color=colorama.Fore.BLUE)

                        if tool_func_name == 'agent_finished':
                            ending = True
                            break
                        else:
                            trigger_signal = {tool_func_name: proceed_common_text(tool_func_args, is_json=True)}
                            await bm(self.websocket, 'maica_mtrigger_trigger', trigger_signal, '200', type=MsgType.CARRIAGE)

                            machine = f'{tool_func_name}已被调用过并生效' if self.settings.basic.target_lang == 'zh' else f'{tool_func_name} has been called already and taking effect'
                            await self._construct_query(tool_input=machine, tool_id=tool_id)

                else:
                    await messenger(self.websocket, 'maica_mtrigger_absent', f'No tool called, ending toolchain...', '204', type=MsgType.INFO, color=colorama.Fore.LIGHTBLUE_EX)
                    ending = True
                    
                if self.settings.extra.post_astp and not ending:
                    await messenger(self.websocket, 'maica_mtrigger_astp', f'MTrigger interrupted by pre_astp, ending toolchain...', '200', type=MsgType.INFO, color=colorama.Fore.LIGHTBLUE_EX)
                    ending = True

                await bm(self.websocket, 'maica_mtrigger_round_finish', f'MTrigger toolchain {cycle} round finished, ending is {str(ending)}', '200', type=MsgType.INFO, color=colorama.Fore.BLUE)
            # This goes -1 if agent_finished not called, but I decide to leave it be
            await bm(self.websocket, 'maica_mtrigger_done', f'MTrigger ended with {all_tool_count - 1} triggers sent', '1001', color=colorama.Fore.LIGHTBLUE_EX)

        except CommonMaicaException as ce:
            raise ce
        
        except websockets.WebSocketException as we:
            raise MaicaConnectionWarning(str(we), '408') from we

        except Exception as e:
            raise CommonMaicaError('Uncaught MTrigger exception happened', '500', 'maica_mtrigger_critical') from e
