import re
import json
import datetime
import traceback
import asyncio
import nest_asyncio
import maica_ws
import agent_modules
import persistent_extraction
from openai import AsyncOpenAI # type: ignore
from loadenv import load_env
async def agenting(parent, input, chat_session):
    #nest_asyncio.apply()
    if parent:
        sf_extraction, target_lang = parent.options['opt']['sf_extraction'], parent.options['opt']['target_lang']
        pre_additive, tnd_aggressive, mf_aggressive, esc_aggressive = parent.options['eopt']['pre_additive'], parent.options['eopt']['tnd_aggressive'], parent.options['eopt']['mf_aggressive'], parent.options['eopt']['esc_aggressive']
        websocket = parent.websocket
        session = parent.options['vfc']
    else:
        # These are testing values
        sf_extraction = False
        session = [0, 0, 23]
        target_lang='zh'
        pre_additive=0
        tnd_aggressive=1
        mf_aggressive=False
        esc_aggressive=True
        websocket=None
    if websocket:
        loop = asyncio.get_event_loop()
    client = AsyncOpenAI(
        api_key='EMPTY',
        base_url=load_env('MFOCUS_ADDR'),
    )
    model_list = await client.models.list()
    model_type = model_list.data[0].id
    print(f'MFocus main addressing model, response is:\n{model_type}\nEnd of MFocus main addressing model')
    tools =  [
        {
            "name": "time_acquire",
            "description": "Call this tool to get the current time. 只要对话关于: 时间; 问候; 三餐; 休息, 就使用此工具查询时间. Always use this tool if the conversation mentions: time, greeting, meals, sleep, rest.",
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
            "description": "Call this tool to get the current date. 只要对话关于: 日期; 季节; 年份, 就使用此工具查询日期. Always use this tool if the conversation mentions: date, season, year.",
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
            "description": "Call this tool to get the current weather. 只要对话关于: 天气; 通勤; 户外活动, 就使用此工具查询天气. Always use this tool if the conversation mentions: weather, commuting, outdoor activities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location which you need to get the weather of, using Chinese. Leave empty for local weather. 如果查询本地天气, 则留空.",
                        "example_value": "湖北武汉"
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
            "description": "Call this tool to get the event or holiday of a given date. 只要对话关于: 日期; 节日; 活动; 假期, 就使用此工具查询节日. Always use this tool if the conversation mentions: date, holiday, anniversary, activities, vacation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "int",
                        "description": "The year of the given date, leave empty for the year now. 如果问题涉及今年, 则留空.",
                        "example_value": "2024"
                    },
                    "month": {
                        "type": "int",
                        "description": "The month of the given date, leave empty for the month now. 如果问题涉及本月, 则留空.",
                        "example_value": "6"
                    },
                    "day": {
                        "type": "int",
                        "description": "The day of the given date, leave empty for the day today. 如果问题涉及今天, 则留空.",
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
            "description": "Call this tool to get any additional information about user and yourself as human character, such as their preferences, hobbies, experiences, appearence or relationship. 只要你被问及你作为AI不具有的记忆, 经历, 人格, 感情, 喜好或任何其它事物, 就使用此工具查找记忆. Always use this tool if the conversation mentions memories, humanity, preferences, hobbies, experience or any other thing you don't have as an AI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question you want to know about user or yourself as human character, which is called Monika. 若问题关于你的角色则以'莫妮卡'发问, 若问题关于用户则以'你'发问. Ask about 'Monika' for information about yourself as human character, ask about 'you' for information about user.",
                        "example_value": "莫妮卡喜欢吃什么?"
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
            "description": "Call this tool to interact with the internet search API. This API will search your question on the internet. 当回答问题需要时效性, 地区性, 知识性的信息或解释人名, 地名, 专有名词, 使用此工具查询. Use this tool if regional, informative, timely information or explaination of specific name, location or proper noun is needed to answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question needs to be searched on Google, which should not be too detailed.",
                        "example_value": "附近有哪些餐馆"
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
            "name": "none",
            "description": "Call this tool if no tool is needed to answer. 若你不需要任何工具就能作出回答, 则使用此工具.",
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
    ]
    if mf_aggressive:
        tools.append(
        {
            "name": "conclude_information",
            "description": "Call this tool if you have used every necessary tool and ready to give final answer. 若你已经使用了所有必要的工具并准备好给出最终答案, 则使用此工具.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conclusion": {
                        "type": "string",
                        "description": "Conclude all information you have acquired and reasonings you have made into a concise sentence.",
                        "example_value": "现在是上午九点, 适合吃早餐, 且天气凉爽, 适合户外活动"
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
    messages = []
    if pre_additive:
        sql_expression = 'SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s'
        result = await parent.send_query(expression=sql_expression, values=(session['user_id'], chat_session), pool='maicapool')
        res_dict = json.loads(f'[{result[3]}]')
        lines_num = min(pre_additive * 2, len(res_dict) - 1)
        message_additive = res_dict[-lines_num:] if lines_num > 0 else []
        if message_additive:
            messages.append({'role': 'system', 'content': '请按照指示格式回答, 对话历史仅供参考.'})
            messages.extend(message_additive)
    messages.append({'role': 'user', 'content': input})
    completion_args = {
        "model": model_type,
        "messages": messages,
        "tools": tools,
        "stop": ['Observation:'],
        "temperature": 0.1,
        "top_p": 0.6,
        "presence_penalty": -0.5,
        "frequency_penalty": 0.5,
        "seed": 42
    }
    if not mf_aggressive:
        completion_args['stop'].append('Final Answer:')
    resp = await client.chat.completions.create(**completion_args)
    response = resp.choices[0].message.content
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
        await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_injecting', response_str1, 'debug'))
        await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_toolcall', response_str2, 'debug'))
    print(response_str1)
    print(response_str2)
  

    final_answer = ''
    instructed_final_answer = {}
    inst_wea = inst_time = inst_date = inst_event = inst_pst = inst_search = inst_conc = False
    if int(tnd_aggressive) >= 1:
        instructed_final_answer['time'] = f"[{(await agent_modules.time_acquire(None, target_lang))[3]}]"
        instructed_final_answer['event'] = f"[{(await agent_modules.event_acquire({'year': datetime.date.today().year, 'month': datetime.date.today().month, 'day': datetime.date.today().day}, sf_extraction, session, chat_session, -1, False, target_lang))[3]}]"
    if int(tnd_aggressive) >= 2:
        instructed_final_answer['date'] = f"[{(await agent_modules.date_acquire(None, sf_extraction, session, chat_session, target_lang))[3]}]"
        if persistent_extraction.read_from_sf(session['user_id'], chat_session, 'mas_geolocation')[2]:
            instructed_final_answer['weather'] = f"[{(await agent_modules.weather_acquire(None, sf_extraction, session, chat_session, target_lang))[3]}]"
    instructed_first_answer = instructed_final_answer
    # to be extended
    cycle = 0
    while tool_calls:
        cycle += 1
        if cycle >= 7:
            break
            # something must have went wrong
        exception_return = ''
        # to be added
        return_instruction = ''
        try:
            predict_action_function = tool_calls.function.name
            try:
                real_parameters_dict = json.loads(re.search(r'(\{.*\})', re.sub(r"(?!=\\)'", '"', tool_calls.function.arguments))[1])
            except:
                real_parameters_dict = {"common": tool_calls.function.arguments}
            if re.search((r'time.*acquire'), predict_action_function, re.I):
                time_acquired = await agent_modules.time_acquire(real_parameters_dict, target_lang)
                if time_acquired[0]:
                    return_instruction = f"[{{'time': '{time_acquired[2]}'}}]"
                    if time_acquired[3]:
                        instructed_final_answer['time'] = f"[{time_acquired[3]}]"
                        inst_time = True
                else:
                    raise Exception(time_acquired[1])
            elif re.search((r'date.*acquire'), predict_action_function, re.I):
                date_acquired = await agent_modules.date_acquire(real_parameters_dict, sf_extraction, session, chat_session, target_lang)
                if date_acquired[0]:
                    return_instruction = f"[{{'date': '{date_acquired[2]}'}}]"
                    if date_acquired[3]:
                        instructed_final_answer['date'] = f"[{date_acquired[3]}]"
                        inst_date = True
                else:
                    raise Exception(date_acquired[1])
            elif re.search((r'weather.*acquire'), predict_action_function, re.I):
                weather_acquired = await agent_modules.weather_acquire(real_parameters_dict, sf_extraction, session, chat_session, target_lang)
                if weather_acquired[0]:
                    return_instruction = f"[{{'weather': '{weather_acquired[2]}'}}]"
                    if weather_acquired[3]:
                        instructed_final_answer['weather'] = f"[{weather_acquired[3]}]"
                        inst_wea = True
                else:
                    raise Exception(weather_acquired[1])
            elif re.search((r'event.*acquire'), predict_action_function, re.I):
                if 'year' in real_parameters_dict:
                    if isinstance(real_parameters_dict['year'], str):
                        if not real_parameters_dict['year'].isdigit():
                            real_parameters_dict['year'] = datetime.date.today().year
                        else:
                            real_parameters_dict['year'] = int(real_parameters_dict['year'])
                    elif not isinstance(real_parameters_dict['year'], int):
                        real_parameters_dict['year'] = datetime.date.today().year
                else:
                    real_parameters_dict['year'] = datetime.date.today().year
                if 'month' in real_parameters_dict:
                    if isinstance(real_parameters_dict['month'], str):
                        if not real_parameters_dict['month'].isdigit():
                            real_parameters_dict['month'] = datetime.date.today().month
                        elif int(real_parameters_dict['month']) > 12 or int(real_parameters_dict['month']) < 1:
                            real_parameters_dict['month'] = datetime.date.today().month
                        else:
                            real_parameters_dict['month'] = int(real_parameters_dict['month'])
                    elif not isinstance(real_parameters_dict['month'], int):
                        real_parameters_dict['month'] = datetime.date.today().month
                else:
                    real_parameters_dict['month'] = datetime.date.today().month
                if 'day' in real_parameters_dict:
                    if isinstance(real_parameters_dict['day'], str):
                        if not real_parameters_dict['day'].isdigit():
                            real_parameters_dict['day'] = datetime.date.today().day
                        elif int(real_parameters_dict['day']) > 31 or int(real_parameters_dict['day']) < 1:
                            real_parameters_dict['day'] = datetime.date.today().day
                        else:
                            real_parameters_dict['day'] = int(real_parameters_dict['day'])
                    elif not isinstance(real_parameters_dict['day'], int):
                        real_parameters_dict['day'] = datetime.date.today().day
                else:
                    real_parameters_dict['day'] = datetime.date.today().day
                event_acquired = await agent_modules.event_acquire(real_parameters_dict, sf_extraction, session, chat_session, -1, True, target_lang)
                if event_acquired[0]:
                    return_instruction = f"[{{'event': '{event_acquired[2]}'}}]"
                    if event_acquired[3]:
                        instructed_final_answer['event'] = f"[{event_acquired[3]}]"
                        inst_event = True
                else:
                    raise Exception(event_acquired[1])
            elif re.search((r'persistent.*acquire'), predict_action_function, re.I):
                persistent_acquired = await agent_modules.persistent_acquire(real_parameters_dict, sf_extraction, session, chat_session, target_lang)
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
                internet_acquired = await agent_modules.internet_acquire(real_parameters_dict, sf_extraction, session, chat_session, input, esc_aggressive, target_lang)
                if internet_acquired[0]:
                    return_instruction = f"[{{'search_result': '{internet_acquired[2]}'}}]"
                    if internet_acquired[3]:
                        instructed_final_answer['internet'] = f'"{internet_acquired[3]}"'
                        inst_search= True
                else:
                    raise Exception(internet_acquired[1])
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
            messages.append({'role': 'assistant', 'content': response})
            messages.append({'role': 'tool', 'content': return_instruction})
            resp = await client.chat.completions.create(**completion_args)
            if resp.choices[0].message.tool_calls:
                if resp.choices[0].message.tool_calls[0].function:
                    if resp.choices[0].message.tool_calls[0].function == tool_calls.function:
                        print('Total repetition detected, aborting')
                        break
            response = resp.choices[0].message.content
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
                await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_injecting', response_str1, 'debug'))
                await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_toolcall', response_str2, 'debug'))
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
        fin_final_answer = final_answer + conc_final_answer
    else:
        try:
            conc_final_answer = re.search((r'\s*Final\s*Answer\s*:\s*(.*)\s*$'), response, re.I|re.S)
            fin_final_answer = final_answer + conc_final_answer
        except:
            fin_final_answer = ''
    if mf_aggressive and instructed_final_answer_joined:
        response_str3 = f"MFocus callback achieved, response is:\n{final_answer}\nInfo acquired are:\n{instructed_final_answer_joined}\nEnd of MFocus callback."
        if websocket: await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_done', response_str3, 'debug'))
        print(response_str3)
        return fin_final_answer, instructed_final_answer_joined
    elif instructed_final_answer_joined:
        response_str3 = f"MFocus falling back, Info acquired are:\n{instructed_final_answer_joined}\nEnd of MFocus callback."
        if websocket: await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_done', response_str3, 'debug'))
        print(response_str3)
        return 'EMPTY', instructed_final_answer_joined
    else:
        response_str3 = f"MFocus failed or missed, Ending MFocus callback."
        if websocket: await websocket.send(maica_ws.wrap_ws_formatter('200', 'mfocus_done', response_str3, 'debug'))
        print(response_str3)
        return 'FAIL', ''

if __name__ == "__main__":
    agented = asyncio.run(agenting(None, '今天是什么日子', 1))
    print(agented[0])
    print(agented[1])


"""
{'role': 'system', 'content': system_init}
"""