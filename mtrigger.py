import re
import json
import random
import datetime
import traceback
import asyncio
import nest_asyncio
import maica_ws
import agent_modules
import persistent_extraction
from openai import AsyncOpenAI # type: ignore
from loadenv import load_env
async def wrap_triggering(parent, input, chat_session, trigger_list):
    try:
        res = await triggering(parent, input, chat_session, trigger_list)
        return None
    except Exception as excepted:
        response_str = f"Trigger response acquiring failed, refer to administrator--your ray tracer ID is {parent.traceray_id}"
        await parent.websocket.send(maica_ws.wrap_ws_formatter('503', 'mtrigger_failed', response_str, 'warn'))
        return excepted
async def triggering(parent, input, chat_session, trigger_list):
    if parent:
        sf_extraction = parent.options['opt']['sf_extraction']
        post_additive = parent.options['eopt']['post_additive']
        websocket = parent.websocket
        session = parent.options['vfc']
    else:
        sf_extraction = True
        post_additive = 0
        websocket = None
        session = {"user_id": 23, "username": "edge"}
    if not trigger_list:
        return False
    client = AsyncOpenAI(
        api_key='EMPTY',
        base_url=load_env('MFOCUS_ADDR'),
    )
    model_list = await client.models.list()
    model_type = model_list.data[0].id
    print(f'MTrigger addressing model, response is:\n{model_type}\nEnd of MTrigger addressing model')
    trigger_tool_list = []
    for trigger in trigger_list:

# {
#     "template": "common_affection_template"
# }

# {
#     "template": "common_switch_template",
#     "name": "change_clothes",
#     "exprop":{
#         "item_name": {
#             "zh": "衣服",
#             "en": "clothes"
#         },
#         "item_list": ["白色连衣裙", "黑色连衣裙"],
#         "curr_item": "白色连衣裙"
#     }
# }

# {
#     "template": "common_meter_template",
#     "name": "change_distance",
#     "exprop":{
#         "item_name": {
#             "zh": "距离",
#             "en": "distance"
#         },
#         "value_limits": [0, 2.5],
#         "curr_value": 0.67
#     }
# }

# {
#     "template": "customize",
#     "name": "some_name",
#     "usage":{
#         "zh": "功能",
#         "en": "Function"
#     }
# }

        match trigger['template']:
            case 'common_affection_template':
                cur_aff = 0
                if sf_extraction:
                    quest_res = persistent_extraction.read_from_sf(session['user_id'], chat_session, 'mas_affection')
                    if quest_res[0]:
                        cur_aff = quest_res[2]
                    desc_aff = f"当你认为对用户的好感度应发生变化时调用该工具, 当前好感度是{cur_aff}. 仅当用户表现强烈情感时调用该工具. Call this tool to change affection when you think you should, current affection is {cur_aff}. Use this tool only if user is expressing strong emotion." if cur_aff else "当你认为对用户的好感度应发生变化时调用该工具. 仅当用户表现强烈情感时调用该工具. Call this tool to change affection when you think you should. Use this tool only if user is expressing strong emotion."
                trigger_tool_list.append(
                    {
                        "name": "alter_affection",
                        "description": desc_aff,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "affection": {
                                    "type": "float",
                                    "description": "Emit positive float to increase affection, negative to decrease affection. The maximum increase should be around +2, while it's normally around +1.",
                                    "example_value": "+0.25"
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
            case 'common_switch_template':
                item_name_bil = trigger['exprop']['item_name']
                item_list = trigger['exprop']['item_list']
                cur_item = trigger['exprop']['curr_item'] if 'curr_item' in trigger['exprop'] else ''
                desc_switch = f"调用该工具以切换{item_name_bil['zh']}, 当前的{item_name_bil['zh']}是{cur_item}. Call this tool to switch {item_name_bil['en']}, current {item_name_bil['en']} is {cur_item}." if cur_item else f"调用该工具以切换{item_name_bil['zh']}. Call this tool to switch {item_name_bil['en']}."
                trigger_tool_list.append(
                    {
                        "name": trigger['name'],
                        "description": desc_switch,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "selection": {
                                    "type": "string",
                                    "description": f"According to user's request, choose a proper {item_name_bil['en']} from the following list: {item_list}",
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
            case 'common_meter_template':
                item_name_bil = trigger['exprop']['item_name']
                value_limits = trigger['exprop']['value_limits']
                cur_value = trigger['exprop']['curr_value'] if 'curr_value' in trigger['exprop'] else ''
                desc_meter = f"调用该工具以调整{item_name_bil['zh']}, 当前的{item_name_bil['zh']}是{cur_value}. Call this tool to adjust {item_name_bil['en']}, current {item_name_bil['en']} is {cur_value}." if cur_value else f"调用该工具以调整{item_name_bil['zh']}. Call this tool to adjust {item_name_bil['en']}."
                trigger_tool_list.append(
                    {
                        "name": trigger['name'],
                        "description": desc_meter,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "value": {
                                    "type": "float",
                                    "description": f"According to user's request, choose a proper {item_name_bil['en']} in range {value_limits[0]} to {value_limits[1]}.",
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
            case _:
                trigger_tool_list.append(
                    {
                        "name": trigger['name'],
                        "description": f"调用该工具以触发{trigger['usage']['zh']}. Call this tool to activate {trigger['usage']['en']}",
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
    trigger_tool_list.append(
        {
            "name": "agent_finished",
            "description": f"若你已调用了所有必要的工具, 则调用该工具以表示你已完成. Call this tool after you've finished calling every other necessary tool, so we know you're done.",
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
    messages = []
    if post_additive:
        sql_expression = 'SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s'
        result = await parent.send_query(expression=sql_expression, values=(session['user_id'], chat_session), pool='maicapool')
        res_dict = json.loads(f'[{result[3]}]')
        lines_num = min(post_additive * 2, len(res_dict) - 1)
        message_additive = res_dict[-lines_num:] if lines_num > 0 else []
        if message_additive:
            messages.append({'role': 'system', 'content': '在作答时, 假设你是用户的女友, 名为莫妮卡, 并在此前提下调用工具. 请按照指示格式回答, 对话历史仅供参考.'})
            messages.extend(message_additive)
        else:
            messages.append({'role': 'system', 'content': '在作答时, 假设你是用户的女友, 名为莫妮卡, 并在此前提下调用工具.'})
    messages.append({'role': 'user', 'content': input})
    completion_args = {
        "model": model_type,
        "messages": messages,
        "tools": trigger_tool_list,
        "stop": ['Observation:'],
        "temperature": 0.1,
        "top_p": 0.6,
        "presence_penalty": -0.5,
        "frequency_penalty": 0.5,
        "seed": 42
    }
    resp = await client.chat.completions.create(**completion_args)
    response = resp.choices[0].message.content
    #print(resp.choices[0].message.tool_calls)
    if resp.choices[0].message.tool_calls:
        tool_calls = resp.choices[0].message.tool_calls[0]
        trigger_name = tool_calls.function.name
        try:
            trigger_params_json = json.loads(re.search(r'(\{.*\})', re.sub(r"(?!=\\)'", '"', tool_calls.function.arguments))[1])
        except:
            trigger_params_json = {}
    else:
        tool_calls = None
    cycle = 0
    while tool_calls and not re.search(r'agent.*finished', trigger_name, re.I):
        cycle += 1
        if cycle >= 7:
            break
        print(f"MTrigger triggered {trigger_name} with params {trigger_params_json}.")
        if websocket:
            await websocket.send(maica_ws.wrap_ws_formatter('110', 'mtrigger_trigger', [trigger_name, trigger_params_json], 'carriage'))
        return_instruction = '{"status": "success"}'
        messages.append({'role': 'assistant', 'content': response})
        messages.append({'role': 'tool', 'content': return_instruction})
        resp = await client.chat.completions.create(**completion_args)
        response = resp.choices[0].message.content
        if resp.choices[0].message.tool_calls:
            tool_calls = resp.choices[0].message.tool_calls[0]
            trigger_name = tool_calls.function.name
            try:
                trigger_params_json = re.search(r'(\{.*\})', re.sub(r"(?!=\\)'", '"', tool_calls.function.arguments))[1]
            except:
                trigger_params_json = {}
        else:
            tool_calls = None
    finish_sentence = f"{cycle} MTrigger requests sent, active trigger finished." if cycle else "No MTrigger activated."
    print(finish_sentence)
    if websocket:
        await websocket.send(maica_ws.wrap_ws_formatter('1010', 'mtrigger_done', finish_sentence, 'info'))
    return True

if __name__ == "__main__":
    triggered = asyncio.run(triggering(None, "你好啊", 1, [{"template": "common_affection_template"}]))