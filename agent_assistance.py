import re
import json
import datetime
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
Gather the information needed to reply to the following sentence. You need to sort the information you gathered into a conclusion. Do not directly answer the sentence.
There should be nothing but the information in your reply.
If you dont think any information mentioned below is needed to answer the sentence, say None.
You have access to the following APIs:
1. time_acquire: Call this tool to interact with the time API. This API will return the current time. Parameters: []

2. date_acquire: Call this tool to interact with the date API. This API will return the current date. Parameters: []

3. event_acquire: Call this tool to interact with the event API. This API will return what special day it is. Parameters: [{"name": "month", "description": "The month of the date to search", "required": "False"}, {"name": "day", "description": "The day of the date to search", "required": "False"}]

4. experience_acquire: Call this tool to interact with the experience API. This API will return what the characters experienced together before. Parameters: [{"name": "experience", "description": "Experience of which event should be acquired, use 全部 to acquire them all", "required": "True"}]

5. affection_acquire: Call this tool to interact with the affection API. This API will return what relationship the characters are in. Parameters: []

Use the following format:

Thought: you should always think about what to do
Action: the action to take, should be one of the above tools[time_acquire, date_acquire, event_acquire, experience_acquire, affection_acquire]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question
Begin!
"""
    backup_init = """
6. appearence_acquire: Call this tool to interact with the appearence API. This API will return how the characters look. Parameters: [{"name": "who", "description": "Choose from user and assistant whose appearence needs to be acquired", "required": "True"}, {"name": "which", "description": "The detailed bodypart needs to be acquired", "required": "True"}]

"""
    messages = [{'role': 'system', 'content': system_init}, {'role': 'user', 'content': input}]
    resp = client.chat.completions.create(
        model=model_type,
        messages=messages,
        stop=['Observation:'],
        seed=42)
    response = resp.choices[0].message.content
    print(f"first response is {response}")
    instructed_final_answer = ''
    cycle = 0
    while not re.search((r'^\s*Final\s*Answer\s*:\s*(.*)\s*$'), response, re.I|re.M):
        cycle+1
        if cycle >= 7:
            break
        exception_return = ''
        if not re.match((r'^\s*none'), response, re.I):
            match_action = re.search((r'^\s*Action\s*:\s*(.*)\s*$'), response, re.I|re.M)
            if match_action:
                predict_action_funcion = match_action[1]
                print(predict_action_funcion)
            match_action_input = re.search((r'^\s*Action\s*Input\s*:\s*(.*)\s*$'), response, re.I|re.M)
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
                        instructed_final_answer += f"[{time_acquired[3]}]"
                    else:
                        raise Exception(time_acquired[1])
                elif re.search((r'date.*acquire'), predict_action_funcion, re.I):
                    date_acquired = agent_modules.date_acquire(real_parameters_json)
                    if date_acquired[0]:
                        return_instruction = f"['date': '{date_acquired[2]['year']}年{date_acquired[2]['month']}月{date_acquired[2]['day']}日']"
                        instructed_final_answer += f"[{date_acquired[3]}]"
                    else:
                        raise Exception(date_acquired[1])
                elif re.search((r'event.*acquire'), predict_action_funcion, re.I):
                    if not 'year' in real_parameters_json:
                        real_parameters_json['year'] = datetime.date.today().year
                    if not 'month' in real_parameters_json:
                        real_parameters_json['month'] = datetime.date.today().month
                    if not 'day' in real_parameters_json:
                        real_parameters_json['day'] = datetime.date.today().day
                    event_acquired = agent_modules.event_acquire(real_parameters_json, sf_extraction, session, chat_session)
                    if event_acquired[0]:
                        return_instruction = f"['event': '{event_acquired[2]}']"
                        instructed_final_answer += f"[{event_acquired[3]}]"
                    else:
                        raise Exception(event_acquired[1])
                elif re.search((r'experience.*acquire'), predict_action_funcion, re.I):
                    experience_acquired = agent_modules.experience_acquire(real_parameters_json, sf_extraction, session, chat_session)
                    if experience_acquired[0]:
                        return_instruction = f"['experience_had_together': '{experience_acquired[2]}']"
                        instructed_final_answer += f"[{experience_acquired[3]}]"
                    else:
                        raise Exception(experience_acquired[1])
                elif re.search((r'affection.*acquire'), predict_action_funcion, re.I):
                    affection_acquired = agent_modules.affection_acquire(real_parameters_json)
                    if affection_acquired[0]:
                        return_instruction = f"['characters_affection_state': '{affection_acquired[2]}']"
                    else:
                        raise Exception(affection_acquired[1])
                else:
                    raise Exception('None Function Actually Matched')
            except Exception as excepted:
                exception_return = excepted
                print(excepted)
            if not exception_return:
                if len(messages) > 2:
                    messages[2]['content'] = response + f"\n{return_instruction}"
                else:
                    messages.append({'role': 'assistant', 'content': response + f"\n{return_instruction}"})
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
            return 'EMPTY'
    final_answer = re.search((r'^\s*Final\s*Answer\s*:\s*(.*)\s*$'), response, re.I|re.M)
    if final_answer:
        print(f"agent final answer is {final_answer[1]}")
        return final_answer[1]
    else:
        print("None Returned Or Something Went Wrong")
        return None

if __name__ == "__main__":
    agented = agenting('你喜欢我吗?')
    print(agented)