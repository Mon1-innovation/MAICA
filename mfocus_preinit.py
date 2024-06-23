import re
import json
import datetime
import traceback
import agent_modules # type: ignore
from openai import OpenAI # type: ignore
from loadenv import load_env
def agenting(input, sf_extraction, session, chat_session):
    client = OpenAI(
        api_key='EMPTY',
        base_url=load_env('MFOCUS_ADDR'),
    )
    model_type = client.models.list().data[0].id
    print(f'MFocus preinit addressing model, response is:\n{model_type}\nEnd of MFocus addressing model')
    system_init = """
You are an assistant designed to sort and conclude from sentences. Proceed the following sentence accroding to rules provided below.
You have access to following tools:
1. time_acquire: Call this tool if you think the current time is needed to answer the sentence. Parameters: []

2. date_acquire: Call this tool if you think the current date is needed to answer the sentence. Parameters: []

3. event_acquire: Call this tool if you think the event or holiday of a given date is needed to answer the sentence. Parameters: [{"name": "date", "description": "The given date of which you need to know its event, leave empty for today", "required": "False"}]

4. persistent_acquire: Call this tool if you think any additional information about the speakers is needed to answer the sentence, such as their preferences, hobbies, experiences, appearence or relationship. Parameters: [{"name": "question", "description": "The information needed to answer the sentence", "required": "True"}]

5. search_internet: Call this tool to interact with the internet search API. This API will search the phase provided in the parameters on the internet. Parameters: [{"name": "question", "description": "The question needs to be searched on Google. This question should not be too detailed", "required": "True"}]

If you are using search_internet tool, only include the location and the abstract information needed. Do not include too many details.

If there is anything additional you want to know about the speakers, call persistent_acquire tool.

Answer using the following format:

Thought: you should always think about what to do
Action: the action to take, should be one of the above tools[time_acquire, date_acquire, event_acquire, persistent_acquire, search_internet]
Action Input: the parameters to pass in
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
Thought: I now know the final answer
Final Answer: sort up every information you acquired, and output directly.
Begin!
"""
    weather_bkp = """
3. weather_acquire: Call this tool if you think the current weather information or weather forcast is needed to answer the sentence. Parameters: []
"""
    init_example_1 = """Thought: 要回答干点什么好, 对话者必须知道当前的时间
Action: time_acquire
Action Input: []
Observation: [{'time': '13:49'}]
Thought: 要回答干点什么好, 对话者必须知道对方的爱好
Action: persistent_acquire
Action Input: {'question': '你的爱好是什么'}
Observation: [{'personal_info': ['[player]喜欢运动']}]
Thought: 我需要搜索互联网以获取合适的运动场地
Action: search_internet
Action Input: {"question": "附近的运动场馆"}
Observation: [{'search_result': '信息1: 附近有一座体育馆'}]
Thought: I now know the final answer
Final Answer: [player]喜欢运动, 附近有一座体育馆, 且现在是下午13:49
"""
    init_example_2 = """Thought: 要回答今天是什么日子, 对话者必须知道今天的节日
Action: event_acquire
Action Input: {}
Observation: [{'event': '情人节'}]
Thought: I now know the final answer
Final Answer: 今天是情人节
"""
    tools =  [
        {
            "name": "time_acquire",
            "description": "Call this tool to get the current time.",
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
            "description": "Call this tool to get the current date.",
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
            "description": "Call this tool to get the current weather.",
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
            "name": "event_acquire",
            "description": "Call this tool to get the event or holiday of a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "int",
                        "description": "The year of the given date, leave empty for the year now.",
                        "example_value": "2023"
                    },
                    "month": {
                        "type": "int",
                        "description": "The month of the given date, leave empty for the month now.",
                        "example_value": "6"
                    },
                    "day": {
                        "type": "int",
                        "description": "The day of the given date, leave empty for the day today.",
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
            "description": "Call this tool to get any additional information about the speakers, such as their preferences, hobbies, experiences, appearence or relationship. 如果你被问及你作为AI不具有的记忆, 经历, 人格或感情, 请使用此工具查找.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question you want to ask the speakers.",
                        "example_value": "你喜欢吃什么?"
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
            "description": "Call this tool to interact with the internet search API. This API will search your question on the internet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question needs to be searched on Google, which should not be too detailed.",
                        "example_value": "今天天气怎么样"
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
    messages = []
    messages_appending = [
        {'role': 'user', 'content': '我们现在干点什么好呢?'},
        {'role': 'assistant', 'content': init_example_1},
        {'role': 'user', 'content': '你知道今天是什么日子吗?'},
        {'role': 'assistant', 'content': init_example_2}
    ]
    #messages.extend(messages_appending)
    messages.append({'role': 'user', 'content': input})
    resp = client.chat.completions.create(
        model=model_type,
        messages=messages,
        tools = tools,
        stop=['Observation:'],
        temperature=0.6,
        top_p = 0.6,
        presence_penalty = 0.0,
        frequency_penalty = 0.0,
        seed=42)
    response = resp.choices[0].message.content
    tool_calls = resp.choices[0].message.tool_calls
    print(f"MFocus preinit 1st round finished, response is:\n{response}\nEnd of MFocus preinit 1st round")
    print(f"Acquiring tool call from MFocus preinit 1st round, response is:\n{tool_calls}\nEnd of tool call acquiration")

    instructed_final_answer = {}
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
            predict_action_function = tool_calls['function']['name']
            real_parameters_dict = json.loads(re.sub(r"(?!=\\)'", '"', tool_calls['function']['arguments']))
            if re.search((r'time.*acquire'), predict_action_function, re.I):
                time_acquired = agent_modules.time_acquire(real_parameters_dict)
                if time_acquired[0]:
                    return_instruction = f"[{{'time': '{time_acquired[2].hour}:{time_acquired[2].minute}'}}]"
                    if time_acquired[3]:
                        instructed_final_answer['time'] = f"[{time_acquired[3]}]"
                        inst_time = True
                else:
                    raise Exception(time_acquired[1])
            elif re.search((r'date.*acquire'), predict_action_function, re.I):
                date_acquired = agent_modules.date_acquire(real_parameters_dict, sf_extraction, session, chat_session)
                if date_acquired[0]:
                    return_instruction = f"[{{'date': '{date_acquired[2].year}年{date_acquired[2].month}月{date_acquired[2].day}日'}}]"
                    instructed_final_answer['date'] = f"{date_acquired[3]}"
                    inst_date = True
                else:
                    raise Exception(date_acquired[1])
            elif re.search((r'weather.*acquire'), predict_action_function, re.I):
                weather_acquired = agent_modules.weather_acquire(real_parameters_dict, sf_extraction, session, chat_session)
                if weather_acquired[0]:
                    return_instruction = f"[{{'weather': {weather_acquired[2]}}}]"
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
                event_acquired = agent_modules.event_acquire(real_parameters_dict, sf_extraction, session, chat_session)
                if event_acquired[0]:
                    return_instruction = f"[{{'event': '{event_acquired[2]}'}}]"
                    if event_acquired[3]:
                        instructed_final_answer['event'] = f"[{event_acquired[3]}]"
                        inst_event = True
                else:
                    raise Exception(event_acquired[1])
            elif re.search((r'persistent.*acquire'), predict_action_function, re.I):
                persistent_acquired = agent_modules.persistent_acquire(real_parameters_dict, sf_extraction, session, chat_session)
                if persistent_acquired[0]:
                    return_instruction = f"[{{'known_info': {persistent_acquired[2]}}}]"
                    if persistent_acquired[3]:
                        if 'persistent' in instructed_final_answer:
                            instructed_final_answer['persistent'] += f"{persistent_acquired[3]}"
                        else:
                            instructed_final_answer['persistent'] = f"{persistent_acquired[3]}"
                        inst_pst = True
                else:
                    raise Exception(persistent_acquired[1])
            elif re.search((r'search.*internet'), predict_action_function, re.I):
                internet_acquired = agent_modules.internet_acquire(real_parameters_dict, sf_extraction, session, chat_session)
                if internet_acquired[0]:
                    return_instruction = f"[{{'search_result': '{internet_acquired[2]}'}}]"
                    if internet_acquired[3]:
                        instructed_final_answer['internet'] = f"[{internet_acquired[3]}]"
                        inst_search= True
                else:
                    raise Exception(internet_acquired[1])
            else:
                raise Exception('None Function Actually Matched')
        except Exception as excepted:
            exception_return = excepted
            #traceback.print_exc()
            print(f'Exception occured during MFocus preinit: {exception_return}')
        if not exception_return:
            messages.append({'role': 'assistant', 'content': response})
            messages.append({'role': 'tool', 'content': return_instruction})
            resp = client.chat.completions.create(
                model=model_type,
                messages=messages,
                tools = tools,
                stop=['Observation:'],
                temperature=0.6,
                top_p = 0.6,
                presence_penalty = 0.0,
                frequency_penalty = 0.0,
                seed=42)
            response = resp.choices[0].message.content
            print(f"MFocus preinit {cycle+1}nd/rd/th round finished, response is:\n{response}\nEnd of MFocus preinit 1st round")
            tool_calls = resp.choices[0].message.tool_calls
            print(f"Acquiring tool call from MFocus preinit {cycle+1}nd/rd/th round, response is:\n{tool_calls}\nEnd of tool call acquiration")
        else:
            break
    #print(instructed_final_answer)
    instructed_final_answer_joined = ''.join(str(x) for x in instructed_final_answer.values())
    final_answer = re.search((r'\s*Final\s*Answer\s*:\s*(.*)\s*$'), response, re.I|re.S)
    if final_answer:
        print(f"MFocus callback achieved, response is:\n{final_answer[1]}\nEnd of MFocus callback")
        return final_answer[1], instructed_final_answer_joined
    else:
        print("No final answer found for MFocus callback, can be exception")
        return 'FAIL', instructed_final_answer_joined

if __name__ == "__main__":
    agented = agenting('你有什么想吃的东西吗', True, [0,0,23], 1)
    #print(agented[0])
    print(agented[1])


"""
{'role': 'system', 'content': system_init}
"""