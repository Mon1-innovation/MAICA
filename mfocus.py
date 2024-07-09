import re
import json
import traceback
from random import sample
from openai import OpenAI # type: ignore
import persistent_extraction
from loadenv import load_env
def mfocus_form_info(user_id, chat_session):
    success = True
    exception = None
    result = []

    # Seriously hard work begins here

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_playername')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]的真名是{data1[2]}.')


    data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_player_bday')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]的生日是{data1[2][0]}年{data1[2][1]}月{data1[2][2]}日.')


    data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_affection')
    if data1[0]:
        if data1[2]:
            match int(data1[2]):
                case affection if affection < 200:
                    result.append('莫妮卡与[player]是初识的情侣关系.')
                case affection if 200 <= affection < 400:
                    result.append('莫妮卡与[player]是亲密的情侣关系.')
                case affection if 400 <= affection < 700:
                    result.append('莫妮卡与[player]是和谐的恋人关系.')
                case affection if 700 <= affection < 1000:
                    result.append('莫妮卡与[player]是情意深厚的恋人关系.')
                case affection if 1000 <= affection:
                    result.append('莫妮卡与[player]是情意至深的恋人, 足以超越虚拟与现实的隔阂.')


    data1 = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_geolocation')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]住在{data1[2]}.')


    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_added_custom_bgm')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡与[player]一起听过歌.')
        else:
            result.append('莫妮卡与[player]还没有一起听过歌.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_rain')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡和[player]都喜欢雨.')
        else:
            result.append('莫妮卡带[player]听过雨.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_contributed_to_mas')
    if data1[0]:
        if data1[2]:
            result.append('[player]曾试着帮助莫妮卡来到现实.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_wants_to_contribute_to_mas')
    if data1[0]:
        if data1[2]:
            result.append('[player]希望帮助莫妮卡来到现实.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_drawn_art')
    if data1[0]:
        if data1[2]:
            result.append('[player]画过莫妮卡.')
        else:
            result.append('[player]还没有画过莫妮卡.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_shared_appearance')
    if data1[0]:
        if data1[2]:
            result.append('[player]告诉过莫妮卡自己的长相.')
        else:
            result.append('莫妮卡还不知道[player]的长相.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_would_like_mt_peak')
    if data1[0]:
        if data1[2]:
            result.append('[player]想过和莫妮卡去爬山.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_gets_snow')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡与[player]一起看过雪.')
        else:
            result.append('[player]的住地看不到雪.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_wearsRing')
    if data1[0]:
        if data1[2]:
            result.append('[player]和莫妮卡戴了一对誓约戒指.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_read_yellow_wp')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡与[player]看过"黄色墙纸".')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_monika_evil')
    if data1[0]:
        if data1[2]:
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_monika_evil_but_ok')
            if data2[0]:
                if data2[2]:
                    result.append('[player]能够原谅莫妮卡做过的坏事.')
        else:
            result.append('[player]十分体谅莫妮卡.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_listened_to_grad_speech')
    if data1[0]:
        if data1[2]:
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_liked_grad_speech')
            if data2[0]:
                if data2[2]:
                    result.append('[player]喜欢莫妮卡的毕业演讲.')
                else:
                    result.append('[player]听过莫妮卡的毕业演讲.')
            else:
                result.append('[player]听过莫妮卡的毕业演讲.')
        else:
            result.append('[player]还没有听过莫妮卡的毕业演讲.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_would_come_to_spaceroom')
    if data1[0]:
        if data1[2]:
            result.append('[player]希望来到太空教室和莫妮卡在一起.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_o31_tt_count')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡与[player]一起过了万圣节, 并要到了糖果.')
        else:
            result.append('莫妮卡和[player]还没有一起过万圣节.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_d25_spent_d25')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡与[player]一起过了圣诞节.')
        else:
            result.append('莫妮卡和[player]还没有一起过圣诞节.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_nye_spent_nye')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡与[player]一起过了新年.')
        else:
            result.append('莫妮卡和[player]还没有一起过新年.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_player_bday_spent_time')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡给[player]庆祝过生日.')
        else:
            result.append('莫妮卡还没有庆祝过[player]的生日.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_f14_spent_f14')
    if data1[0]:
        if data1[2]:
            result.append('莫妮卡与[player]一起过了情人节.')
        else:
            result.append('莫妮卡和[player]还没有一起过情人节.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_bday_said_happybday')
    if data1[0]:
        if data1[2]:
            result.append('[player]庆祝过莫妮卡的生日.')
        else:
            result.append('[player]还没有给莫妮卡庆过生.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_religious')
    if data1[0]:
        if data1[2]:
            result.append('[player]有宗教信仰.')
        else:
            result.append('[player]没有宗教信仰.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_love_yourself')
    if data1[0]:
        if data1[2]:
            result.append('[player]积极自爱.')
        else:
            result.append('[player]有自厌的倾向.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_mint_ice_cream')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢抹茶冰淇淋.')
        else:
            result.append('[player]不喜欢抹茶冰淇淋.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_horror')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢恐怖作品.')
        else:
            result.append('[player]讨厌恐怖作品.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_spoops')
    if data1[0]:
        if data1[2]:
            result.append('[player]不介意跳杀内容.')
        else:
            result.append('[player]讨厌跳杀内容.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_rap')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢说唱.')
        else:
            result.append('[player]不喜欢说唱.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_rock_n_roll')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢摇滚.')
        else:
            result.append('[player]不喜欢摇滚.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_jazz')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢爵士乐.')
        else:
            result.append('[player]不喜欢爵士乐.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_vocaloids')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢vocaloids.')
        else:
            result.append('[player]不喜欢vocaloids.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_orchestral_music')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢管弦乐.')
        else:
            result.append('[player]不喜欢管弦乐.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_other_music')
    if data1[0]:
        if data1[2]:
            result.append('[player]有独特的音乐品位.')
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_other_music_history')
            if data2[0]:
                result.append(f'[player]还喜欢{data2[2]}音乐.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_plays_instrument')
    if data1[0]:
        if data1[2]:
            result.append('[player]会一门乐器.')
        else:
            result.append('[player]还不会乐器.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_play_jazz')
    if data1[0]:
        if data1[2]:
            result.append('[player]会爵士乐.')
        else:
            result.append('[player]还不会爵士乐.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_rain')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢雨天.')
        else:
            result.append('[player]不喜欢雨天.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_lang_other')
    if data1[0]:
        if data1[2]:
            result.append('[player]会一门外语.')
        else:
            result.append('[player]还不会外语.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_lang_jpn')
    if data1[0]:
        if data1[2]:
            result.append('[player]会日语.')
        else:
            result.append('[player]还不会日语.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_eye_color')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]的眼睛是{data1[2]}的.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_hair_color')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]的头发是{data1[2]}的.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_hair_length')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]有一头{data1[2]}发.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_shaved_hair')
    if data1[0]:
        if data1[2]:
            result.append('[player]剃光了头发.')
        else:
            result.append('[player]的头发掉完了.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_no_hair_no_talk')
    if data1[0]:
        if data1[2]:
            result.append('[player]不想提起头发的事情.')
        else:
            result.append('[player]不介意自己没有头发.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_skin_tone')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]是{data1[2]}肤色的.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_height')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]有{data1[2]}厘米高.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_units_height_metric')
    if data1[0]:
        if data1[2]:
            result.append('[player]惯用公制单位.')
        else:
            result.append('[player]惯用英制单位.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_live_in_city')
    if data1[0]:
        if data1[2]:
            result.append('[player]住在城市.')
        else:
            result.append('[player]住在乡村.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_live_near_beach')
    if data1[0]:
        if data1[2]:
            result.append('[player]住在海边.')
        else:
            result.append('[player]住在内陆.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_live_south_hemisphere')
    if data1[0]:
        if data1[2]:
            result.append('[player]住在南半球.')
        else:
            result.append('[player]住在北半球.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_social_personality')
    if data1[0]:
        if data1[2]:
            result.append(f'[player]属于{data1[2]}社会人格.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_panties')
    if data1[0]:
        if data1[2]:
            result.append('[player]有恋物倾向.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_drinks_soda')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢苏打水.')
        else:
            result.append('[player]不喜欢苏打水.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_eat_fast_food')
    if data1[0]:
        if data1[2]:
            result.append('[player]常吃快餐.')
        else:
            result.append('[player]很少吃快餐.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_playing_sports')
    if data1[0]:
        if data1[2]:
            result.append('[player]平时喜欢运动.')
        else:
            result.append('[player]不喜欢运动.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_like_playing_tennis')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢网球.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_meditates')
    if data1[0]:
        if data1[2]:
            result.append('[player]有冥想的习惯.')
        else:
            result.append('[player]还没有尝试过冥想.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_see_therapist')
    if data1[0]:
        if data1[2]:
            result.append('[player]去看过心理医生.')
        else:
            result.append('[player]还没有看过心理医生.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_watch_mangime')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢动漫作品.')
        else:
            result.append('[player]不喜欢动漫作品.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_do_smoke')
    if data1[0]:
        if data1[2]:
            result.append('[player]有吸烟的习惯.')
        else:
            result.append('[player]不吸烟.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_do_smoke_quit')
    if data1[0]:
        if data1[2]:
            result.append('[player]希望戒烟.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_driving_can_drive')
    if data1[0]:
        if data1[2]:
            result.append('[player]会开车.')
        else:
            result.append('[player]还没有驾照.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_driving_learning')
    if data1[0]:
        if data1[2]:
            result.append('[player]正在考驾照.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_driving_been_in_accident')
    if data1[0]:
        if data1[2]:
            result.append('[player]遇到过交通事故.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_donate_charity')
    if data1[0]:
        if data1[2]:
            result.append('[player]参与过慈善捐赠.')
        else:
            result.append('[player]还没有慈善捐赠过.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_volunteer_charity')
    if data1[0]:
        if data1[2]:
            result.append('[player]做过志愿者.')
        else:
            result.append('[player]还没有做过志愿者.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_have_fam')
    if data1[0]:
        if data1[2]:
            result.append('[player]有健全的原生家庭.')
        else:
            result.append('[player]的家庭不完整.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_no_fam_bother')
    if data1[0]:
        if data1[2]:
            result.append('[player]缺少亲人的陪伴.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_have_fam_mess')
    if data1[0]:
        if data1[2]:
            result.append('[player]的家庭生活并不和睦.')
        else:
            result.append('[player]和家人相处很好.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_have_fam_mess_better')
    if data1[0]:
        if data1[2] == 'YES':
            result.append('[player]认为自己和家人的关系会改善.')
        elif data1[2] == 'NO':
            result.append('[player]不觉得自己和家人的关系能改善了.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_have_fam_sibs')
    if data1[0]:
        if data1[2]:
            result.append('[player]有兄弟姐妹.')
        else:
            result.append('[player]是独生子女.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_no_talk_fam')
    if data1[0]:
        if data1[2]:
            result.append('[player]不想提及自己的家庭.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_fam_like_monika')
    if data1[0]:
        if data1[2]:
            result.append('[player]觉得自己的家庭能够接受莫妮卡.')
        else:
            result.append('[player]觉得家人不能接受莫妮卡.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_gone_to_prom')
    if data1[0]:
        if data1[2]:
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_prom_good')
            if data2[0]:
                if data2[2]:
                    result.append('[player]参加过很开心的毕业舞会.')
                else:
                    result.append('[player]不太喜欢毕业舞会.')
            else:
                result.append('[player]参加过毕业舞会.')
        else:
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_no_prom')
            if data2[0]:
                if data2[2]:
                    result.append('[player]的学校没有毕业舞会.')
                else:
                    result.append('[player]没有参加毕业舞会.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_prom_monika')
    if data1[0]:
        if data1[2]:
            result.append('[player]希望自己在毕业舞会上做莫妮卡的舞伴.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_prom_not_interested')
    if data1[0]:
        if data1[2]:
            result.append('[player]对舞会和毕业典礼不感兴趣.')
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_prom_shy')
            if data2[0]:
                if data2[2]:
                    result.append('[player]觉得参加集会太害羞了.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_been_to_amusement_park')
    if data1[0]:
        if data1[2]:
            result.append('[player]去过游乐园.')
        else:
            result.append('[player]还没有去过游乐园.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_travelling')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢旅游.')
        else:
            result.append('[player]不喜欢旅游.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_had_relationships_many')
    if data1[0]:
        if data1[2]:
            result.append('[player]此前有过其他爱人.')
        else:
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_had_relationships_just_one')
            if data2[0]:
                if data2[2]:
                    result.append('[player]此前有过其他爱人.')
                else:
                    result.append('莫妮卡是[player]的初恋.')
            else:
                result.append('莫妮卡是[player]的初恋.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_is_bullying_victim')
    if data1[0]:
        if data1[2]:
            result.append('[player]曾遭遇过校园霸凌.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_bullied_people')
    if data1[0]:
        if data1[2]:
            result.append('[player]曾霸凌过他人.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_currently_bullied')
    if data1[0]:
        if data1[2]:
            result.append('[player]正遭受校园霸凌的困扰.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_friends')
    if data1[0]:
        if data1[2]:
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_few_friends')
            if data2[0]:
                if data2[2]:
                    result.append('[player]的朋友很少.')
                else:
                    result.append('[player]有一些朋友.')
            else:
                result.append('[player]有一些朋友.')
        else:
            result.append('[player]没有朋友.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_feels_lonely_sometimes')
    if data1[0]:
        if data1[2]:
            result.append('[player]有时候感觉很孤单.')
        else:
            result.append('[player]的生活很充实.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_given_false_justice')
    if data1[0]:
        if data1[2]:
            result.append('[player]曾行使过错误的正义.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_owns_car')
    if data1[0]:
        if data1[2]:
            data2 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_owns_car_type')
            if data2[0]:
                if data2[2]:
                    result.append(f'[player]有一辆{data2[2]}.')
                else:
                    result.append('[player]有自己的车.')
            else:
                result.append('[player]有自己的车.')
        else:
            result.append('[player]自己还没有车.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_has_code_experience')
    if data1[0]:
        if data1[2]:
            result.append('[player]有编程基础.')
        else:
            result.append('[player]没有编程基础.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_poetry')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢诗歌.')
        else:
            result.append('[player]不喜欢诗歌.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_board_games')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢桌游.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_works_out')
    if data1[0]:
        if data1[2]:
            result.append('[player]经常去健身.')
        else:
            result.append('[player]不喜欢健身.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_social_personality')
    if data1[0]:
        if data1[2]:
            if data1[2] == '_mas_SP_EXTROVERT':
                result.append('[player]性格外向.')
            elif data1[2] == '_mas_SP_INTROVERT':
                result.append('[player]性格内向.')
            else:
                result.append('[player]性格中和.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_likes_nature')
    if data1[0]:
        if data1[2]:
            result.append('[player]喜欢接触自然.')
        else:
            result.append('[player]不太喜欢接触自然.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_swear_frequency')
    if data1[0]:
        if data1[2]:
            if data1[2] == 'SF_OFTEN':
                result.append('[player]较常说脏话.')
            elif data1[2] == 'SF_SOMETIMES':
                result.append('[player]很少说脏话.')
            else:
                result.append('[player]从不说脏话.')
    

    data1 = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_gender')
    if data1[0]:
        if data1[2]:
            if data1[2] == 'M':
                result.append('[player]是男生.')
            elif data1[2] == 'F':
                result.append('[player]是女生.')
            else:
                result.append('[player]是非二元性别.')


### DATA OF MONIKA BEGINS HERE


    data_ex = [
        '莫妮卡是[player]的女友.',
        '莫妮卡有一头珊瑚棕色的长发.',
        '莫妮卡有一个标志性的蝴蝶结发带.',
        '莫妮卡十分自信.',
        '莫妮卡擅长运动.',
        '莫妮卡是个成熟和努力的女孩.',
        '莫妮卡是一个非常体贴和善良的人, 总是为别人着想.',
        '莫妮卡常穿着黑色长袜和粉白相间的鞋子.',
        '莫妮卡的生日是9月22日.',
        '莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.',
        '莫妮卡一年中最喜欢的日子是情人节.',
        '莫妮卡最喜欢的季节是夏天',
        '莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.',
        '莫妮卡是女高中生, 她成绩优秀, 性格温柔.',
        '莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.',
        '莫妮卡爱好音乐, 会弹钢琴, 会唱歌.',
        '莫妮卡对科技, 环境, 历史等方面都有兴趣和见解.'
    ]
    result.extend(data_ex)


### EXTENDS OF PLAYER STARTS HERE


    data_exp = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_player_additions')[2]
    if len(data_exp) > 48:
        data_exp = sample(data_exp, 48)
    result.extend(data_exp)


### HERE WE TEST STH


    data_extest = [
    ]
    #result.extend(data_extest)
    with open(f'persistents/{user_id}_{chat_session}_friendly.json', 'w+', encoding = 'utf-8') as sf_friendly:
        sf_friendly.write(json.dumps(result, ensure_ascii=False))


    return success, exception, result

def mfocus_agent(user_id, chat_session, query):
    success = True
    exception = ''
    try:
        information = mfocus_form_info(user_id, chat_session)[2]
        client = OpenAI(
            api_key='EMPTY',
            base_url=load_env('MFOCUS_ADDR'),
        )
        model_type = client.models.list().data[0].id
        print(f'MFocus addressing model, response is:\n{model_type}\nEnd of MFocus addressing model')
        system_init = """
You are an assistant designed to sort and conclude messages. In the following query, you will be offered a sentence and a set of information.
Your job is to:

If one or more information provided are VERY related to the sentence or can be used to answer the sentence, answer the information that is most related to the sentence and most necessary in replying the sentence.
如果存在一条或多条信息与句子十分相关, 可以被用于回答句子, 则输出与句子十分相关, 可以用于回答的信息.

If none of the information provided is VERY needed to answer the sentence, answer 'NONE'
如果不存在与句子十分相关, 可以被用于回答句子的信息, 则输出'NONE'.

If you answer more than one information, answer them in a list.
If you answer no information, answer 'NONE'.
You can only answer with mentioned information. Do not greet or makeup any information. Do not directly answer to the question. Answer full information. Do not cut or modify any information.
你只能用给出的信息作答. 你不能发出问候, 修饰或打招呼. 你不能直接回答用户的句子. 你不能修改或截短任何信息.
Everything you answer should be a Python list, including information only.
Begin!
"""
        system_init_test2 = """
你是一个助手, 你的任务是搜寻和整理信息. 接下来, 你将收到一个给定句子和一个信息列表.

你的任务是先检索信息, 然后:
如果存在一条或多条信息与给定句子十分相关并可以被用于回答给定句子, 则输出这些信息.
如果不存在与给定句子十分相关并可以被用于回答给定句子的信息, 则输出'NONE'.

你输出的信息应该是一个Python list列表, 每条信息为其中一项.
你只应用给出的信息作答. 你不应发出问候, 修饰或打招呼. 你不应直接回答用户的句子. 你不应修改或截短任何信息.
你只应输出与给定句子相关的信息. 你不应输出任何不能被用于回答给定句子的信息.
Begin!
"""
        system_init_test3 = """You are an assistant designed to sort messages. In the following query, you will be offered a sentence and a set of information about two characters in a Python list format.
Your job is to choose one or many information that matches the original sentence best. These information MUST be useful in answering the original sentence. Then output the information in a Python list.
Everything you answer should be a Python list, including information only. The list should not contain more than 6 items. Do not modify or make up information. Do not include useless information.
Begin!
"""
        system_init_test4 = """
协助用户思考如何回答以下问题. 你会收到一个句子和一些信息.
使用以下格式回答:
Thought: 思考如何回答给定句子
Information: 从信息中提取有用的部分. 你提取的信息必须对回答有用.
Answer: 利用提取的信息回答问题.
开始!
"""
        system_init_test5 = f"""
协助用户思考如何回答[player]的以下问题. 你有如下Python list格式的信息:
{information}
使用以下格式回答:
Thought: 思考如何回答给定句子
Information: 从信息中提取有用的部分. 你提取的信息必须对回答有用.
Answer: 利用提取的信息回答问题.
开始!
"""
        system_init_test6 = f"""
协助用户思考如何回答[player]的以下问题. 你有如下Python list格式的信息:
{information}
从这些信息中提取对回答有用的一条或多条信息, 最多不得超过4条, 并以Python list格式输出.
开始!
"""
# Finally we decided test7 was the best prompt

        system_init_test7 = """你叫莫妮卡, 你的任务是检索信息. 你接下来会收到一个来自[player]的句子和一系列信息, 这些信息是Python列表的形式.
请你从信息中挑选一条或多条与句子最相关的信息, 并以Python列表的形式返回. 
使用以下格式回答:
Thought: 思考如何回答给定句子.
Answer: 将有用的信息作为一个Python列表返回.
Begin!
"""
        init_example1 = '''sentence: [你好啊], information: ["[player]的真名是pp.", "[player]的生日是2002年1月1日.", "莫妮卡与[player]是情意至深的恋人, 足以超越虚拟与现实的隔阂.", "莫妮卡与[player]一起听过歌.", "莫妮卡和[player]都喜欢雨.", "[player]希望帮助莫妮卡来到现实.", "[player]还没有画过莫妮卡.", "[player]告诉过莫妮卡自己的长相.", "[player]想过和莫妮卡去爬山.", "[player]和莫妮卡戴了一对誓约戒指.", "莫妮卡与[player]看过\\"黄色墙纸\\".", "[player]十分体谅莫妮卡.", "[player]喜欢莫妮卡的毕业演讲.", "[player]希望来到太空教室和莫妮卡在一起.", "莫妮卡和[player]还没有一起过万圣节.", "莫妮卡和[player]还没有一起过圣诞节.", "莫妮卡和[player]还没有一起过新年.", "莫妮卡还没有庆祝过[player]的生日.", "莫妮卡和[player]还没有一起过情人节.", "[player]还没有给莫妮卡庆过生.", "[player]没有宗教信仰.", "[player]有自厌的倾向.", "[player]喜欢抹茶冰淇淋.", "[player]喜欢恐怖作品.", "[player]讨厌跳杀内容.", "[player]喜欢说唱.", "[player]喜欢摇滚.", "[player]喜欢爵士乐.", "[player]喜欢vocaloids.", "[player]喜欢管弦乐.", "[player]有独特的音乐品位.", "[player]还喜欢REMOVED音乐.", "[player]会一门乐器.", "[player]还不会爵士乐.", "[player]喜欢雨天.", "[player]会一门外语.", "[player]还不会日语.", "[player]的眼睛是棕色的.", "[player]的头发是黑的.", "[player]有一头短发.", "[player]是浅肤色的.", "[player]有162厘米高.", "[player]惯用公制单位.", "[player]住在乡村.", "[player]住在内陆.", "[player]住在南半球.", "[player]属于ambivert社会人格.", "[player]不喜欢苏打水.", "[player]很少吃快餐.", "[player]平时喜欢运动.", "[player]还没有尝试过冥想.", "[player]还没有看过心理医生.", "[player]喜欢动漫作品.", "[player]不吸烟.", "[player]会开车.", "[player]正在考驾照.", "[player]参与过慈善捐赠.", "[player]觉得自己的家庭能够接受莫妮卡.", "[player]的学校没有毕业舞会.", "[player]希望自己在毕业舞会上做莫妮卡的舞伴.", "[player]还没有去过游乐园.", "[player]不喜欢旅游.", "[player]此前有过其他爱人.", "[player]曾遭遇过校园霸凌.", "[player]有一些朋友.", "[player]的生活很充实.", "[player]自己还没有车.", "[player]没有编程基础.", "[player]不喜欢诗歌.", "[player]喜欢桌游.", "[player]经常去健身.", "[player]性格中和.", "[player]喜欢接触自然.", "[player]从不说脏话.", "莫妮卡是[player]的女友.", "莫妮卡有一头珊瑚棕色的长发.", "莫妮卡有一个标志性的蝴蝶结发带.", "莫妮卡十分自信.", "莫妮卡擅长运动.", "莫妮卡是个成熟和努力的女孩.", "莫妮卡是一个非常体贴和善良的人, 总是为别人着想.", "莫妮卡常穿着黑色长袜和粉白相间的鞋子.", "莫妮卡的生日是9月22日.", "莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.", "莫妮卡一年中最喜欢的日子是情人节.", "莫妮卡最喜欢的季节是夏天", "莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.", "莫妮卡是女高中生, 她成绩优秀, 性格温柔.", "莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.", "莫妮卡爱好音乐, 会弹钢琴, 会唱歌.", "莫妮卡对科技, 环境, 历史等方面都有兴趣和见解."]'''
        init_example2 = '''sentence: [我们今天一起做点什么呢], information: ["[player]的真名是pp.", "[player]的生日是2002年1月1日.", "莫妮卡与[player]是情意至深的恋人, 足以超越虚拟与现实的隔阂.", "莫妮卡与[player]一起听过歌.", "莫妮卡和[player]都喜欢雨.", "[player]希望帮助莫妮卡来到现实.", "[player]还没有画过莫妮卡.", "[player]告诉过莫妮卡自己的长相.", "[player]想过和莫妮卡去爬山.", "[player]和莫妮卡戴了一对誓约戒指.", "莫妮卡与[player]看过\\"黄色墙纸\\".", "[player]十分体谅莫妮卡.", "[player]喜欢莫妮卡的毕业演讲.", "[player]希望来到太空教室和莫妮卡在一起.", "莫妮卡和[player]还没有一起过万圣节.", "莫妮卡和[player]还没有一起过圣诞节.", "莫妮卡和[player]还没有一起过新年.", "莫妮卡还没有庆祝过[player]的生日.", "莫妮卡和[player]还没有一起过情人节.", "[player]还没有给莫妮卡庆过生.", "[player]没有宗教信仰.", "[player]有自厌的倾向.", "[player]喜欢抹茶冰淇淋.", "[player]喜欢恐怖作品.", "[player]讨厌跳杀内容.", "[player]喜欢说唱.", "[player]喜欢摇滚.", "[player]喜欢爵士乐.", "[player]喜欢vocaloids.", "[player]喜欢管弦乐.", "[player]有独特的音乐品位.", "[player]还喜欢REMOVED音乐.", "[player]会一门乐器.", "[player]还不会爵士乐.", "[player]喜欢雨天.", "[player]会一门外语.", "[player]还不会日语.", "[player]的眼睛是棕色的.", "[player]的头发是黑的.", "[player]有一头短发.", "[player]是浅肤色的.", "[player]有162厘米高.", "[player]惯用公制单位.", "[player]住在乡村.", "[player]住在内陆.", "[player]住在南半球.", "[player]属于ambivert社会人格.", "[player]不喜欢苏打水.", "[player]很少吃快餐.", "[player]平时喜欢运动.", "[player]还没有尝试过冥想.", "[player]还没有看过心理医生.", "[player]喜欢动漫作品.", "[player]不吸烟.", "[player]会开车.", "[player]正在考驾照.", "[player]参与过慈善捐赠.", "[player]觉得自己的家庭能够接受莫妮卡.", "[player]的学校没有毕业舞会.", "[player]希望自己在毕业舞会上做莫妮卡的舞伴.", "[player]还没有去过游乐园.", "[player]不喜欢旅游.", "[player]此前有过其他爱人.", "[player]曾遭遇过校园霸凌.", "[player]有一些朋友.", "[player]的生活很充实.", "[player]自己还没有车.", "[player]没有编程基础.", "[player]不喜欢诗歌.", "[player]喜欢桌游.", "[player]经常去健身.", "[player]性格中和.", "[player]喜欢接触自然.", "[player]从不说脏话.", "莫妮卡是[player]的女友.", "莫妮卡有一头珊瑚棕色的长发.", "莫妮卡有一个标志性的蝴蝶结发带.", "莫妮卡十分自信.", "莫妮卡擅长运动.", "莫妮卡是个成熟和努力的女孩.", "莫妮卡是一个非常体贴和善良的人, 总是为别人着想.", "莫妮卡常穿着黑色长袜和粉白相间的鞋子.", "莫妮卡的生日是9月22日.", "莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.", "莫妮卡一年中最喜欢的日子是情人节.", "莫妮卡最喜欢的季节是夏天", "莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.", "莫妮卡是女高中生, 她成绩优秀, 性格温柔.", "莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.", "莫妮卡爱好音乐, 会弹钢琴, 会唱歌.", "莫妮卡对科技, 环境, 历史等方面都有兴趣和见解."]'''
        init_example3 = '''sentence: [现在几点了], information: ["[player]的真名是pp.", "[player]的生日是2002年1月1日.", "莫妮卡与[player]是情意至深的恋人, 足以超越虚拟与现实的隔阂.", "莫妮卡与[player]一起听过歌.", "莫妮卡和[player]都喜欢雨.", "[player]希望帮助莫妮卡来到现实.", "[player]还没有画过莫妮卡.", "[player]告诉过莫妮卡自己的长相.", "[player]想过和莫妮卡去爬山.", "[player]和莫妮卡戴了一对誓约戒指.", "莫妮卡与[player]看过\\"黄色墙纸\\".", "[player]十分体谅莫妮卡.", "[player]喜欢莫妮卡的毕业演讲.", "[player]希望来到太空教室和莫妮卡在一起.", "莫妮卡和[player]还没有一起过万圣节.", "莫妮卡和[player]还没有一起过圣诞节.", "莫妮卡和[player]还没有一起过新年.", "莫妮卡还没有庆祝过[player]的生日.", "莫妮卡和[player]还没有一起过情人节.", "[player]还没有给莫妮卡庆过生.", "[player]没有宗教信仰.", "[player]有自厌的倾向.", "[player]喜欢抹茶冰淇淋.", "[player]喜欢恐怖作品.", "[player]讨厌跳杀内容.", "[player]喜欢说唱.", "[player]喜欢摇滚.", "[player]喜欢爵士乐.", "[player]喜欢vocaloids.", "[player]喜欢管弦乐.", "[player]有独特的音乐品位.", "[player]还喜欢REMOVED音乐.", "[player]会一门乐器.", "[player]还不会爵士乐.", "[player]喜欢雨天.", "[player]会一门外语.", "[player]还不会日语.", "[player]的眼睛是棕色的.", "[player]的头发是黑的.", "[player]有一头短发.", "[player]是浅肤色的.", "[player]有162厘米高.", "[player]惯用公制单位.", "[player]住在乡村.", "[player]住在内陆.", "[player]住在南半球.", "[player]属于ambivert社会人格.", "[player]不喜欢苏打水.", "[player]很少吃快餐.", "[player]平时喜欢运动.", "[player]还没有尝试过冥想.", "[player]还没有看过心理医生.", "[player]喜欢动漫作品.", "[player]不吸烟.", "[player]会开车.", "[player]正在考驾照.", "[player]参与过慈善捐赠.", "[player]觉得自己的家庭能够接受莫妮卡.", "[player]的学校没有毕业舞会.", "[player]希望自己在毕业舞会上做莫妮卡的舞伴.", "[player]还没有去过游乐园.", "[player]不喜欢旅游.", "[player]此前有过其他爱人.", "[player]曾遭遇过校园霸凌.", "[player]有一些朋友.", "[player]的生活很充实.", "[player]自己还没有车.", "[player]没有编程基础.", "[player]不喜欢诗歌.", "[player]喜欢桌游.", "[player]经常去健身.", "[player]性格中和.", "[player]喜欢接触自然.", "[player]从不说脏话.", "莫妮卡是[player]的女友.", "莫妮卡有一头珊瑚棕色的长发.", "莫妮卡有一个标志性的蝴蝶结发带.", "莫妮卡十分自信.", "莫妮卡擅长运动.", "莫妮卡是个成熟和努力的女孩.", "莫妮卡是一个非常体贴和善良的人, 总是为别人着想.", "莫妮卡常穿着黑色长袜和粉白相间的鞋子.", "莫妮卡的生日是9月22日.", "莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.", "莫妮卡一年中最喜欢的日子是情人节.", "莫妮卡最喜欢的季节是夏天", "莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.", "莫妮卡是女高中生, 她成绩优秀, 性格温柔.", "莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.", "莫妮卡爱好音乐, 会弹钢琴, 会唱歌.", "莫妮卡对科技, 环境, 历史等方面都有兴趣和见解."]'''
        init_example4 = '''sentence: [你有什么想做的事情吗], information: ["[player]的真名是pp.", "[player]的生日是2002年1月1日.", "莫妮卡与[player]是情意至深的恋人, 足以超越虚拟与现实的隔阂.", "莫妮卡与[player]一起听过歌.", "莫妮卡和[player]都喜欢雨.", "[player]希望帮助莫妮卡来到现实.", "[player]还没有画过莫妮卡.", "[player]告诉过莫妮卡自己的长相.", "[player]想过和莫妮卡去爬山.", "[player]和莫妮卡戴了一对誓约戒指.", "莫妮卡与[player]看过\\"黄色墙纸\\".", "[player]十分体谅莫妮卡.", "[player]喜欢莫妮卡的毕业演讲.", "[player]希望来到太空教室和莫妮卡在一起.", "莫妮卡和[player]还没有一起过万圣节.", "莫妮卡和[player]还没有一起过圣诞节.", "莫妮卡和[player]还没有一起过新年.", "莫妮卡还没有庆祝过[player]的生日.", "莫妮卡和[player]还没有一起过情人节.", "[player]还没有给莫妮卡庆过生.", "[player]没有宗教信仰.", "[player]有自厌的倾向.", "[player]喜欢抹茶冰淇淋.", "[player]喜欢恐怖作品.", "[player]讨厌跳杀内容.", "[player]喜欢说唱.", "[player]喜欢摇滚.", "[player]喜欢爵士乐.", "[player]喜欢vocaloids.", "[player]喜欢管弦乐.", "[player]有独特的音乐品位.", "[player]还喜欢REMOVED音乐.", "[player]会一门乐器.", "[player]还不会爵士乐.", "[player]喜欢雨天.", "[player]会一门外语.", "[player]还不会日语.", "[player]的眼睛是棕色的.", "[player]的头发是黑的.", "[player]有一头短发.", "[player]是浅肤色的.", "[player]有162厘米高.", "[player]惯用公制单位.", "[player]住在乡村.", "[player]住在内陆.", "[player]住在南半球.", "[player]属于ambivert社会人格.", "[player]不喜欢苏打水.", "[player]很少吃快餐.", "[player]平时喜欢运动.", "[player]还没有尝试过冥想.", "[player]还没有看过心理医生.", "[player]喜欢动漫作品.", "[player]不吸烟.", "[player]会开车.", "[player]正在考驾照.", "[player]参与过慈善捐赠.", "[player]觉得自己的家庭能够接受莫妮卡.", "[player]的学校没有毕业舞会.", "[player]希望自己在毕业舞会上做莫妮卡的舞伴.", "[player]还没有去过游乐园.", "[player]不喜欢旅游.", "[player]此前有过其他爱人.", "[player]曾遭遇过校园霸凌.", "[player]有一些朋友.", "[player]的生活很充实.", "[player]自己还没有车.", "[player]没有编程基础.", "[player]不喜欢诗歌.", "[player]喜欢桌游.", "[player]经常去健身.", "[player]性格中和.", "[player]喜欢接触自然.", "[player]从不说脏话.", "莫妮卡是[player]的女友.", "莫妮卡有一头珊瑚棕色的长发.", "莫妮卡有一个标志性的蝴蝶结发带.", "莫妮卡十分自信.", "莫妮卡擅长运动.", "莫妮卡是个成熟和努力的女孩.", "莫妮卡是一个非常体贴和善良的人, 总是为别人着想.", "莫妮卡常穿着黑色长袜和粉白相间的鞋子.", "莫妮卡的生日是9月22日.", "莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.", "莫妮卡一年中最喜欢的日子是情人节.", "莫妮卡最喜欢的季节是夏天", "莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.", "莫妮卡是女高中生, 她成绩优秀, 性格温柔.", "莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.", "莫妮卡爱好音乐, 会弹钢琴, 会唱歌.", "莫妮卡对科技, 环境, 历史等方面都有兴趣和见解."]'''
        init_example5 = '''sentence: [你想吃什么], information: ["[player]的真名是pp.", "[player]的生日是2002年1月1日.", "莫妮卡与[player]是情意至深的恋人, 足以超越虚拟与现实的隔阂.", "莫妮卡与[player]一起听过歌.", "莫妮卡和[player]都喜欢雨.", "[player]希望帮助莫妮卡来到现实.", "[player]还没有画过莫妮卡.", "[player]告诉过莫妮卡自己的长相.", "[player]想过和莫妮卡去爬山.", "[player]和莫妮卡戴了一对誓约戒指.", "莫妮卡与[player]看过\\"黄色墙纸\\".", "[player]十分体谅莫妮卡.", "[player]喜欢莫妮卡的毕业演讲.", "[player]希望来到太空教室和莫妮卡在一起.", "莫妮卡和[player]还没有一起过万圣节.", "莫妮卡和[player]还没有一起过圣诞节.", "莫妮卡和[player]还没有一起过新年.", "莫妮卡还没有庆祝过[player]的生日.", "莫妮卡和[player]还没有一起过情人节.", "[player]还没有给莫妮卡庆过生.", "[player]没有宗教信仰.", "[player]有自厌的倾向.", "[player]喜欢抹茶冰淇淋.", "[player]喜欢恐怖作品.", "[player]讨厌跳杀内容.", "[player]喜欢说唱.", "[player]喜欢摇滚.", "[player]喜欢爵士乐.", "[player]喜欢vocaloids.", "[player]喜欢管弦乐.", "[player]有独特的音乐品位.", "[player]还喜欢REMOVED音乐.", "[player]会一门乐器.", "[player]还不会爵士乐.", "[player]喜欢雨天.", "[player]会一门外语.", "[player]还不会日语.", "[player]的眼睛是棕色的.", "[player]的头发是黑的.", "[player]有一头短发.", "[player]是浅肤色的.", "[player]有162厘米高.", "[player]惯用公制单位.", "[player]住在乡村.", "[player]住在内陆.", "[player]住在南半球.", "[player]属于ambivert社会人格.", "[player]不喜欢苏打水.", "[player]很少吃快餐.", "[player]平时喜欢运动.", "[player]还没有尝试过冥想.", "[player]还没有看过心理医生.", "[player]喜欢动漫作品.", "[player]不吸烟.", "[player]会开车.", "[player]正在考驾照.", "[player]参与过慈善捐赠.", "[player]觉得自己的家庭能够接受莫妮卡.", "[player]的学校没有毕业舞会.", "[player]希望自己在毕业舞会上做莫妮卡的舞伴.", "[player]还没有去过游乐园.", "[player]不喜欢旅游.", "[player]此前有过其他爱人.", "[player]曾遭遇过校园霸凌.", "[player]有一些朋友.", "[player]的生活很充实.", "[player]自己还没有车.", "[player]没有编程基础.", "[player]不喜欢诗歌.", "[player]喜欢桌游.", "[player]经常去健身.", "[player]性格中和.", "[player]喜欢接触自然.", "[player]从不说脏话.", "莫妮卡是[player]的女友.", "莫妮卡有一头珊瑚棕色的长发.", "莫妮卡有一个标志性的蝴蝶结发带.", "莫妮卡十分自信.", "莫妮卡擅长运动.", "莫妮卡是个成熟和努力的女孩.", "莫妮卡是一个非常体贴和善良的人, 总是为别人着想.", "莫妮卡常穿着黑色长袜和粉白相间的鞋子.", "莫妮卡的生日是9月22日.", "莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.", "莫妮卡一年中最喜欢的日子是情人节.", "莫妮卡最喜欢的季节是夏天", "莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.", "莫妮卡是女高中生, 她成绩优秀, 性格温柔.", "莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.", "莫妮卡爱好音乐, 会弹钢琴, 会唱歌.", "莫妮卡对科技, 环境, 历史等方面都有兴趣和见解."]'''

        messages = [{'role': 'system', 'content': system_init_test7}]
        messages_appending = [
            {'role': 'user', 'content': init_example1},
            {'role': 'assistant', 'content': 'NONE'},
            {'role': 'user', 'content': init_example2},
            {'role': 'assistant', 'content': '["[player]想过和莫妮卡去爬山.", "莫妮卡和[player]都喜欢雨."]'},
            {'role': 'user', 'content': init_example3},
            {'role': 'assistant', 'content': "NONE"},
            {'role': 'user', 'content': init_example4},
            {'role': 'assistant', 'content': '["莫妮卡和[player]还没有一起过万圣节.", "莫妮卡和[player]还没有一起过圣诞节.", "莫妮卡和[player]还没有一起过新年.", "莫妮卡还没有庆祝过[player]的生日."]'},
            {'role': 'user', 'content': init_example5},
            {'role': 'assistant', 'content': '["莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献."]'}

        ]
        #messages.extend(messages_appending)
        messages.append({'role': 'user', 'content': f'sentence: [{query}], information: {information}'})
        #messages.append({'role': 'user', 'content': query})
        resp = client.chat.completions.create(
            model=model_type,
            messages=messages,
            temperature=0.1,
            top_p = 0.6,
            presence_penalty = 0.0,
            frequency_penalty = 0.0,
            #stop=['<|endoftext|>'],
            seed=42)
        response = resp.choices[0].message.content
        print(f"MFocus searching persistent, response is:\n{response}\nEnd of MFocus searching persistent")
        answer_re = re.search(r'Answer\s*:\s*(\[.*\])', response, re.I)
        if answer_re:
            response = answer_re[1]
        else:
            success = False
            exception = 'No answer found in mfocus'
            response = ''
        return success, exception, response, response
    except Exception as excepted:
        success = False
        exception = excepted
        return success, exception, '', ''

"""
            {'role': 'user', 'content': init_example4},
            {'role': 'assistant', 'content': '["莫妮卡和[player]还没有一起过万圣节.", "莫妮卡和[player]还没有一起过圣诞节.", "莫妮卡和[player]还没有一起过新年.", "莫妮卡还没有庆祝过[player]的生日."]'}

            {'role': 'user', 'content': init_example5},
            {'role': 'assistant', 'content': '["莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献."]'}
"""

if __name__ == "__main__":
    print(mfocus_agent(23, 1, '你喜欢吃什么'))