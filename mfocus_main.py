import re
import json
import random
import datetime
import traceback
import asyncio
import functools
import nest_asyncio
import maica_ws
import agent_modules
from openai import AsyncOpenAI # type: ignore
from loadenv import load_env

async def wrap_run_in_exc(loop, func, *args, **kwargs):
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs))
    return result

async def agenting(parent, input, chat_session, bypass_mt=False):
    #nest_asyncio.apply()
    if parent:
        sf_extraction, deformation, target_lang = parent.options['opt']['sf_extraction'] or parent.options['temp']['sf_extraction_once'], parent.options['opt']['deformation'], parent.options['opt']['target_lang']
        pre_additive, tnd_aggressive, mf_aggressive, esc_aggressive, amt_aggressive, tz = parent.options['eopt']['pre_additive'], parent.options['eopt']['tnd_aggressive'], parent.options['eopt']['mf_aggressive'], parent.options['eopt']['esc_aggressive'], parent.options['eopt']['amt_aggressive'], parent.options['eopt']['tz']
        websocket = parent.websocket
        sf_inst, mt_inst = parent.sf_inst, parent.mt_inst
        session = parent.options['vfc']
        client = parent.sock2
    else:
        # These are testing values
        sf_extraction = True
        deformation = False
        session = {"user_id": 23, "username": "edge"}
        target_lang = 'zh'
        pre_additive = 0
        tnd_aggressive = 1
        mf_aggressive = True
        esc_aggressive = True
        amt_aggressive = True
        websocket = None
        import mfocus_sfe
        sf_inst = mfocus_sfe.sf_bound_instance(23,1,target_lang)
        await sf_inst.init1()
        mt_inst = None
        client = AsyncOpenAI(
            api_key='EMPTY',
            base_url=load_env('MFOCUS_ADDR'),
        )
        tz = target_lang
    if websocket:
        loop = asyncio.get_event_loop()
    if mt_inst and not bypass_mt:
        trigger_list = await wrap_run_in_exc(None, mt_inst.get_valid_triggers)
    else:
        trigger_list = None
    
    model_list = await client.models.list()
    model_type = model_list.data[0].id
    print(f'MFocus main addressing model, response is:\n{model_type}\nEnd of MFocus main addressing model')
    tools =  [
        {
            "name": "time_acquire",
            "description": "调用该工具以获取当前时间. 只要对话关于: 时间, 问候, 三餐, 休息, 生活节律与建议等, 或你需要获取当前时间以帮助回答, 就使用此工具查询时间." if target_lang == 'zh' else "Call this tool to get the current time. Always use this tool if the conversation mentions: time, greeting, meals, sleep, rest, pace of life or related suggestions, or if you want to know the current time to make your answer.",
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
            "description": "调用该工具以获取当前日期. 只要对话关于: 日期, 季节, 年份, 或你需要获取当前日期以帮助回答, 就使用此工具查询日期." if target_lang == 'zh' else "Call this tool to get the current date. Always use this tool if the conversation mentions: date, season, year, or if you want to know the current date to make your answer.",
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
            "description": "调用该工具以获取当前天气. 只要对话关于: 天气, 通勤, 户外活动, 或你需要获取当前天气以帮助回答, 就使用此工具查询天气." if target_lang == 'zh' else "Call this tool to get the current weather. Always use this tool if the conversation mentions: weather, commuting, outdoor activities, or if you need to know the current weather to make your answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "你需要查询天气的地理位置. 如果查询用户本地天气, 则留空." if target_lang == 'zh' else "The location which you need to get the weather of. Leave empty for the user's local weather.",
                        "example_value": "湖北武汉" if target_lang == 'zh' else "Los Angeles"
                    },
                },
                "required": [
                ],
                "optional": [
                ]
            }
        },
        {
            "name": "event_acquire",
            "description": "调用该工具以查询当前或指定日期的节日或事件. 只要对话关于: 日期, 节日, 活动, 假期, 或你需要获取指定的事件以帮助回答, 就使用此工具查询节日或事件." if target_lang == 'zh' else "Call this tool to get the event or holiday of a given date or current date. Always use this tool if the conversation mentions: date, holiday, anniversary, activities, vacation, or if you need to know the specific event to make your answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "int",
                        "description": "需要查询日期的年份. 如果日期在今年, 则留空." if target_lang == 'zh' else "The year of the given date, leave empty for this year.",
                        "example_value": "2003"
                    },
                    "month": {
                        "type": "int",
                        "description": "需要查询日期的月份. 如果日期在本月, 则留空." if target_lang == 'zh' else "The month of the given date, leave empty for this month.",
                        "example_value": "6"
                    },
                    "day": {
                        "type": "int",
                        "description": "需要查询日期的日数. 如果日期在本日, 则留空." if target_lang == 'zh' else "The day of the given date, leave empty for the day today.",
                        "example_value": "26"
                    }
                },
                "required": [
                ],
                "optional": [
                    "year",
                    "month",
                    "day"
                ]
            }
        },
        {
            "name": "persistent_acquire",
            "description": "调用该工具以查询你(莫妮卡)或用户的记忆, 例如你或用户的喜好, 兴趣, 经历, 体验, 关系或个人信息. 只要你被问及你作为AI不具有的记忆, 经历, 个性, 喜好或其它事物, 就使用此工具查找记忆. " if target_lang == 'zh' else "Call this tool to get any additional information from your(Monika's) memory or user's memory, such as your or user's preferences, hobbies, experiences, appearence, relationship or personal information. Always use this tool if the conversation mentions memories, personality, preferences, hobbies, experience or any other thing you don't have as an AI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "需要从你或用户的记忆中搜索的信息, 以尽可能直接回答问题. 以第三人称方式提出问题, 不要提及'我'或'我们'." if target_lang == 'zh' else "The question you want to search from your memory or user's memory, to answer the question as directly as possible. Ask in third person perspective, do not use appellation 'I', 'me' or 'us'.",
                        "example_value": "莫妮卡喜欢吃什么?" if target_lang == 'zh' else "What does Monika like to eat?"
                    }
                },
                "required": [
                    "question"
                ],
                "optional": [
                ]
            }
        },
        {
            "name": "search_internet",
            "description": "调用该工具以搜索互联网. 如果你需要联网搜索信息以帮助回答, 则使用该工具搜索互联网. 如果该信息可以通过其它工具获取, 则优先使用其它工具." if target_lang == 'zh' else "Call this tool to search a question on the Internet. Use this tool if you need information from the Internet to make your answer. If another tool avaliable could provide the information, use that tool instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "需要在搜索引擎中搜索的问题, 应当是一个简洁的句子." if target_lang == 'zh' else "The question needs to be searched on Google, which should be a simple sentence.",
                        "example_value": "附近的餐馆" if target_lang == 'zh' else "Nearby restaurants"
                    }
                },
                "required": [
                    "question"
                ],
                "optional": [
                ]
            }
        },
    ]
    if trigger_list and amt_aggressive:
        choice_list = []; choice_checklist = []; choice_conclusion = []
        for trigger in trigger_list:
            match trigger['template']:
                case 'common_affection_template':
                    pass
                case 'common_switch_template':
                    cst_temp_list = []
                    for i in trigger['exprop']['item_list']:
                        choice_checklist.append(i)
                        j = f'选择{i}' if target_lang == 'zh' else f'switch to {i}'
                        cst_temp_list.append(j)
                    if 'suggestion' in trigger['exprop'] and trigger['exprop']['suggestion']:
                        comj = f"选择任意的{trigger['exprop']['item_name']['zh']}" if target_lang == 'zh' else f"Choose any other {trigger['exprop']['item_name']['en']}"
                        cst_temp_list.append(j)
                    cst_explaination = f"更换{trigger['exprop']['item_name']['zh']}" if target_lang == 'zh' else f"Change {trigger['exprop']['item_name']['en']}"
                    choice_list.append({cst_explaination: cst_temp_list})
                case 'common_meter_template':
                    cmt_iname = trigger['exprop']['item_name']['zh'] if target_lang == 'zh' else trigger['exprop']['item_name']['en']
                    choice_checklist.append(cmt_iname)
                    j = f"调整{cmt_iname}, 范围是{trigger['exprop']['value_limits'][0]}到{trigger['exprop']['value_limits'][1]}" if target_lang == 'zh' else f"Adjust {cmt_iname} within range {trigger['exprop']['value_limits'][0]} to {trigger['exprop']['value_limits'][1]}"
                    choice_list.append(j)
                case _:
                    cc_iname = trigger['usage']['zh'] if target_lang == 'zh' else trigger['usage']['en']
                    choice_checklist.append(cc_iname)
                    j = f"触发{cc_iname}" if target_lang == 'zh' else f"Trigger {cc_iname}"
                    choice_list.append(j)
        if choice_list:
            tools.append(
                {
                    "name": "react_trigger",
                    "description": "此工具能检验用户的特定要求可否完成. 如果用户对你提出以下类别请求: 切换(如换衣服, 换地点, 换场景), 调整(如调距离, 调亮度), 触发(如开灯, 开启某模式), 则调用该工具." if target_lang == 'zh' else "This tool can verify if user's specific request can be done. If user is requesting you to: switching(like changing your clothes, changing location, changing scene), adjusting(like adjusting distance, adjusting brightness), triggering(like turning on light, turning on some mode), use this tool.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prediction": {
                                "type": "string",
                                "description": f"你将收到一系列可用选项. 若某选项能够满足用户的请求, 则输出该选项, 否则输出false. 以下是可用选项: {str(choice_list)}" if target_lang == 'zh' else f"You'll be offered a list of avaliable choices. return the choice if you think it matches the query, or return false if none matches. Avaliable choices: {str(choice_list)}",
                                "example_value": random.choice(choice_checklist)
                            }
                        },
                        "required": [
                            "ability"
                        ],
                        "optional": [
                        ]
                    }
                },
            )
    if mf_aggressive:
        tools.append(
            {
                "name": "conclude_information",
                "description": "此工具用于总结你的输出. 只要你已获取了所有必要信息且准备好作答, 就在作答前调用该工具." if target_lang == 'zh' else "This tool can conclude your outputs. Always use this tool if you have acquired all necessary informations before making final answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conclusion": {
                            "type": "string",
                            "description": "总结你获取的信息和作出的推理, 并整理成一个简洁的句子." if target_lang == 'zh' else "Conclude all information you have acquired and reasonings you have made into a concise sentence.",
                            "example_value": "现在是上午九点, 因此适合吃早餐, 且天气凉爽, 因此适合户外活动."  if target_lang == 'zh' else "It's 9:00 in the morning, suitable for breakfast. The weather is cool, good for exercising."
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
    else:
        tools.append(
            {
                "name": "none",
                "description": "若你不需要任何工具就能作出回答, 则先调用此工具." if target_lang == 'zh' else "If you don't need any other tool to make your answer, call this tool before final answer.",
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
    messages = []
    if pre_additive and 1 <= chat_session <= 9:
        sql_expression = 'SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s'
        result = await parent.send_query(expression=sql_expression, values=(session['user_id'], chat_session), pool='maicapool')
        if result:
            res_dict = json.loads(f'[{result[3]}]')
            lines_num = min(pre_additive * 2, len(res_dict) - 1)
            message_additive = res_dict[-lines_num:] if lines_num > 0 else []
            if message_additive:
                messages.append({'role': 'system', 'content': '\n请按照指示格式回答, 对话历史仅供参考.'}  if target_lang == 'zh' else {'role': 'system', 'content': 'Answer according to the format guidance, the chat history is just a reference.'})
                messages.extend(message_additive)
    messages.append({'role': 'user', 'content': input})
    completion_args = {
        "model": model_type,
        "messages": messages,
        "tools": tools,
        "stop": ['Observation:'],
        "temperature": 0.2,
        "top_p": 0.6,
        "presence_penalty": 0.4,
        "frequency_penalty": 0.5,
        "seed": 42
    }
    if not mf_aggressive:
        completion_args['stop'].append('Final Answer:')

    for tries in range(0, 2):
        try:
            resp = await client.chat.completions.create(**completion_args)
            response = resp.choices[0].message.content
        except:
            if tries < 1:
                print('Model temporary failure')
                await asyncio.sleep(100)
            else:
                raise Exception('Model connection failure')
                    
    #print(resp.choices[0].message.tool_calls)
    if resp.choices[0].message.tool_calls:
        tool_calls = resp.choices[0].message.tool_calls[0]
    else:
        tool_calls = None
    if tool_calls and tool_calls.function.name != 'none':
        response_str1 = f'MFocus main 1st round finished, response is:\n{response}\nEnd of MFocus main 1st round.'
        response_str2 = f'Acquiring tool call from MFocus main 1st round, response is:\n{tool_calls}\nEnd of tool call acquiration.'
    else:
        response_str1 = f'MFocus main 1st round finished, response is:\n{response}\nEnding due to returning none or corruption.'
        response_str2 = f'No tool called by MFocus.'
    if websocket:
        await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_injecting', response_str1, 'debug', deformation))
        await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_toolcall', response_str2, 'info', deformation))
    print(response_str1)
    print(response_str2)
  

    final_answer = ''
    instructed_final_answer = {}
    return_instruction = ''
    inst_wea = inst_time = inst_date = inst_event = inst_pst = inst_search = inst_rct = inst_conc = False
    if int(tnd_aggressive) >= 1:
        instructed_final_answer['time'] = f"[{(await agent_modules.time_acquire(None, target_lang, tz))[3]}]"
        instructed_final_answer['event'] = f"[{(await agent_modules.event_acquire(None, sf_extraction, sf_inst, -1, False, target_lang, tz))[3]}]"
    if int(tnd_aggressive) >= 2:
        instructed_final_answer['date'] = f"[{(await agent_modules.date_acquire(None, sf_extraction, sf_inst, target_lang, tz))[3]}]"
        if sf_inst.read_from_sf('mas_geolocation')[2]:
            instructed_final_answer['weather'] = f"[{(await agent_modules.weather_acquire(None, sf_extraction, sf_inst, target_lang))[3]}]"
    instructed_first_answer = instructed_final_answer
    # to be extended
    cycle = 0
    while tool_calls and tool_calls.function.name != 'none':
        cycle += 1
        if cycle >= 7:
            break
            # something must have went wrong
        exception_return = ''
        # to be added
        try:
            predict_action_function = tool_calls.function.name
            try:
                real_parameters_dict = json.loads(re.search(r'(\{.*\})', re.sub(r"(?!=\\)'", '"', tool_calls.function.arguments))[1])
            except:
                real_parameters_dict = {"common": tool_calls.function.arguments}
            if re.search((r'time.*acquire'), predict_action_function, re.I):
                time_acquired = await agent_modules.time_acquire(real_parameters_dict, target_lang, tz)
                if time_acquired[0]:
                    return_instruction = f"[{{'time': '{time_acquired[2]}'}}]"
                    if time_acquired[3]:
                        instructed_final_answer['time'] = f"[{time_acquired[3]}]"
                        inst_time = True
                else:
                    raise Exception(time_acquired[1])
            elif re.search((r'date.*acquire'), predict_action_function, re.I):
                date_acquired = await agent_modules.date_acquire(real_parameters_dict, sf_extraction, sf_inst, target_lang, tz)
                if date_acquired[0]:
                    return_instruction = f"[{{'date': '{date_acquired[2]}'}}]"
                    if date_acquired[3]:
                        instructed_final_answer['date'] = f"[{date_acquired[3]}]"
                        inst_date = True
                else:
                    raise Exception(date_acquired[1])
            elif re.search((r'weather.*acquire'), predict_action_function, re.I):
                weather_acquired = await agent_modules.weather_acquire(real_parameters_dict, sf_extraction, sf_inst, target_lang)
                if weather_acquired[0]:
                    return_instruction = f"[{{'weather': '{weather_acquired[2]}'}}]"
                    if weather_acquired[3]:
                        instructed_final_answer['weather'] = f"[{weather_acquired[3]}]"
                        inst_wea = True
                else:
                    raise Exception(weather_acquired[1])
            elif re.search((r'event.*acquire'), predict_action_function, re.I):
                event_acquired = await agent_modules.event_acquire(real_parameters_dict, sf_extraction, sf_inst, -1, True, target_lang, tz)
                if event_acquired[0]:
                    return_instruction = f"[{{'event': '{event_acquired[2]}'}}]"
                    if event_acquired[3]:
                        instructed_final_answer['event'] = f"[{event_acquired[3]}]"
                        inst_event = True
                else:
                    raise Exception(event_acquired[1])
            elif re.search((r'persistent.*acquire'), predict_action_function, re.I):
                persistent_acquired = await agent_modules.persistent_acquire(real_parameters_dict, sf_extraction, session, chat_session, sf_inst, target_lang)
                if persistent_acquired[0]:
                    return_instruction = f"[{{'known_info': {persistent_acquired[2]}}}]"
                    if persistent_acquired[3]:
                        if 'persistent' in instructed_final_answer:
                            persis_old_list = json.loads(re.sub("'",'"',instructed_final_answer['persistent']))
                            persis_new_list = json.loads(re.sub("'",'"',persistent_acquired[3]))
                            for item_plus in persis_new_list:
                                if not item_plus in persis_old_list:
                                    persis_old_list.append(item_plus)
                            instructed_final_answer['persistent'] = re.sub('"',"'",json.dumps(persis_old_list, ensure_ascii=False))
                        else:
                            instructed_final_answer['persistent'] = f'{persistent_acquired[3]}'
                        inst_pst = True
                else:
                    raise Exception(persistent_acquired[1])
            elif re.search((r'search.*internet'), predict_action_function, re.I):
                internet_acquired = await agent_modules.internet_acquire(real_parameters_dict, sf_extraction, sf_inst, input, esc_aggressive, target_lang)
                if internet_acquired[0]:
                    return_instruction = f"[{{'search_result': '{internet_acquired[2]}'}}]"
                    if internet_acquired[3]:
                        instructed_final_answer['internet'] = f'"{internet_acquired[3]}"'
                        inst_search= True
                else:
                    raise Exception(internet_acquired[1])
            elif re.search((r'react.*trigger'), predict_action_function, re.I):
                trigger_ability = real_parameters_dict[list(real_parameters_dict.keys())[0]]
                return_instruction = f"[{{'reaction_correct': True}}]"
                if not trigger_ability or (isinstance(trigger_ability, str) and trigger_ability.lower() == "false"):
                    instructed_final_answer['trigger'] = '"[player]的请求当前无法被满足. 请表示你做不到, 并建议[player]自行解决或寻找其它方法."' if target_lang == 'zh' else '"[player]\'s current request cannot be satisfied. please indicate that you can\'t do it, and suggest [player] doing it themselves or find another way."'
                else:
                    if str(trigger_ability).lower() in str(choice_checklist).lower():
                        choice_conclusion.append(str(trigger_ability))
                        instructed_final_answer['trigger'] = f'"[player]的请求是你所了解的, 且会被系统完成, 请作出关于{', '.join(choice_conclusion)}的正面答复."' if target_lang == 'zh' else f'"[player]\'s request is understood and will be done by system, please make positive answer about {', '.join(choice_conclusion)}."'
                        inst_rct = True
                    elif not inst_rct:
                        instructed_final_answer['trigger'] = '"[player]的请求是你所了解的, 且会被系统完成, 请作出正面答复."' if target_lang == 'zh' else '"[player]\'s request is understood and will be done by system, please make positive answer."'
                #print(real_parameters_dict)
                inst_rct = True
            elif re.search((r'conclude.*information'), predict_action_function, re.I):
                #print(real_parameters_dict)
                conc_final_answer = f"\"{real_parameters_dict[list(real_parameters_dict.keys())[0]]}\""
                inst_conc = True
                raise Exception('Final conclusion provided, making early break')
            else:
                raise Exception('No function matched, making early break')
        except Exception as excepted:
            exception_return = excepted
            #traceback.print_exc()
            print(f'MFocus main early broke: {exception_return}')
        if not exception_return:
            print(f"MFocus acquired instruction: {return_instruction}")
            messages.append({'role': 'assistant', 'content': response})
            messages.append({'role': 'tool', 'content': return_instruction})

            for tries in range(0, 2):
                try:
                    resp = await client.chat.completions.create(**completion_args)
                    response = resp.choices[0].message.content
                except:
                    if tries < 1:
                        print('Model temporary failure')
                        await asyncio.sleep(100)
                    else:
                        raise Exception('Model connection failure')

            if resp.choices[0].message.tool_calls:
                if resp.choices[0].message.tool_calls[0].function:
                    if resp.choices[0].message.tool_calls[0].function == tool_calls.function:
                        print('Total repetition detected, aborting')
                        break
            if resp.choices[0].message.tool_calls:
                tool_calls = resp.choices[0].message.tool_calls[0]
            else:
                tool_calls = None
            if tool_calls:
                response_str1 = f'MFocus main {cycle+1}nd/rd/th round finished, response is:\n{response}\nEnd of MFocus main following round.'
                response_str2 = f'Acquiring tool call from MFocus main {cycle+1}nd/rd/th round, response is:\n{tool_calls}\nEnd of tool call acquiration.'
            else:
                response_str1 = f'MFocus main {cycle+1}nd/rd/th round finished, response is:\n{response}\nEnding due to returning none or corruption.'
                response_str2 = f'No tool called by MFocus.'
            if websocket:
                await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_injecting', response_str1, 'debug', deformation))
                await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_toolcall', response_str2, 'info', deformation))
            print(response_str1)
            print(response_str2)
            if not tool_calls:
                break
        else:
            break
    #print(instructed_final_answer)
    if 'persistent' in instructed_final_answer:
        instructed_final_answer['persistent'] = f"\"{str(instructed_final_answer['persistent']).strip('[').strip(']')}\""
    instructed_final_answer_joined = ''.join(str(x) for x in instructed_final_answer.values())
    if inst_time and 'time' in instructed_first_answer:
        instructed_first_answer.pop('time')
    if inst_event and 'event' in instructed_first_answer:
        instructed_first_answer.pop('event')
    if inst_date and 'date' in instructed_first_answer:
        instructed_first_answer.pop('date')
    if inst_wea and 'weather' in instructed_first_answer:
        instructed_first_answer.pop('weather')
    for key in instructed_first_answer.keys():
        final_answer += instructed_first_answer[key]
    if inst_conc:
        fin_final_answer = final_answer + '"' + conc_final_answer + '"'
    else:
        try:
            conc_final_answer = re.search((r'\s*Final\s*Answer\s*:\s*(.*)\s*$'), response, re.I|re.S)[1]
            fin_final_answer = final_answer + '"' + conc_final_answer + '"'
        except:
            fin_final_answer = ''
    if mf_aggressive and instructed_final_answer_joined:
        response_str3 = f"MFocus callback achieved, response is:\n{fin_final_answer}\nInfo acquired are:\n{instructed_final_answer_joined}\nEnd of MFocus callback."
        if websocket: await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_done', response_str3, 'info', deformation))
        print(response_str3)
        return fin_final_answer, instructed_final_answer_joined
    elif instructed_final_answer_joined:
        response_str3 = f"MFocus falling back, Info acquired are:\n{instructed_final_answer_joined}\nEnd of MFocus callback."
        if websocket: await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_done', response_str3, 'info', deformation))
        print(response_str3)
        return 'EMPTY', instructed_final_answer_joined
    else:
        response_str3 = f"MFocus failed or missed, Ending MFocus callback."
        if websocket: await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_done', response_str3, 'info', deformation))
        print(response_str3)
        return 'FAIL', ''

if __name__ == "__main__":
    import time
    start_time = time.time()
    agented = asyncio.run(agenting(None, '你记得我的生日吗', 1))
    print(agented[0])
    print(agented[1])
    end_time = time.time()
    print(f"AbstractGpuConsume: {end_time-start_time}")


"""
{'role': 'system', 'content': system_init}
"""