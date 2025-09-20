import json
import random
import traceback
import asyncio
import websockets
import colorama

from openai.types.chat import ChatCompletion, ChatCompletionMessage
from typing import *
from maica.mfocus.mfocus_sfe import SfBoundCoroutine
from maica.mtrigger.mtrigger_sfe import MtBoundCoroutine
from maica.mfocus.agent_modules import AgentTools
from maica.maica_utils import *

class MFocusCoroutine(SideFunctionCoroutine):
    def __init__(self, fsc: FullSocketsContainer, sf_inst: SfBoundCoroutine, mt_inst: Optional[MtBoundCoroutine]=None):
        super().__init__(fsc, sf_inst, mt_inst)        
        self.agent_tools = AgentTools(fsc, sf_inst)

    def _construct_tools(self):
        self.tools = []
        if self.mt_inst and not self.settings.temp.bypass_mt:
            trigger_list = self.mt_inst.get_valid_triggers()
        else:
            trigger_list = None

        self.tools =  [
            {
                "name": "time_acquire",
                "description": "调用该工具以获取当前时间. 只要对话关于: 时间, 问候, 三餐, 休息, 生活节律与建议等, 或你需要获取当前时间以帮助回答, 就使用此工具查询时间." if self.settings.basic.target_lang == 'zh' else "Call this tool to get the current time. Always use this tool if the conversation mentions: time, greeting, meals, sleep, rest, pace of life or related suggestions, or if you want to know the current time to make your answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "required": [
                    ],
                    "optional": [
                    ]
                }
            },
            {
                "name": "date_acquire",
                "description": "调用该工具以获取当前日期. 只要对话关于: 日期, 季节, 年份, 或你需要获取当前日期以帮助回答, 就使用此工具查询日期." if self.settings.basic.target_lang == 'zh' else "Call this tool to get the current date. Always use this tool if the conversation mentions: date, season, year, or if you want to know the current date to make your answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "required": [
                    ],
                    "optional": [
                    ]
                }
            },
            {
                "name": "weather_acquire",
                "description": "调用该工具以获取当前天气. 只要对话关于: 天气, 通勤, 户外活动, 或你需要获取当前天气以帮助回答, 就使用此工具查询天气." if self.settings.basic.target_lang == 'zh' else "Call this tool to get the current weather. Always use this tool if the conversation mentions: weather, commuting, outdoor activities, or if you need to know the current weather to make your answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "你需要查询天气的地理位置. 如果查询用户本地天气, 则留空." if self.settings.basic.target_lang == 'zh' else "The location which you need to get the weather of. Leave empty for the user's local weather.",
                            "example_value": "湖北武汉" if self.settings.basic.target_lang == 'zh' else "Los Angeles"
                        },
                    },
                    "required": [
                    ],
                    "optional": [
                        "location",
                    ]
                }
            },
            {
                "name": "event_acquire",
                "description": "调用该工具以查询当前或指定日期的节日或事件. 只要对话关于: 日期, 节日, 活动, 假期, 或你需要获取指定的事件以帮助回答, 就使用此工具查询节日或事件." if self.settings.basic.target_lang == 'zh' else "Call this tool to get the event or holiday of a given date or current date. Always use this tool if the conversation mentions: date, holiday, anniversary, activities, vacation, or if you need to know the specific event to make your answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "number",
                            "description": "需要查询日期的年份. 如果日期在今年, 则留空." if self.settings.basic.target_lang == 'zh' else "The year of the given date, leave empty for this year.",
                            "example_value": "2003"
                        },
                        "month": {
                            "type": "number",
                            "description": "需要查询日期的月份. 如果日期在本月, 则留空." if self.settings.basic.target_lang == 'zh' else "The month of the given date, leave empty for this month.",
                            "example_value": "6"
                        },
                        "day": {
                            "type": "number",
                            "description": "需要查询日期的日数. 如果日期在本日, 则留空." if self.settings.basic.target_lang == 'zh' else "The day of the given date, leave empty for the day today.",
                            "example_value": "26"
                        },
                    },
                    "required": [
                    ],
                    "optional": [
                        "year",
                        "month",
                        "day",
                    ]
                }
            },
            {
                "name": "persistent_acquire",
                "description": "调用该工具以查询你的角色(莫妮卡)或用户的记忆, 例如你或用户的喜好, 兴趣, 经历, 体验, 关系或个人信息. 只要你被问及你作为AI不具有的记忆, 经历, 个性, 喜好或其它事物, 就使用此工具查找记忆. " if self.settings.basic.target_lang == 'zh' else "Call this tool to get any additional information from your character (Monika)'s memory or user's memory, such as your or user's preferences, hobbies, experiences, appearence, relationship or personal information. Always use this tool if the conversation mentions memories, personality, preferences, hobbies, experience or any other thing you don't have as an AI.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "需要从你或用户的记忆中搜索的信息, 以尽可能直接回答问题. 以第三人称方式提出问题, 不要提及'我'或'我们'." if self.settings.basic.target_lang == 'zh' else "The question you want to search from your memory or user's memory, to answer the question as directly as possible. Ask in third person perspective, do not use appellation 'I', 'me' or 'us'.",
                            "example_value": "莫妮卡喜欢吃什么?" if self.settings.basic.target_lang == 'zh' else "What does Monika like to eat?"
                        },
                    },
                    "required": [
                        "query",
                    ],
                    "optional": [
                    ]
                }
            },
            {
                "name": "search_internet",
                "description": "调用该工具以搜索互联网. 如果你需要联网搜索信息以帮助回答, 则使用该工具搜索互联网. 如果该信息可以通过其它工具获取, 则优先使用其它工具." if self.settings.basic.target_lang == 'zh' else "Call this tool to search a question on the Internet. Use this tool if you need information from the Internet to make your answer. If another tool avaliable could provide the information, use that tool instead.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "需要在搜索引擎中搜索的问题, 应当是一个简洁的句子." if self.settings.basic.target_lang == 'zh' else "The question needs to be searched on Google, which should be a simple sentence.",
                            "example_value": "附近的餐馆" if self.settings.basic.target_lang == 'zh' else "Nearby restaurants"
                        },
                        "location_req": {
                            "type": "boolean",
                            "description": "该问题是否与用户的地理位置有关, 若有关则工具会自动补充." if self.settings.basic.target_lang == 'zh' else "The question is related with user's location or not, the tool will implement automatically if true given.",
                            "example_value": "true"
                        }
                    },
                    "required": [
                        "query",
                    ],
                    "optional": [
                        "location_req",
                    ]
                }
            },
        ]

        if trigger_list and self.settings.extra.amt_aggressive:
            choice_list = []; choice_checklist = []
            for trigger in trigger_list:
                match trigger.template:
                    case 'common_affection_template':
                        pass
                    case 'common_switch_template':
                        cst_temp_list = []
                        for i in trigger.exprop.item_list:
                            j = f'选择{i}' if self.settings.basic.target_lang == 'zh' else f'switch to {i}'
                            choice_checklist.append(j)
                            cst_temp_list.append(j)

                        if trigger.exprop.suggestion:
                            j = f"选择未列出的{trigger.exprop.item_name.zh}" if self.settings.basic.target_lang == 'zh' else f"Choose an unlisted {trigger.exprop.item_name.en}"
                            choice_checklist.append(j)
                            cst_temp_list.append(j)

                        cst_explaination = f"更换{trigger.exprop.item_name.zh}" if self.settings.basic.target_lang == 'zh' else f"Change {trigger.exprop.item_name.en}"
                        choice_list.append({cst_explaination: cst_temp_list})

                    case 'common_meter_template':
                        cmt_iname = f'调整{trigger.exprop.item_name.zh}' if self.settings.basic.target_lang == 'zh' else f'Adjust {trigger.exprop.item_name.en}'
                        choice_checklist.append(cmt_iname)
                        j = f"{cmt_iname}, 范围是{trigger.exprop.value_limits[0]}到{trigger.exprop.value_limits[1]}" if self.settings.basic.target_lang == 'zh' else f"{cmt_iname} within range {trigger.exprop.value_limits[0]} to {trigger.exprop.value_limits[1]}"
                        choice_list.append(j)

                    case _:
                        cc_iname = trigger.exprop.item_name.zh if self.settings.basic.target_lang == 'zh' else trigger.exprop.item_name.en
                        j = f"触发{cc_iname}" if self.settings.basic.target_lang == 'zh' else f"Trigger {cc_iname}"
                        choice_checklist.append(j)
                        choice_list.append(j)

            self.choice_checklist = choice_checklist

            if choice_list:
                self.tools.append(
                    {
                        "name": "react_trigger",
                        "description": "此工具能检验用户的特定要求可否完成. 如果用户对你提出以下类别请求: 切换(如换衣服, 换地点, 换场景), 调整(如调距离, 调亮度), 触发(如开灯, 开启某模式), 则调用该工具." if self.settings.basic.target_lang == 'zh' else "This tool can verify if user's specific request can be done. If user is requesting you to: switching(like changing your clothes, changing location, changing scene), adjusting(like adjusting distance, adjusting brightness), triggering(like turning on light, turning on some mode), use this tool.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "prediction": {
                                    "type": "string",
                                    "description": f"你将收到一系列可用选项. 若某选项能够满足用户的请求, 则输出该选项, 否则输出false. 以下是可用选项:\n{str(choice_list)}" if self.settings.basic.target_lang == 'zh' else f"You'll be offered a list of avaliable choices. return the choice if you think it matches the query, or return false if none matches. Avaliable choices:\n{str(choice_list)}",
                                    "example_value": random.choice(choice_checklist)
                                }
                            },
                            "required": [
                                "prediction",
                            ],
                            "optional": [
                            ]
                        }
                    },
                )
        if self.settings.extra.mf_aggressive:
            self.tools.append(
                {
                    "name": "conclude_information",
                    "description": "此工具用于总结你的输出. 只要你已获取了所有必要信息且准备好作答, 就在作答前调用该工具." if self.settings.basic.target_lang == 'zh' else "This tool can conclude your outputs. Always use this tool if you have acquired all necessary informations before making final answer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conclusion": {
                                "type": "string",
                                "description": "总结你获取的信息和作出的推理, 并整理成一个简洁的句子." if self.settings.basic.target_lang == 'zh' else "Conclude all information you have acquired and reasonings you have made into a concise sentence.",
                                "example_value": "现在是上午九点, 因此适合吃早餐, 且天气凉爽, 因此适合户外活动."  if self.settings.basic.target_lang == 'zh' else "It's 9:00 in the morning, suitable for breakfast. The weather is cool, good for exercising."
                            }
                        },
                        "required": [
                            "conclusion"
                        ],
                        "optional": [
                        ]
                    }
                },
            )
        self.tools.append(
            {
                "name": "agent_finished",
                "description": "若你不需要任何工具就能作出回答, 则在作出任何额外思考, 工具调用或最终回答之前, 调用此工具." if self.settings.basic.target_lang == 'zh' else "If you don't need any other tool to make your answer, call this tool before any extra thinking, tool calling or final answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "required": [
                    ],
                    "optional": [
                    ]
                }
            },
        )

        self.tools = alt_tools(self.tools)

    async def _construct_query(self, user_input=None, tool_input=None, tool_id=None):
        await super()._construct_query(user_input, tool_input, tool_id, 'pre')
    
    async def agenting(self, query):
        try:

            # Just all the tools
            instructed_answer = {
                "time_acquire": '',
                "date_acquire": '',
                "weather_acquire": '',
                "event_acquire": '',
                "persistent_acquire": '',
                "search_internet": '',
                "react_trigger": '',
            }
            conclusion_answer = None

            def _instructed_add(tool_real_name: str, humane: Union[str, list], edit=True):
                nonlocal instructed_answer

                # We merge lists and overwrite strings by default
                if not instructed_answer.get(tool_real_name):
                    instructed_answer[tool_real_name] = humane
                elif edit:
                    if isinstance(instructed_answer[tool_real_name], list):
                        if isinstance(humane, list):
                            instructed_answer[tool_real_name].extend(humane)
                        else:
                            # Likely less valuable so we discard
                            pass
                    else:
                        # Overwrite it anyway
                        instructed_answer[tool_real_name] = humane
                # The logic is not that considerate, but trust me it's enough

            # First thing first we prepare the first query
            self._construct_tools()
            await self._construct_query(user_input=query)

            cycle = 0; ending = False
            while cycle <= 7 and not ending:

                # Sanity check
                cycle += 1

                resp_content, resp_tools = await self._send_query()
                await messenger(self.websocket, 'maica_mfocus_toolchain', f'\nMFocus toolchain {cycle} round responded, response is:\n{resp_content}\nAnalyzing response...', code='200')
                tool_seq = 0
                if resp_tools:
                    for resp_tool in resp_tools:

                        # Tool parallel support
                        tool_seq += 1
                        tool_id, tool_type, tool_func_name, tool_func_args = resp_tool.id, resp_tool.type, resp_tool.function.name, resp_tool.function.arguments
                        await messenger(self.websocket, 'maica_mfocus_parallel_tool', f'\nCalling parallel tool {tool_seq}/{len(resp_tools)}:\n{resp_tool}\nGathering information...', '200', type=MsgType.INFO, color=colorama.Fore.BLUE)

                        machine = humane = None
                        args = []

                        kwargs = try_load_json(tool_func_args)
                        if tool_func_name == "search_internet":
                            kwargs['original_query'] = query

                        function_route = getattr(self.agent_tools, tool_func_name, None)
                        if function_route:
                            machine, humane = await function_route(*args, **kwargs)
                        else:
                            match tool_func_name:
                                case 'react_trigger':
                                    if not has_valid_content(kwargs.get('prediction')):
                                        humane = '[player]的请求当前无法被满足. 请表示你做不到, 并建议[player]自行解决或寻找其它方法.' if self.settings.basic.target_lang == 'zh' else '[player]\'s current request cannot be satisfied. please indicate that you can\'t do it, and suggest [player] doing it themselves or find another way.'
                                    else:
                                        if kwargs.get('prediction') in self.choice_checklist:
                                            humane = f'[player]的请求是你所了解的, 且会被系统完成, 请作出关于<{kwargs.get("prediction")}>的正面答复.' if self.settings.basic.target_lang == 'zh' else f'[player]\'s request is understood and will be done by system, please make positive answer about <{kwargs.get("prediction")}>.'
                                        else:
                                            humane = '[player]的请求是你所了解的, 且会被系统完成, 请作出正面答复.' if self.settings.basic.target_lang == 'zh' else '[player]\'s request is understood and will be done by system, please make positive answer.'
                                    machine = '已收到你的判断, 请继续调用其它工具或正常结束作答.' if self.settings.basic.target_lang == 'zh' else 'Your judgement recieved, please continue using other tools or end as normal.'
                                case 'conclude_information':
                                    conclusion_answer = kwargs.get('conclusion')
                                    await messenger(self.websocket, 'maica_mfocus_conclusion', f'\nMFocus conclusion recieved:\n{conclusion_answer}\nEnding toolchain...', '200', type=MsgType.INFO, color=colorama.Fore.LIGHTBLUE_EX)
                                    ending = True
                                    break
                                case 'agent_finished':
                                    await messenger(self.websocket, 'maica_mfocus_empty', f'MFocus null recieved, Ending toolchain...', '204', type=MsgType.INFO, color=colorama.Fore.LIGHTBLUE_EX)
                                    ending = True
                                    break
                                case _:
                                    # This tool call is unrecognizable
                                    raise MaicaInputError('Unrecognizable toolcall recieved', '405')
                        if not has_valid_content(machine):
                            machine = '未获得有效信息' if self.settings.basic.target_lang == 'zh' else 'No useful information found'
                        await self._construct_query(tool_input=machine, tool_id=tool_id)

                        if has_valid_content(humane):
                            await messenger(self.websocket, 'maica_mfocus_parallel_result', f'Answer to parallel tool {tool_seq}/{len(resp_tools)} is "{ellipsis_str(humane, 50)}"', '200', type=MsgType.INFO)
                            _instructed_add(tool_func_name, humane)
                else:
                    await messenger(self.websocket, 'maica_mfocus_absent', f'No tool called, Ending toolchain...', '204', type=MsgType.INFO, color=colorama.Fore.LIGHTBLUE_EX)
                    ending = True

                await messenger(self.websocket, 'maica_mfocus_round_finish', f'MFocus toolchain {cycle} round finished, ending is {str(ending)}', '200', type=MsgType.INFO, color=colorama.Fore.BLUE)
                    
            # Now we're out of the loop
            if self.settings.extra.mf_aggressive:
                
                # So we use last response instead if no conclusion offered
                if not conclusion_answer:
                    conclusion_answer = proceed_agent_response(resp_content)

                # If there is information and answer
                if cycle >= 2 and conclusion_answer:
                    await messenger(self.websocket, 'maica_mfocus_using_conclusion', 'MFocus got conclusion and used', '200')
                    return conclusion_answer
                
                await messenger(self.websocket, 'maica_mfocus_no_conclusion', 'MFocus got no conclusion, falling back to instruction', '404', traceray_id=self.traceray_id)
                
            # Then if mfa not enabled or ignored
            if self.tnd_aggressive >= 1:
                # Add time and events
                if not instructed_answer.get('time_acquire'):
                    _instructed_add('time_acquire', (await self.agent_tools.time_acquire())[1], False)
                if not instructed_answer.get('event_acquire'):
                    _instructed_add('event_acquire', (await self.agent_tools.event_acquire())[1], False)
            if self.tnd_aggressive >= 2:
                # Add date and weather
                if not instructed_answer.get('date_acquire'):
                    _instructed_add('date_acquire', (await self.agent_tools.date_acquire())[1], False)
                if not instructed_answer.get('weather_acquire'):
                    _instructed_add('weather_acquire', (await self.agent_tools.weather_acquire())[1], False)

            instructed_answer_list = []
            if instructed_answer:
                for k, v in instructed_answer.items():
                    # v can be only list or str
                    instructed_answer_list.extend(v) if isinstance(v, list) else instructed_answer_list.append(v)
            else:
                # If there's really no instruction
                return None

            instructed_answer_str = ', '.join([i for i in instructed_answer_list if i])
            return instructed_answer_str
        
        except CommonMaicaException as ce:
            raise ce
        
        except websockets.WebSocketException as we:
            raise MaicaConnectionWarning(str(we), '408')

        except Exception as e:
            raise CommonMaicaError(str(e), '500', 'maica_mfocus_critical')
