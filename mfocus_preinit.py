import re
import json
import datetime
import traceback
import agent_modules # type: ignore
from openai import OpenAI # type: ignore
def agenting(input, sf_extraction, session, chat_session):
    client = OpenAI(
        api_key='EMPTY',
        base_url='http://192.168.9.84:8021/v1',
    )
    model_type = client.models.list().data[0].id
    print(model_type)
    system_init = """
You are an assistant designed to sort and conclude from sentences. Proceed the following sentence accroding to rules provided below.
You have access to following tools:
1. time_acquire: Call this tool if you think the current time is needed to answer the sentence. Parameters: []

2. date_acquire: Call this tool if you think the current date is needed to answer the sentence. Parameters: []

3. weather_acquire: Call this tool if you think the current weather information or weather forcast is needed to answer the sentence. Parameters: []

4. event_acquire: Call this tool if you think the event or holiday of a given date is needed to answer the sentence. Parameters: [{"name": "date", "description": "The given date of which you need to know its event, leave empty for today", "required": "False"}]

5. persistent_acquire: Call this tool if you think any additional information about the speakers is needed to answer the sentence, such as their hobbies, experiences, appearence or relationship. Parameters: []

6. search_internet: Call this tool to interact with the internet search API. This API will search the phase provided in the parameters on the internet. Parameters: [{"name": "question", "description": "The question needs to be searched on Google", "required": "True"}]

Answer using the following format:

Thought: you should always think about what to do
Action: the action to take, should be one of the above tools[time_acquire, date_acquire, weather_acquire, event_acquire, persistent_acquire, search_internet]
Action Input: the parameters to pass in
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
Thought: I have used every necessary tool
Begin!
"""
    init_example_1 = """
Thought: 要回答干点什么好, 对话者必须知道当前的时间
Action: time_acquire
Action Input: []
Observation: [{'time': '13:49'}]
Thought: 要回答干点什么好, 对话者必须知道对方的爱好
Action: persistent_acquire
Action Input: []
Observation: [{'personal_info': ['[player]喜欢运动']}]
Thought: I have used every necessary tool
"""
    init_example_2 = """
Thought: 要回答今天是什么日子, 对话者必须知道今天的节日
Action: event_acquire
Action Input: []
Observation: [{'event': '情人节'}]
Thought: I have used every necessary tool
"""
    messages = [{'role': 'system', 'content': system_init}]
    messages_appending = [
        {'role': 'user', 'content': '我们现在干点什么好呢?'},
        {'role': 'assistant', 'content': init_example_1},
        {'role': 'user', 'content': '你知道今天是什么日子吗?'},
        {'role': 'assistant', 'content': init_example_2}
    ]
    messages.append(messages_appending)
    messages.append({'role': 'user', 'content': input})
    resp = client.chat.completions.create(
        model=model_type,
        messages=messages,
        stop=['Observation:'],
        seed=42)
    response = resp.choices[0].message.content
    print(f"first response is {response}")
    instructed_final_answer = ''
    cycle = 0
    inst_time = inst_date = inst_event = inst_exp = inst_aff = inst_pinfo = inst_search = False
    while not re.search((r'\s*Final\s*Answer\s*:\s*(.*)\s*$'), response, re.I|re.M):
        cycle += 1
        if cycle >= 7:
            break
        exception_return = ''
        if not re.match((r'^\s*none'), response, re.I):
            match_action = re.search((r'\s*Action\s*:\s*(.*)\s*$'), response, re.I|re.M)
            if match_action:
                predict_action_funcion = match_action[1]
                print(predict_action_funcion)
            match_action_input = re.search((r'\s*Action\s*Input\s*:\s*(\{.*\})\s*$'), response, re.I|re.M)
            if match_action_input:
                predict_parameters_json = match_action_input[1].replace('\'', '"')
                print('serialization completed')
            else:
                predict_parameters_json = '{}'
            try:
                real_parameters_json = json.loads(predict_parameters_json)
                return_instruction = ''
                if re.search((r'time.*acquire'), predict_action_funcion, re.I):
                    time_acquired = agent_modules.time_acquire(real_parameters_json)
                    if time_acquired[0]:
                        return_instruction = f"['time': '{time_acquired[2].hour}:{time_acquired[2].minute}']"
                        if not inst_time and time_acquired[3]:
                            instructed_final_answer += f"[{time_acquired[3]}]"
                            inst_time = True
                    else:
                        raise Exception(time_acquired[1])
                elif re.search((r'date.*acquire'), predict_action_funcion, re.I):
                    date_acquired = agent_modules.date_acquire(real_parameters_json, sf_extraction, session, chat_session)
                    if date_acquired[0]:
                        return_instruction = f"['date': '{date_acquired[2].year}年{date_acquired[2].month}月{date_acquired[2].day}日']"
                        if not inst_date:
                            instructed_final_answer += f"[{date_acquired[3]}]"
                            inst_date = True
                    else:
                        raise Exception(date_acquired[1])
                elif re.search((r'event.*acquire'), predict_action_funcion, re.I):
                    if 'year' in real_parameters_json:
                        if isinstance(real_parameters_json['year'], str):
                            if not real_parameters_json['year'].isdigit():
                                real_parameters_json['year'] = datetime.date.today().year
                            else:
                                real_parameters_json['year'] = int(real_parameters_json['year'])
                        elif not isinstance(real_parameters_json['year'], int):
                            real_parameters_json['year'] = datetime.date.today().year
                    else:
                        real_parameters_json['year'] = datetime.date.today().year
                    if 'month' in real_parameters_json:
                        if isinstance(real_parameters_json['month'], str):
                            if not real_parameters_json['month'].isdigit():
                                real_parameters_json['month'] = datetime.date.today().month
                            elif int(real_parameters_json['month']) > 12 or int(real_parameters_json['month']) < 1:
                                real_parameters_json['month'] = datetime.date.today().month
                            else:
                                real_parameters_json['month'] = int(real_parameters_json['month'])
                        elif not isinstance(real_parameters_json['month'], int):
                            real_parameters_json['month'] = datetime.date.today().month
                    else:
                        real_parameters_json['month'] = datetime.date.today().month
                    if 'day' in real_parameters_json:
                        if isinstance(real_parameters_json['day'], str):
                            if not real_parameters_json['day'].isdigit():
                                real_parameters_json['day'] = datetime.date.today().day
                            elif int(real_parameters_json['day']) > 31 or int(real_parameters_json['day']) < 1:
                                real_parameters_json['day'] = datetime.date.today().day
                            else:
                                real_parameters_json['day'] = int(real_parameters_json['day'])
                        elif not isinstance(real_parameters_json['day'], int):
                            real_parameters_json['day'] = datetime.date.today().day
                    else:
                        real_parameters_json['day'] = datetime.date.today().day
                    event_acquired = agent_modules.event_acquire(real_parameters_json, sf_extraction, session, chat_session)
                    if event_acquired[0]:
                        return_instruction = f"['event': '{event_acquired[2]}']"
                        if not inst_event and event_acquired[3]:
                            instructed_final_answer += f"[{event_acquired[3]}]"
                            inst_event = True
                    else:
                        raise Exception(event_acquired[1])
                elif re.search((r'experience.*acquire'), predict_action_funcion, re.I):
                    experience_acquired = agent_modules.experience_acquire(real_parameters_json, sf_extraction, session, chat_session)
                    if experience_acquired[0]:
                        return_instruction = f"['experience_had': '{experience_acquired[2]}']"
                        if not inst_exp and experience_acquired[3]:
                            instructed_final_answer += f"[{experience_acquired[3]}]"
                            inst_exp = True
                    else:
                        raise Exception(experience_acquired[1])
                elif re.search((r'affection.*acquire'), predict_action_funcion, re.I):
                    affection_acquired = agent_modules.affection_acquire(real_parameters_json, sf_extraction, session, chat_session)
                    if affection_acquired[0]:
                        return_instruction = f"['characters_affection_state': '{affection_acquired[2]}']"
                        if not inst_aff and affection_acquired[3]:
                            instructed_final_answer += f"[{affection_acquired[3]}]"
                            inst_aff = True
                    else:
                        raise Exception(affection_acquired[1])
                elif re.search((r'personal.*information'), predict_action_funcion, re.I):
                    pinfo_acquired = agent_modules.pinfo_acquire(real_parameters_json, sf_extraction, session, chat_session)
                    if affection_acquired[0]:
                        return_instruction = f"['personal_info': '{pinfo_acquired[2]}']"
                        if not inst_pinfo and pinfo_acquired[3]:
                            instructed_final_answer += f"[{pinfo_acquired[3]}]"
                            inst_pinfo = True
                    else:
                        raise Exception(pinfo_acquired[1])
                elif re.search((r'search.*internet'), predict_action_funcion, re.I):
                    internet_acquired = agent_modules.internet_acquire(real_parameters_json, sf_extraction, session, chat_session)
                    if internet_acquired[0]:
                        return_instruction = f"['search_result': '{internet_acquired[2]}']"
                        if not inst_search and internet_acquired[3]:
                            instructed_final_answer += f"[{internet_acquired[3]}]"
                            inst_search= True
                    else:
                        raise Exception(internet_acquired[1])
                else:
                    raise Exception('None Function Actually Matched')
            except Exception as excepted:
                exception_return = excepted
                #traceback.print_exc()
                print(excepted)
            if not exception_return:
                print(len(messages))
                #print(len(messages_appending))
                if True:
                    messages[len(messages) - 1]['content'] += response + f"\n{return_instruction}"
                else:
                    messages.append({'role': 'assistant', 'content': response + f"\n{return_instruction}"})
                    print(messages)
                resp = client.chat.completions.create(
                    model=model_type,
                    messages=messages,
                    stop=['Observation:'],
                    seed=42)
                response = resp.choices[0].message.content
                print(f"following response is {response}")
            else:
                break
        else:
            return 'EMPTY', ''
    final_answer = re.search((r'\s*Final\s*Answer\s*:\s*(.*)\s*$'), response, re.I|re.M)
    if final_answer:
        print(f"agent final answer is {final_answer[1]}")
        return final_answer[1], instructed_final_answer
    else:
        print("None Returned Or Something Went Wrong")
        return 'FAIL', instructed_final_answer

if __name__ == "__main__":
    agented = agenting('我们今天干点什么好呢?', False, None, None)
    print(agented[0])
    print(agented[1])
