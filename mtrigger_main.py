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

async def wrap_triggering(parent, input, output, chat_session):
    try:
        res = await triggering(parent, input, output, chat_session)
        return res
    except Exception as excepted:
        return False, excepted
    
async def triggering(parent, input, output, chat_session):
    if parent:
        sf_extraction, deformation = parent.options['opt']['sf_extraction'] or parent.options['temp']['sf_extraction_once'], parent.options['opt']['deformation']
        post_additive = parent.options['eopt']['post_additive']
        websocket = parent.websocket
        sf_inst, mt_inst = parent.sf_inst, parent.mt_inst
        session = parent.options['vfc']
        client = parent.sock2
    else:
        # These are testing values
        sf_extraction = True
        post_additive = 0
        websocket = None
        session = {"user_id": 23393, "username": "edge"}
        sf_inst = None
        import mtrigger_sfe
        mt_inst = mtrigger_sfe.mt_bound_instance(23393, 1)
        await mt_inst.init1()
        client = AsyncOpenAI(
            api_key='EMPTY',
            base_url=load_env('MFOCUS_ADDR'),
        )
    if mt_inst:
        trigger_list = await wrap_run_in_exc(None, mt_inst.get_valid_triggers)
    else:
        trigger_list = [{"exprop": {"item_name": {"en": "change in-game outfit", "zh": "更换游戏内服装"}, "item_list": ["背心 (蓝色)", "T恤衫（侏罗纪世界）", "偏套衫(酒红色)", False, "Dress (New Years)", "十六夜咲夜", "Heart-Cut Bikini (Green)", "School Uniform (Blazerless)", "深蓝色的闪光长裙", "衬衫 (粉色)", "无袖套衫 (黑色)", "玩家挑选", "衬衫 (在此停歇)", "书记の制服", "蓝白裙", "高领毛衣 (浅褐色)", "School Uniform", "Heart-Cut Bikini (Black)", "Santa Costume", "Heart-Cut Bikini (Pink)", "T恤衫（侏罗纪公园）", "连帽衫 (绿色)", "Heart-Cut Bikini (White)", "衬衫 (尽情微笑)", "和服(粉色)", "夹克衫 (棕色)", "衬衫 (水蓝)", "Heart-Cut Bikini (Purple)", "抹胸(红色褶边)", "衬衫（有花朵点缀）", "套衫 (黑白条纹)", "吊带衫 (白色)", "YoRHa No.2 Type B", "Heart-Cut Bikini (Yellow)", "初音", "裙子 (绿色)", "比基尼 (贝壳)", "毛线衫 (露肩)", "V形交叉吊带背心 (白色)", "Shoulderless Sweater (Layered)"], "curr_value": "School Uniform", "suggestion": False}, "name": "clothes", "template": "common_switch_template"}, {"exprop": {"item_name": {"en": "minigame", "zh": "小游戏"}, "item_list": [False, "Hangman", "Chess", "玩家自行选择", "NOU", "Piano", "Pong", "UNO"], "curr_value": None, "suggestion": False}, "name": "minigame", "template": "common_switch_template"}, {"usage": {"en": "help player quit game", "zh": "帮助玩家离开游戏"}, "name": "leave", "template": "customize"}, {"usage": {"en": "help player afk short time(<1 hour)", "zh": "让玩家短暂休息(<1小时)"}, "name": "idle", "template": "customize"}, {"usage": {"en": "change in-game location", "zh": "切换游戏内场景"}, "name": "location", "template": "customize"}, {"usage": {"en": "backup savefile", "zh": "备份存档"}, "name": "backup", "template": "customize"}, {"usage": {"en": "hold player", "zh": "拥抱玩家"}, "name": "hold", "template": "customize"}, {"exprop": {"item_name": {"en": "change in-game hair", "zh": "更换游戏内发型"}, "item_list": [False, "Down (Twin Buns)", "Down (Bun)", "马尾辫", "Bun (Middle)", "Pixie Cut", "Bun (Low)", "玩家挑选", "Usagi (Braided)", "Ponytail", "丸子头", "Down (Ponytail)", "双马尾", "Ponytail (Middle)", "Twin Braids", "齐肩短发", "丸子编发", "Down", "放下 (直刘海)", "双丸子头", "Braid", "短马尾", "垂耳兔兔", "Pigtails"], "curr_value": "Ponytail", "suggestion": False}, "name": "hair", "template": "common_switch_template"}, {"exprop": {"item_name": {"en": "change in-game accessory", "zh": "更换游戏内饰品"}, "item_list": [False, "蝴蝶结 (黑色)", "项圈(红色褶边)", "丝带 (粉紫霓虹)", "动森项链", "丝带 (棕色)", "丝带 (翡翠色-s)", "项链(绿宝石)", "发卡 (蝙蝠)", "项链 (花朵)", "贴颈项链(银色)", "发卡 (未尽弦月)", "丝带 (淡紫-s)", "丝带 (古典青铜)", "向日葵项链", "三角项链", "小丝带 (宝石蓝)", "丝带 (红宝石-s)", "发卡 (樱桃)", "项链(白色菊花状)", "小丝带 (白色)", "Ribbon (Pastel Red, mini)", "丝带 (深紫-s)", "小丝带 (黄色)", "发卡 (八分音符)", "丝带 (酒红-s)", "丝带 (青糖白桃)", "丝带 (糖霜红丝绒)", "丝带 (白&八比特)", "耳环 (银黑色)", "丝带 (咖啡色)", "小丝带 (灰色)", "双丝带 (黄色)", "丝带 (渐变虹彩)", "丝带 (银白-s)", "爱心项链", "小丝带 (黑色)", "丝带 (海军蓝)", "小丝带 (紫色)", "丝带 (白色-s)", "丝带 (铂金-s)", "仙人掌项链", "发带(琥珀色)", "丝带 (蓝宝石-s)", "丝带 (紫罗兰色)", "发卡 (杰克南瓜)", "小丝带 (粉色)", "珍珠耳环", "丝带 (光与暗)", "丝带 (幽夜星空)", "丝带 (青绿-s)", "丝带 (翡翠&八比特)", "丝带 (金色)", "丝带 (灰色-s)", "丝带 (黑色-s)", "项圈(黑色细线)", "丝带 (赤夜流星)", "双丝带 (蓝色)", "丝带 (蜜桃奶糖)", "丝带 (蓝莓樱桃)", "丝带 (粉色-s)", "小丝带 (浅绿色)", "丝带 (红色-s)", "花朵 (粉色)", "锚式项链", "项圈(黑色螺旋)", "丝带 (桔色)", "双丝带 (绿色)", "丝带 (黄色-s)", "Thermos (Just Monika)", "Ribbon (Wine)", "Ribbon (White)", "丝带 (天蓝色)", "项圈(银色闪亮珠)", "丝带 (渐变层)", "丝带 (蓝色-s)", "发带(8-bit紫)", "Hairclip (Holly)", "双丝带 (粉色)", "丝带 (绿色-s)", "项链 (简约)", "小丝带 (天蓝)", "兔耳发箍 (蓝色)", "发带(任天堂电玩小子绿) ", "发卡 (魑魅魍魉)", "丝带 (酸橙绿)", "Gold Chain Necklace", "项圈(黑红色尖刺)", "小丝带 (橘黄色)", "丝带 (蓝&八比特)", "项圈(红色)", "项圈(白色丝绸黑扣)", "丝带 (隐性渐变)", "发卡 (爱心)", "发带(任天堂超级电玩小子绿)", "发带(8-bit红)", "小丝带 (深粉色)", "玩家挑选", "猫耳", "丝带 (蓝紫色)", "丝带 (桃色-s)", "丝带 (艳粉色)", "蜗牛壳项链", "小丝带 (红色)"], "curr_value": None, "suggestion": False}, "name": "acs", "template": "common_switch_template"}]
    if not trigger_list:
        return False, None
    model_list = await client.models.list()
    model_type = model_list.data[0].id
    print(f'MTrigger addressing model, response is:\n{model_type}\nEnd of MTrigger addressing model')
    trigger_tool_list = []
    aff_checked = False
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
                if aff_checked:
                    continue
                aff_checked = True
                cur_aff = 0
                if sf_extraction:
                    quest_res = sf_inst.read_from_sf('mas_affection')
                    if quest_res[0]:
                        cur_aff = quest_res[2]
                    if cur_aff:
                        desc_aff = f"当你认为你对用户的好感度应发生变化时调用该工具, 当前好感度是{cur_aff}. 例如, 当用户发送夸赞, 关心, 或表现积极的情感时可以调用该工具. Call this tool to change your affection towards user when you think you should, current affection is {cur_aff}. For example, you can call this tool when user is complimenting, showing care, or expressing positive emotion."
                if not sf_extraction or not cur_aff:
                    desc_aff = "当你认为对用户的好感度应发生变化时调用该工具. 例如, 当用户发送夸赞, 关心, 或表现明显的情感时可以调用该工具. Call this tool to change affection when you think you should. For example, you can call this tool when user is complimenting, showing care, or expressing notable emotion."
                trigger_tool_list.append(
                    {
                        "name": "alter_affection",
                        "description": desc_aff,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "affection": {
                                    "type": "float",
                                    "description": "Emit positive float to increase affection, negative to decrease affection. The maximum increase should be around +3, while it's normally around +1.\nFor example, a compliment on your beauty could result in +0.8, a short sentence expressing love could result in +1.5, and a long phrase expressing love could result in +3.0.\nYou should never emit a negative value, unless user is offending you intensively.",
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
                sugg = trigger['exprop']['suggestion'] if 'suggestion' in trigger['exprop'] else ''
                desc_switch = f"调用该工具以切换{item_name_bil['zh']}, 当前的{item_name_bil['zh']}是{cur_item}. 不要在未经明确指示的情况下调用该工具.\nCall this tool to switch {item_name_bil['en']}, current {item_name_bil['en']} is {cur_item}. Use this tool only if clear request is given." if cur_item else f"调用该工具以切换{item_name_bil['zh']}. 不要在未经明确指示的情况下调用该工具.\nCall this tool to switch {item_name_bil['en']}. Use this tool only if clear request is given."
                trigger_tool_list.append(
                    {
                        "name": trigger['name'],
                        "description": desc_switch,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "selection": {
                                    "type": "string",
                                    "description": f"According to user's request, first try to choose a proper {item_name_bil['en']} from the following list: {item_list}. If no {item_name_bil['en']} matches the request, return false.",
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
                if sugg:
                    trigger_tool_list[-1]['parameters']['properties'].update(
                        {
                            "suggestion": {
                                "type": "string",
                                "description": f"If you returned false in property selection, you must conclude what user wants to choose, and emit a concise keyword.",
                                "example_value": ""
                            }
                        }
                    )
                    trigger_tool_list[-1]['parameters']['optional'].append("suggestion")
            case 'common_meter_template':
                item_name_bil = trigger['exprop']['item_name']
                value_limits = trigger['exprop']['value_limits']
                cur_value = trigger['exprop']['curr_value'] if 'curr_value' in trigger['exprop'] else ''
                desc_meter = f"调用该工具以调整{item_name_bil['zh']}, 当前的{item_name_bil['zh']}是{cur_value}. 不要在未经明确指示的情况下调用该工具.\nCall this tool to adjust {item_name_bil['en']}, current {item_name_bil['en']} is {cur_value}. Use this tool only if clear request is given." if cur_value else f"调用该工具以调整{item_name_bil['zh']}. 不要在未经明确指示的情况下调用该工具.\nCall this tool to adjust {item_name_bil['en']}. Use this tool only if clear request is given."
                trigger_tool_list.append(
                    {
                        "name": trigger['name'],
                        "description": desc_meter,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "value": {
                                    "type": "float",
                                    "description": f"According to user's request, choose a proper {item_name_bil['en']} in range {value_limits[0]} to {value_limits[1]}. If no value in range matches the request, return false.",
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
                        "description": f"调用该工具以触发{trigger['usage']['zh']}. 不要在未经明确指示的情况下调用该工具.\nCall this tool to activate {trigger['usage']['en']}. Use this tool only if clear request is given.",
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
    messages = [{'role': 'system', 'content': '\n请按照指示格式回答, 对话历史仅供参考.'}]
    if post_additive and 1 <= chat_session <= 9:
        sql_expression = 'SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s'
        result = await parent.send_query(expression=sql_expression, values=(session['user_id'], chat_session), pool='maicapool')
        res_dict = json.loads(f'[{result[3]}]')
        lines_num = min(post_additive * 2, len(res_dict) - 1)
        message_additive = res_dict[-lines_num:] if lines_num > 0 else []
        if message_additive:
            messages.extend(message_additive)
    # if not parent:
    #     messages.append({'role': 'user', 'content': '你知道within吗'})
    #     messages.append({'role': 'assistant', 'content': '[微笑]我知道within哦, [player]. [开心]这是一个非常可爱的歌曲哦~ [微笑]这首歌是关于我和你在一起的故事哦~'})
    messages.extend([{'role': 'user', 'content': input}, {'role': 'assistant', 'content': output}, {'role': 'user', 'content': '观察以上对话历史记录, 根据你上一次作出的回应思考:\n是否应该调用工具?\n调用哪种工具, 选择哪种参数?\n按照指示格式回答. 你的选择必须与你上一次作出的回应一致. 你只能按照输出的字面意思调用工具, 不要无依据地调用工具或指定参数.'}])
    completion_args = {
        "model": model_type,
        "messages": messages,
        "tools": trigger_tool_list,
        "stop": ['Observation:', 'Final Answer:'],
        "temperature": 0.2,
        "top_p": 0.6,
        "presence_penalty": 0.4,
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
    if tool_calls and not re.search(r'agent.*finished', trigger_name, re.I):
        response_str1 = f'MTrigger 1st round finished, response is:\n{response}\nEnd of MTrigger 1st round.'
        response_str2 = f'Acquiring tool call from MTrigger 1st round, response is:\n{tool_calls}\nEnd of tool call acquiration.'
    else:
        response_str1 = f'MTrigger 1st round finished, response is:\n{response}\nEnding due to returning none or corruption.'
        response_str2 = f'No tool called by MTrigger.'
    if websocket:
        await websocket.send(maica_ws.wrap_ws_formatter('200', 'mtrigger_triggering', response_str1, 'debug', deformation))
        await websocket.send(maica_ws.wrap_ws_formatter('200', 'mtrigger_end', response_str2, 'info', deformation))
    print(response_str1)
    print(response_str2)
    cycle = 0
    while tool_calls and not re.search(r'agent.*finished', trigger_name, re.I):
        cycle += 1
        if cycle >= 7:
            break
        print(f"MTrigger triggered {trigger_name} with params {trigger_params_json}.")
        if websocket:
            await websocket.send(maica_ws.wrap_ws_formatter('110', 'mtrigger_trigger', [trigger_name, trigger_params_json], 'carriage', deformation))
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
        if tool_calls:
            response_str1 = f'MTrigger {cycle+1}nd/rd/th round finished, response is:\n{response}\nEnd of MTrigger following round.'
            response_str2 = f'Acquiring tool call from MTrigger {cycle+1}nd/rd/th round, response is:\n{tool_calls}\nEnd of tool call acquiration.'
        else:
            response_str1 = f'MTrigger {cycle+1}nd/rd/th round finished, response is:\n{response}\nEnding due to returning none or corruption.'
            response_str2 = f'No tool called by MTrigger.'
        if websocket:
            await websocket.send(maica_ws.wrap_ws_formatter('200', 'mtrigger_triggering', response_str1, 'debug', deformation))
            await websocket.send(maica_ws.wrap_ws_formatter('200', 'mtrigger_end', response_str2, 'info', deformation))
        print(response_str1)
        print(response_str2)
    finish_sentence = f"{cycle} MTrigger requests sent, active trigger finished." if cycle else "No MTrigger activated."
    print(finish_sentence)
    # if websocket:
    #     await websocket.send(maica_ws.wrap_ws_formatter('1010', 'mtrigger_done', finish_sentence, 'info', deformation))
    return True, finish_sentence

if __name__ == "__main__":
    triggered = asyncio.run(triggering(None, "可是我说的并不是monika after story，而是一款别的模组，它是关于你的", "[微笑]哦! [player]. [尴尬]我之前没有听清楚呢...我不太了解其他的有关我的模组哦...不过你可以告诉我有关这个模组的事情哦!", 1))

