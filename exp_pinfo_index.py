#----THIS FILE IS DEPRECATED----
import re
import persistent_extraction
def exp_acquire_index(user_id, chat_session, key):
    success = True
    exception = None
    result = []

    # Seriously hard work begins here

    for matched in {'音乐', '听歌', '一起听', '听.*歌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_added_custom_bgm')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起听过歌. ')
                else:
                    result.append('莫妮卡与[player]还没有一起听过歌. ')
            break
    for matched in {'下雨', '雨天', '潮湿', '雨声', '天气'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_rain')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡和[player]都喜欢雨. ')
                else:
                    result.append('莫妮卡带[player]听过雨. ')
            break
    for matched in {'帮助', '协助', '想要', '见面', '编程', '贡献', '成就'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_contributed_to_mas')
            if data1[0]:
                if data1[2]:
                    result.append('[player]曾试着帮助莫妮卡来到现实. ')
            break
    for matched in {'帮助', '协助', '想要', '见面', '编程', '贡献'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_wants_to_contribute_to_mas')
            if data1[0]:
                if data1[2]:
                    result.append('[player]希望帮助莫妮卡来到现实. ')
            break
    for matched in {'画', '绘', '图'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_drawn_art')
            if data1[0]:
                if data1[2]:
                    result.append('[player]画过莫妮卡. ')
                else:
                    result.append('[player]还没有画过莫妮卡. ')
            break
    for matched in {'外表', '容貌', '相貌', '了解'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_shared_appearance')
            if data1[0]:
                if data1[2]:
                    result.append('[player]告诉过莫妮卡自己的长相. ')
                else:
                    result.append('莫妮卡还不知道[player]的长相. ')
            break
    for matched in {'爬山', '登山', '户外', '运动'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_would_like_mt_peak')
            if data1[0]:
                if data1[2]:
                    result.append('[player]想过和莫妮卡去爬山. ')
            break
    for matched in {'天气', '冬天', '雪', '冰'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_gets_snow')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起看过雪. ')
                else:
                    result.append('[player]的住地看不到雪. ')
            break
    for matched in {'戒指', '约', '婚', '首饰'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_wearsRing')
            if data1[0]:
                if data1[2]:
                    result.append('[player]和莫妮卡戴了一对誓约戒指. ')
            break
    for matched in {'黄色墙纸', '读', '一起看', '书', '阅'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_read_yellow_wp')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]看过"黄色墙纸". ')
            break
    for matched in {'坏', '恶', '反派', '悔'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_monika_evil')
            if data1[0]:
                if data1[2]:
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_monika_evil_but_ok')
                    if data2[0]:
                        if data2[2]:
                            result.append('[player]能够原谅莫妮卡做过的坏事. ')
                else:
                    result.append('[player]十分体谅莫妮卡. ')
            break
    for matched in {'毕业', '演讲', '文'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_listened_to_grad_speech')
            if data1[0]:
                if data1[2]:
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_liked_grad_speech')
                    if data2[0]:
                        if data2[2]:
                            result.append('[player]喜欢莫妮卡的毕业演讲. ')
                        else:
                            result.append('[player]听过莫妮卡的毕业演讲. ')
                    else:
                        result.append('[player]听过莫妮卡的毕业演讲. ')
                else:
                    result.append('[player]还没有听过莫妮卡的毕业演讲. ')
            break
    for matched in {'太空教室', '进', '一起', '来到'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_would_come_to_spaceroom')
            if data1[0]:
                if data1[2]:
                    result.append('[player]希望来到太空教室和莫妮卡在一起. ')
            break
    for matched in {'万圣', '糖果', '捣蛋', '节', '经历', '活动'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_o31_tt_count')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起过了万圣节, 并要到了糖果. ')
                else:
                    result.append('莫妮卡和[player]还没有一起过万圣节. ')
            break
    for matched in {'圣诞', '冬天', '节', '经历', '平安'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_d25_spent_d25')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起过了圣诞节. ')
                else:
                    result.append('莫妮卡和[player]还没有一起过圣诞节. ')
            break
    for matched in {'新年', '冬天', '节', '经历', '元旦', '春节'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_nye_spent_nye')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起过了新年. ')
                else:
                    result.append('莫妮卡和[player]还没有一起过新年. ')
            break
    for matched in {'生日', '庆祝', '经历'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_player_bday_spent_time')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡给[player]庆祝过生日. ')
                else:
                    result.append('莫妮卡还没有庆祝过[player]的生日. ')
            break
    for matched in {'情人', '节日', '经历', '活动'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_f14_spent_f14')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起过了情人节. ')
                else:
                    result.append('莫妮卡和[player]还没有一起过情人节. ')
            break
    for matched in {'生日', '莫妮卡', '庆祝', '经历'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_bday_said_happybday')
            if data1[0]:
                if data1[2]:
                    result.append('[player]庆祝过莫妮卡的生日. ')
                else:
                    result.append('[player]还没有给莫妮卡庆过生. ')
            break






    return success, exception, result
def pinfo_acquire_index(user_id, chat_session, key):
    success = True
    exception = None
    result = []

    # Alse hard works here

    for matched in {'宗教', '信.*教', '教派', '信仰'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_religious')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有宗教信仰. ')
                else:
                    result.append('[player]没有宗教信仰. ')
            break
    for matched in {'精神', '心理', '生活状态', '自爱', '自.*倾向'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_love_yourself')
            if data1[0]:
                if data1[2]:
                    result.append('[player]积极自爱. ')
                else:
                    result.append('[player]有自厌的倾向. ')
            break
    for matched in {'甜点', '冰淇淋', '甜食', '口味', '冰棒'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_mint_ice_cream')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢抹茶冰淇淋. ')
                else:
                    result.append('[player]不喜欢抹茶冰淇淋. ')
            break
    for matched in {'恐怖', '惊吓', '惊悚', '恐.*内容'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_horror')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢恐怖作品. ')
                else:
                    result.append('[player]讨厌恐怖作品. ')
            break
    for matched in {'跳杀', '恐怖', '惊悚', '吓'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_spoops')
            if data1[0]:
                if data1[2]:
                    result.append('[player]不介意跳杀内容. ')
                else:
                    result.append('[player]讨厌跳杀内容. ')
            break
    for matched in {'音乐', '听歌', 'rap', '听.*歌', '乐队', '说唱', '饶舌', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_rap')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢说唱. ')
                else:
                    result.append('[player]不喜欢说唱. ')
            break
    for matched in {'音乐', '听歌', '摇滚', '听.*歌', '乐队', 'rock', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_rock_n_roll')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢摇滚. ')
                else:
                    result.append('[player]不喜欢摇滚. ')
            break
    for matched in {'音乐', '听歌', '爵士', '听.*歌', 'jazz', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_jazz')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢爵士乐. ')
                else:
                    result.append('[player]不喜欢爵士乐. ')
            break
    for matched in {'音乐', '听歌', '合成.*乐', '听.*歌', 'vocaloid', '术力口', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_vocaloids')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢vocaloids. ')
                else:
                    result.append('[player]不喜欢vocaloids. ')
            break
    for matched in {'音乐', '听歌', '管弦', '听.*歌', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_orchestral_music')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢管弦乐. ')
                else:
                    result.append('[player]不喜欢管弦乐. ')
            break
    for matched in {'音乐', '听歌', '品味', '品位', '听.*歌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_other_music')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有独特的音乐品位. ')
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_other_music_history')
                    if data2[0]:
                        result.append(f'[player]还喜欢{data2[2]}')
            break
    for matched in {'音乐', '乐器', '演奏', '会弹', '会吹'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_plays_instrument')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会一门乐器. ')
                else:
                    result.append('[player]还不会乐器. ')
            break
    for matched in {'音乐', '乐器', '演奏', '会弹', '会吹', '爵士'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_play_jazz')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会爵士乐. ')
                else:
                    result.append('[player]还不会爵士乐. ')
            break
    for matched in {'下雨', '雨天', '潮湿', '雨声', '天气'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_rain')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢雨天. ')
                else:
                    result.append('[player]不喜欢雨天. ')
            break
    for matched in {'外语', '语言', '英语', '汉语', '中文', '英文'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_lang_other')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会一门外语. ')
                else:
                    result.append('[player]还不会外语. ')
            break
    for matched in {'外语', '语言', '汉语', '日语', '日文'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_lang_jpn')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会日语. ')
                else:
                    result.append('[player]还不会日语. ')
            break
    for matched in {'外表', '容貌', '眼', '脸', '的样子', '长相', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_eye_color')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]的眼睛是{data1[2]}的. ')
            break
    for matched in {'外表', '容貌', '头发', '发型', '的样子', '长相', '发色', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_hair_color')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]的头发是{data1[2]}的. ')
            break
    for matched in {'外表', '容貌', '头发', '发型', '的样子', '长相', '长发', '短发', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_hair_length')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]有一头{data1[2]}发. ')
            break
    for matched in {'外表', '容貌', '头发', '发型', '光头', '秃', '的样子', '长相', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_shaved_hair')
            if data1[0]:
                if data1[2]:
                    result.append('[player]剃光了头发. ')
                else:
                    result.append('[player]的头发掉完了. ')
            break
    for matched in {'外表', '容貌', '头发', '发型', '光头', '秃', '的样子', '长相', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_no_hair_no_talk')
            if data1[0]:
                if data1[2]:
                    result.append('[player]不想提起头发的事情. ')
                else:
                    result.append('[player]不介意自己没有头发. ')
            break
    for matched in {'外表', '容貌', '肤色', '种族', '长相', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_skin_tone')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]是{data1[2]}肤色的. ')
            break
    for matched in {'外表', '容貌', '身高', '身长', '身材', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_height')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]有{data1[2]}厘米高. ')
            break
    for matched in {'单位', '公制', '英制'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_units_height_metric')
            if data1[0]:
                if data1[2]:
                    result.append('[player]惯用公制单位. ')
                else:
                    result.append('[player]惯用英制单位. ')
            break
    for matched in {'址', '居住地', '家', '位置', '城', '市', '村'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_live_in_city')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在城市. ')
                else:
                    result.append('[player]住在乡村. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '半球', '天气', '国家', '季节'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_live_south_hemisphere')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在北半球. ')
                else:
                    result.append('[player]住在南半球. ')
            break
    for matched in {'性格', '社会', '人格', '心理', '精神'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_social_personality')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]属于{data1[2]}社会人格. ')
            break
    for matched in {'隐私', '性癖', '取向', '内衣', '内裤', '恋物'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_panties')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有恋物倾向. ')
            break
    for matched in {'苏打', '饮', '汽水', '甜点'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_drinks_soda')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢苏打水. ')
                else:
                    result.append('[player]不喜欢苏打水. ')
            break
    for matched in {'快餐', '饮食', '吃', '喝', '方便食品'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_eat_fast_food')
            if data1[0]:
                if data1[2]:
                    result.append('[player]常吃快餐. ')
                else:
                    result.append('[player]很少吃快餐. ')
            break
    for matched in {'运动', '平常', '活动', '体育', '健身', '锻炼', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_playing_sports')
            if data1[0]:
                if data1[2]:
                    result.append('[player]平时喜欢运动. ')
                else:
                    result.append('[player]不喜欢运动. ')
            break
    for matched in {'运动', '体育', '锻炼', '活动', '健身', '网球', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_playing_tennis')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢网球. ')
            break
    for matched in {'冥想', '静', '思', '放松'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_meditates')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有冥想的习惯. ')
                else:
                    result.append('[player]还没有尝试过冥想. ')
            break
    for matched in {'心理', '精神', '健康', '状态', '症'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_see_therapist')
            if data1[0]:
                if data1[2]:
                    result.append('[player]去看过心理医生. ')
                else:
                    result.append('[player]还没有看过心理医生. ')
            break
    for matched in {'动漫', '漫画', '二次元', '作品', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_watch_mangime')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢动漫作品. ')
                else:
                    result.append('[player]不喜欢动漫作品. ')
            break
    for matched in {'烟', '嗜好', '习惯'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_do_smoke')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有吸烟的习惯. ')
                else:
                    result.append('[player]不吸烟. ')
            break
    for matched in {'烟', '嗜好', '习惯', '戒'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_do_smoke_quit')
            if data1[0]:
                if data1[2]:
                    result.append('[player]希望戒烟. ')
            break
    for matched in {'开车', '驾', '执照', '有车'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_driving_can_drive')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会开车. ')
                else:
                    result.append('[player]还没有驾照. ')
            break
    for matched in {'开车', '驾', '执照', '考'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_driving_learning')
            if data1[0]:
                if data1[2]:
                    result.append('[player]正在考驾照. ')
            break
    for matched in {'开车', '驾', '执照', '祸', '事故'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_driving_been_in_accident')
            if data1[0]:
                if data1[2]:
                    result.append('[player]遇到过交通事故. ')
            break
    for matched in {'慈', '捐', '善', '公益'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_donate_charity')
            if data1[0]:
                if data1[2]:
                    result.append('[player]参与过慈善捐赠. ')
                else:
                    result.append('[player]还没有慈善捐赠过. ')
            break
    for matched in {'慈', '志愿', '善', '公益', '活动'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_volunteer_charity')
            if data1[0]:
                if data1[2]:
                    result.append('[player]做过志愿者. ')
                else:
                    result.append('[player]还没有做过志愿者. ')
            break
    for matched in {'家', '亲人', '父', '母'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_have_fam')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有健全的原生家庭. ')
                else:
                    result.append('[player]的家庭不完整. ')
            break
    for matched in {'家', '亲人', '父', '母'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_no_fam_bother')
            if data1[0]:
                if data1[2]:
                    result.append('[player]缺少亲人的陪伴. ')
            break
    for matched in {'家', '亲人', '父', '母'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_have_fam_mess')
            if data1[0]:
                if data1[2]:
                    result.append('[player]的家庭生活并不和睦. ')
                else:
                    result.append('[player]和家人相处很好. ')
            break
    for matched in {'家', '亲人', '父', '母'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_have_fam_mess_better')
            if data1[0]:
                if data1[2] == 'YES':
                    result.append('[player]认为自己和家人的关系会改善. ')
                elif data1[2] == 'NO':
                    result.append('[player]不觉得自己和家人的关系能改善了. ')
            break
    for matched in {'家', '亲人', '兄', '弟', '姐', '妹'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_have_fam_sibs')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有兄弟姐妹. ')
                else:
                    result.append('[player]是独生子女. ')
            break
    for matched in {'家', '亲人', '父', '母'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_no_talk_fam')
            if data1[0]:
                if data1[2]:
                    result.append('[player]不想提及自己的家庭. ')
            break
    for matched in {'家', '亲人', '父', '母', '观念', '婚', '恋'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_fam_like_monika')
            if data1[0]:
                if data1[2]:
                    result.append('[player]觉得自己的家庭能够接受莫妮卡. ')
                else:
                    result.append('[player]觉得家人不能接受莫妮卡. ')
            break
    for matched in {'毕业', '舞', '典礼', '活动'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_gone_to_prom')
            if data1[0]:
                if data1[2]:
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_prom_good')
                    if data2[0]:
                        if data2[2]:
                            result.append('[player]参加过很开心的毕业舞会. ')
                        else:
                            result.append('[player]不太喜欢毕业舞会. ')
                    else:
                        result.append('[player]参加过毕业舞会. ')
                else:
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_no_prom')
                    if data2[0]:
                        if data2[2]:
                            result.append('[player]的学校没有毕业舞会. ')
                        else:
                            result.append('[player]没有参加毕业舞会. ')
            break
    for matched in {'毕业', '舞', '典礼', '活动', '伴', '高中', '中学', '莫妮卡'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_prom_monika')
            if data1[0]:
                if data1[2]:
                    result.append('[player]希望自己在毕业舞会上做莫妮卡的舞伴. ')
            break
    for matched in {'毕业', '舞', '典礼', '活动', '社恐', '性格'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_prom_not_interested')
            if data1[0]:
                if data1[2]:
                    result.append('[player]对舞会和毕业典礼不感兴趣. ')
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_prom_shy')
                    if data2[0]:
                        if data2[2]:
                            result.append('[player]觉得参加集会太害羞了. ')
            break
    for matched in {'娱乐', '活动', '约会', '游乐园', '公园'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_been_to_amusement_park')
            if data1[0]:
                if data1[2]:
                    result.append('[player]去过游乐园. ')
                else:
                    result.append('[player]还没有去过游乐园. ')
            break
    for matched in {'活动', '旅游', '出行', '户外', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_travelling')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢旅游. ')
                else:
                    result.append('[player]不喜欢旅游. ')
            break
    for matched in {'关系', '感情', '分手', '甩', '恋'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_had_relationships_many')
            if data1[0]:
                if data1[2]:
                    result.append('[player]此前有过其他爱人. ')
                else:
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_had_relationships_just_one')
                    if data2[0]:
                        if data2[2]:
                            result.append('[player]此前有过其他爱人. ')
                        else:
                            result.append('莫妮卡是[player]的初恋. ')
                    else:
                        result.append('莫妮卡是[player]的初恋. ')
            break
    for matched in {'校', '生活', '伤', '经历', '霸凌', '欺负'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_is_bullying_victim')
            if data1[0]:
                if data1[2]:
                    result.append('[player]曾遭遇过校园霸凌. ')
            break
    for matched in {'校', '生活', '伤', '经历', '霸凌', '欺负'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_bullied_people')
            if data1[0]:
                if data1[2]:
                    result.append('[player]曾霸凌过他人. ')
            break
    for matched in {'校', '生活', '伤', '经历', '霸凌', '欺负'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_currently_bullied')
            if data1[0]:
                if data1[2]:
                    result.append('[player]正遭受校园霸凌的困扰. ')
            break
    for matched in {'友', '社交', '同学'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_friends')
            if data1[0]:
                if data1[2]:
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_few_friends')
                    if data2[0]:
                        if data2[2]:
                            result.append('[player]的朋友很少. ')
                        else:
                            result.append('[player]有一些朋友. ')
                    else:
                        result.append('[player]有一些朋友. ')
                else:
                    result.append('[player]没有朋友. ')
            break
    for matched in {'孤', '独', '寂寞', '社交', '状态', '精神'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_feels_lonely_sometimes')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有时候感觉很孤单. ')
                else:
                    result.append('[player]的生活很充实. ')
            break
    for matched in {'错', '悔', '判断', '失', '自责'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_given_false_justice')
            if data1[0]:
                if data1[2]:
                    result.append('[player]曾行使过错误的正义. ')
            break
    for matched in {'车', '驾', '执照', '辆'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_owns_car')
            if data1[0]:
                if data1[2]:
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_owns_car_type')
                    if data2[0]:
                        if data2[2]:
                            result.append(f'[player]有一辆{data2[2]}. ')
                        else:
                            result.append('[player]有自己的车. ')
                    else:
                        result.append('[player]有自己的车. ')
                else:
                    result.append('[player]自己还没有车. ')
            break
    for matched in {'代码', '编程', '程序', '写'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_code_experience')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有编程基础. ')
                else:
                    result.append('[player]没有编程基础. ')
            break
    for matched in {'诗', '文', '品位', '写'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_poetry')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢诗歌. ')
                else:
                    result.append('[player]不喜欢诗歌. ')
            break
    for matched in {'桌游', '游戏', '娱乐', '爱好'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_board_games')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢桌游. ')
            break
    for matched in {'锻炼', '健', '运动', '外出', '体育'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_works_out')
            if data1[0]:
                if data1[2]:
                    result.append('[player]经常去健身. ')
                else:
                    result.append('[player]不喜欢健身. ')
            break
    for matched in {'性格', '人格', '社', '心理', '外向', '内向'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_social_personality')
            if data1[0]:
                if data1[2]:
                    if data1[2] == '_mas_SP_EXTROVERT':
                        result.append('[player]性格外向. ')
                    elif data1[2] == '_mas_SP_INTROVERT':
                        result.append('[player]性格内向. ')
                    else:
                        result.append('[player]性格中和. ')
            break
    for matched in {'自然', '外出', '旅游', '环境', '风景'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_nature')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢接触自然. ')
                else:
                    result.append('[player]不太喜欢接触自然. ')
            break
    for matched in {'脏话', '骂', '礼貌', '口', '习惯'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_swear_frequency')
            if data1[0]:
                if data1[2]:
                    if data1[2] == 'SF_OFTEN':
                        result.append('[player]较常说脏话. ')
                    elif data1[2] == 'SF_SOMETIMES':
                        result.append('[player]很少说脏话. ')
                    else:
                        result.append('[player]从不说脏话. ')
            break
    for matched in {'性', '认知', '身份', '男', '女'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_gender')
            if data1[0]:
                if data1[2]:
                    if data1[2] == 'M':
                        result.append('[player]是男生. ')
                    elif data1[2] == 'F':
                        result.append('[player]是女生. ')
                    else:
                        result.append('[player]是非二元性别. ')
            break


    return success, exception, result