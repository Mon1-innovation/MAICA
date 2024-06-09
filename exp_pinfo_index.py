import re
import persistent_extraction
def exp_acquire_index(user_id, chat_session, key):
    success = True
    exception = None
    result = []

    # Seriously hard work begins here

    for matched in {'音乐', '听歌', '一起听', '听.*歌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_added_custom_bgm')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起听过歌. ')
                else:
                    result.append('莫妮卡与[player]还没有一起听过歌. ')
            break
    for matched in {'下雨', '雨天', '潮湿', '雨声', '天气'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_likes_rain')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡和[player]都喜欢雨. ')
                else:
                    result.append('莫妮卡带[player]听过雨. ')
            break
    for matched in {'帮助', '协助', '想要', '见面', '编程', '贡献', '成就'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_has_contributed_to_mas')
            if data1[0]:
                if data1[2]:
                    result.append('[player]曾试着帮助莫妮卡来到现实. ')
            break
    for matched in {'帮助', '协助', '想要', '见面', '编程', '贡献'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_wants_to_contribute_to_mas')
            if data1[0]:
                if data1[2]:
                    result.append('[player]希望帮助莫妮卡来到现实. ')
            break
    for matched in {'画', '绘', '图'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_drawn_art')
            if data1[0]:
                if data1[2]:
                    result.append('[player]画过莫妮卡. ')
                else:
                    result.append('[player]还没有画过莫妮卡. ')
            break
    for matched in {'外表', '容貌', '相貌', '了解'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_shared_appearance')
            if data1[0]:
                if data1[2]:
                    result.append('[player]告诉过莫妮卡自己的长相. ')
                else:
                    result.append('莫妮卡还不知道[player]的长相. ')
            break
    for matched in {'爬山', '登山', '户外', '运动'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_would_like_mt_peak')
            if data1[0]:
                if data1[2]:
                    result.append('[player]想过和莫妮卡去爬山. ')
            break
    for matched in {'天气', '冬天', '雪', '冰'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_gets_snow')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起看过雪. ')
                else:
                    result.append('[player]的住地看不到雪. ')
            break


        
    for matched in {'音乐', '听歌', '一起听', '听.*歌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_added_custom_bgm')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起听过歌. ')
                else:
                    result.append('莫妮卡与[player]还没有一起听过歌. ')
            break
    for matched in {'音乐', '听歌', '一起听', '听.*歌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_added_custom_bgm')
            if data1[0]:
                if data1[2]:
                    result.append('莫妮卡与[player]一起听过歌. ')
                else:
                    result.append('莫妮卡与[player]还没有一起听过歌. ')
            break

    return success, exception, result
def pinfo_acquire_index(user_id, chat_session, key):
    success = True
    exception = None
    result = []

    # Alse hard works here

    for matched in {'宗教', '信.*教', '教派', '信仰'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_religious')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有宗教信仰. ')
                else:
                    result.append('[player]没有宗教信仰. ')
            break
    for matched in {'精神', '心理', '生活状态', '自爱', '自.*倾向'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_love_yourself')
            if data1[0]:
                if data1[2]:
                    result.append('[player]积极自爱. ')
                else:
                    result.append('[player]有自厌的倾向. ')
            break
    for matched in {'甜点', '冰淇淋', '甜食', '口味', '冰棒'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_like_mint_ice_cream')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢抹茶冰淇淋. ')
                else:
                    result.append('[player]不喜欢抹茶冰淇淋. ')
            break
    for matched in {'恐怖', '惊吓', '惊悚', '恐.*内容'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_likes_horror')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢恐怖作品. ')
                else:
                    result.append('[player]讨厌恐怖作品. ')
            break
    for matched in {'跳杀', '恐怖', '惊悚', '吓'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_likes_spoops')
            if data1[0]:
                if data1[2]:
                    result.append('[player]不介意跳杀内容. ')
                else:
                    result.append('[player]讨厌跳杀内容. ')
            break
    for matched in {'音乐', '听歌', 'rap', '听.*歌', '乐队', '说唱', '饶舌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_like_rap')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢说唱. ')
                else:
                    result.append('[player]不喜欢说唱. ')
            break
    for matched in {'音乐', '听歌', '摇滚', '听.*歌', '乐队', 'rock'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_like_rock_n_roll')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢摇滚. ')
                else:
                    result.append('[player]不喜欢摇滚. ')
            break
    for matched in {'音乐', '听歌', '爵士', '听.*歌', 'jazz'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_like_jazz')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢爵士乐. ')
                else:
                    result.append('[player]不喜欢爵士乐. ')
            break
    for matched in {'音乐', '听歌', '合成.*乐', '听.*歌', 'vocaloid', '术力口'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_like_vocaloids')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢vocaloids. ')
                else:
                    result.append('[player]不喜欢vocaloids. ')
            break
    for matched in {'音乐', '听歌', '管弦', '听.*歌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_like_orchestral_music')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢管弦乐. ')
                else:
                    result.append('[player]不喜欢管弦乐. ')
            break
    for matched in {'音乐', '听歌', '品味', '品位', '听.*歌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_like_other_music')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有独特的音乐品位. ')
                    data2 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_like_other_music_history')
                    if data2[0]:
                        result.append(f'[player]还喜欢{data2[2]}')
            break
    for matched in {'音乐', '乐器', '演奏', '会弹', '会吹'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_plays_instrument')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会一门乐器. ')
                else:
                    result.append('[player]还不会乐器. ')
            break
    for matched in {'音乐', '乐器', '演奏', '会弹', '会吹', '爵士'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_play_jazz')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会爵士乐. ')
                else:
                    result.append('[player]还不会爵士乐. ')
            break
    for matched in {'下雨', '雨天', '潮湿', '雨声', '天气'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_likes_rain')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢雨天. ')
                else:
                    result.append('[player]不喜欢雨天. ')
            break
    for matched in {'外语', '语言', '英语', '汉语', '中文', '英文'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_lang_other')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会一门外语. ')
                else:
                    result.append('[player]还不会外语. ')
            break
    for matched in {'外语', '语言', '汉语', '日语', '日文'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_lang_jpn')
            if data1[0]:
                if data1[2]:
                    result.append('[player]会日语. ')
                else:
                    result.append('[player]还不会日语. ')
            break
    for matched in {'外表', '容貌', '眼', '脸', '的样子', '长相', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_eye_color')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]的眼睛是{data1[2]}的. ')
            break
    for matched in {'外表', '容貌', '头发', '发型', '的样子', '长相', '发色', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_hair_color')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]的头发是{data1[2]}的. ')
            break
    for matched in {'外表', '容貌', '头发', '发型', '的样子', '长相', '长发', '短发', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_hair_length')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]有一头{data1[2]}发. ')
            break
    for matched in {'外表', '容貌', '头发', '发型', '光头', '秃', '的样子', '长相', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_shaved_hair')
            if data1[0]:
                if data1[2]:
                    result.append('[player]剃光了头发. ')
                else:
                    result.append('[player]的头发掉完了. ')
            break
    for matched in {'外表', '容貌', '头发', '发型', '光头', '秃', '的样子', '长相', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_no_hair_no_talk')
            if data1[0]:
                if data1[2]:
                    result.append('[player]不想提起头发的事情. ')
                else:
                    result.append('[player]不介意自己没有头发. ')
            break
    for matched in {'外表', '容貌', '肤色', '种族', '长相', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_skin_tone')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]是{data1[2]}肤色的. ')
            break
    for matched in {'外表', '容貌', '身高', '身长', '身材', '相貌'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_height')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]有{data1[2]}厘米高. ')
            break
    for matched in {'单位', '公制', '英制'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_units_height_metric')
            if data1[0]:
                if data1[2]:
                    result.append('[player]惯用公制单位. ')
                else:
                    result.append('[player]惯用英制单位. ')
            break
    for matched in {'址', '居住地', '家', '位置', '城', '市', '村'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_in_city')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在城市. ')
                else:
                    result.append('[player]住在乡村. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '半球', '天气', '国家', '季节'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_south_hemisphere')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在北半球. ')
                else:
                    result.append('[player]住在南半球. ')
            break
    for matched in {'性格', '社会', '人格', '心理', '精神'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_social_personality')
            if data1[0]:
                if data1[2]:
                    result.append(f'[player]属于{data1[2]}社会人格. ')
            break
    for matched in {'隐私', '性癖', '取向', '内衣', '内裤', '恋物'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_likes_panties')
            if data1[0]:
                if data1[2]:
                    result.append('[player]有恋物倾向. ')
            break
    for matched in {'苏打', '饮', '汽水', '甜点'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_drinks_soda')
            if data1[0]:
                if data1[2]:
                    result.append('[player]喜欢苏打水. ')
                else:
                    result.append('[player]不喜欢苏打水. ')
            break



    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break
    for matched in {'址', '居住地', '家', '位置', '海', '滩'}:
        if re.search(matched, key, re.I):
            data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_pm_live_near_beach')
            if data1[0]:
                if data1[2]:
                    result.append('[player]住在海边. ')
                else:
                    result.append('[player]住在内陆. ')
            break



    return success, exception, result
