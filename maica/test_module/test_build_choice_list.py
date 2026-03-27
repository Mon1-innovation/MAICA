from maica.mtrigger.trigger_class import *

def build(trigger_list, targer_lang='zh'):
    choice_list = []; choice_checklist = []
    if trigger_list:
        for trigger in trigger_list:
            match trigger.template:
                case 'common_affection_template':
                    pass
                case 'common_switch_template':
                    cst_temp_list = []
                    for i in trigger.exprop.item_list:
                        j = f'选择{i}' if targer_lang == 'zh' else f'switch to {i}'
                        choice_checklist.append(j)
                        cst_temp_list.append(j)

                    if trigger.exprop.suggestion:
                        j = f"选择未列出的{trigger.exprop.item_name.zh}" if targer_lang == 'zh' else f"Choose an unlisted {trigger.exprop.item_name.en}"
                        choice_checklist.append(j)
                        cst_temp_list.append(j)

                    cst_explaination = f"更换{trigger.exprop.item_name.zh}" if targer_lang == 'zh' else f"Change {trigger.exprop.item_name.en}"
                    choice_list.append({cst_explaination: cst_temp_list})

                case 'common_meter_template':
                    cmt_iname = f'调整{trigger.exprop.item_name.zh}' if targer_lang == 'zh' else f'Adjust {trigger.exprop.item_name.en}'
                    choice_checklist.append(cmt_iname)
                    j = f"{cmt_iname}, 范围是{trigger.exprop.value_limits[0]}到{trigger.exprop.value_limits[1]}" if targer_lang == 'zh' else f"{cmt_iname} within range {trigger.exprop.value_limits[0]} to {trigger.exprop.value_limits[1]}"
                    choice_list.append(j)

                case _:
                    cc_iname = trigger.exprop.item_name.zh if targer_lang == 'zh' else trigger.exprop.item_name.en
                    j = f"触发{cc_iname}" if targer_lang == 'zh' else f"Trigger {cc_iname}"
                    choice_checklist.append(j)
                    choice_list.append(j)

    choice_list = choice_list
    choice_checklist = choice_checklist
    return choice_list

def serialize_triggers(sf_forming_buffer):
    aff_trigger_list: list[CommonAffectionTrigger] = []
    switch_trigger_list: list[CommonSwitchTrigger] = []
    meter_trigger_list: list[CommonMeterTrigger] = []
    customized_trigger_list: list[CustomizedTrigger] = []

    for trigger_dict in sf_forming_buffer:
        match trigger_dict['template']:
            case 'common_affection_template':
                trigger_inst = CommonAffectionTrigger(**trigger_dict)
                aff_trigger_list.append(trigger_inst)
            case 'common_switch_template':
                trigger_inst = CommonSwitchTrigger(**trigger_dict)
                switch_trigger_list.append(trigger_inst)
            case 'common_meter_template':
                trigger_inst = CommonMeterTrigger(**trigger_dict)
                meter_trigger_list.append(trigger_inst)
            case _:
                trigger_inst = CustomizedTrigger(**trigger_dict)
                customized_trigger_list.append(trigger_inst)

    aff_trigger_list = limit_length(aff_trigger_list, 1)
    switch_trigger_list = limit_length(switch_trigger_list, 6)
    meter_trigger_list = limit_length(meter_trigger_list, 6)
    customized_trigger_list = limit_length(customized_trigger_list, 20)

    return aff_trigger_list + switch_trigger_list + meter_trigger_list + customized_trigger_list

def build_case_260326():
    trigger_list=\
[{'exprop': {'item_name': {'en': u'change in-game outfit', 'zh': u'更换游戏内服装'}, 'item_list': [False, u'school uniform (blazerless)', u'school uniform', u'玩家挑选'], 'curr_value': u'school uniform', 'suggestion': False}, 'name': u'clothes', 'template': 'common_switch_template'}, {'exprop': {'item_name': {'en': u'play minigame', 'zh': u'玩小游戏'}, 'item_list': [False, u'pong', u'玩家自行选择'], 'curr_value': None, 'suggestion': False}, 'name': u'minigame', 'template': 'common_switch_template'}, {'exprop': {'item_name': {'en': u'help player quit game', 'zh': u'帮助玩家离开游戏'}}, 'name': u'leave', 'template': 'customized'}, {'exprop': {'item_name': {'en': u'go outside with player', 'zh': u'和玩家一起出门'}}, 'name': u'go_outside', 'template': 'customized'}, {'exprop': {'item_name': {'en': u'call when the player indicates they want to take a temporary leave (<1 hour).', 'zh': u'当玩家表示想要短暂离开(<1小时)时调用'}}, 'name': u'idle', 'template': 'customized'}, {'exprop': {'item_name': {'en': u'change the in-game weather.r', 'zh': u'更改游戏内天气'}, 'item_list': [u'thunder/lightning', u'clear', u'overcast', u'snow', u'rain'], 'curr_value': u'clear', 'suggestion': False}, 'name': u'weather', 'template': 'common_switch_template'}, {'exprop': {'item_name': {'en': u'play music', 'zh': u'播放音乐'}, 'item_list': [u'just monika', u'your reality', u'your reality (piano cover)', u'your reality (eurobeat ver.)', u'i still love you', u'my feelings', u'my confession', u'okay, everyone! (monika)', u'play with me (variant 6)', u'doki doki theme (80s ver.)', u'surprise!', u'玩家自行选择', u'停止/静音'], 'curr_value': u'bgm/credits.ogg', 'suggestion': False}, 'name': u'music', 'template': 'common_switch_template'}, {'exprop': {'item_name': {'en': u'change in-game hair', 'zh': u'更换游戏内发型'}, 'item_list': [False, u'down (twin buns)', u'down (bun)', u'马尾辫', u'bun (middle)', u'pixie cut', u'bun (low)', u'玩家挑选', u'usagi (braided)', u'ponytail', u'丸子头', u'down (ponytail)', u'双马尾', u'ponytail (middle)', u'twin braids', u'齐肩短发', u'丸子编发', u'down', u'放下 (直刘海)', u'双丸子头', u'braid', u'短马尾', u'垂耳兔兔', u'pigtails'], 'curr_value': (u'down',), 'suggestion': False}, 'name': u'hair', 'template': 'common_switch_template'}, {'exprop': {'item_name': {'en': u"change in-game accessory(can't used to unwear accessory)", 'zh': u'更换游戏内饰品(不可用于脱下饰品)'}, 'item_list': [False, u'ribbon (white)', u'玩家挑选'], 'curr_value': None, 'suggestion': False}, 'name': u'acs', 'template': 'common_switch_template'}]
    s_trigger_list = serialize_triggers(trigger_list)
    return build(s_trigger_list)

if __name__ == "__main__":
    print(build_case_260326())