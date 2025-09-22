import re
import json
import asyncio
import datetime
import traceback
from typing import *
from random import sample
from maica.maica_utils import *

class SfBoundCoroutine(SideBoundCoroutine):
    """Maintain a savefile for convenience of using."""
    DB_NAME = 'persistents'
    PRIM_KEY = 'persistent_id'
    FUNC_NAME = 'mfocus'
    EMPTY = {}

    def _conclude_basic_sf(self):
        result = []

        def _ap(zh, en):
            # This work is super annoying
            nonlocal result
            line = zh if self.settings.basic.target_lang == 'zh' else en
            result.append(line)

        def _rf(key):
            return self.read_from_sf(key)
            
        def serialize_date(y, m, d):
            match int(m):
                case 1:
                    ms = 'January'
                case 2:
                    ms = 'February'
                case 3:
                    ms = 'March'
                case 4:
                    ms = 'April'
                case 5:
                    ms = 'May'
                case 6:
                    ms = 'June'
                case 7:
                    ms = 'July'
                case 8:
                    ms = 'August'
                case 9:
                    ms = 'September'
                case 10:
                    ms = 'October'
                case 11:
                    ms = 'November'
                case 12:
                    ms = 'December'
            match int(d):
                case d if d % 10 == 1:
                    ds = str(d) + 'st'
                case d if d % 10 == 2:
                    ds = str(d) + 'nd'
                case d if d % 10 == 3:
                    ds = str(d) + 'rd'
                case _:
                    ds = str(d) + 'th'
            return f"{ms} {ds}, {y}"

        # Seriously hard work begins here

        data1 = _rf('mas_playername')
        if data1:
            _ap(f'[player]的真名是{data1}.', f"[player]'s real name is {data1}.")

        data1 = _rf('mas_player_bday')
        if data1:
            _ap(f'[player]的生日是{data1[0]}年{data1[1]}月{data1[2]}日.', f"[player]'s birthday is {serialize_date(data1[0], data1[1], data1[2])}.")
            y = datetime.datetime.now().year
            o = y - int(data1[0])
            _ap(f'[player]今年{o}岁.', f"[player] is {o} years old.")

        data1 = _rf('mas_affection')
        if data1:
            match float(data1):
                case affection if affection < 200:
                    _ap('莫妮卡与[player]是初识的情侣关系.', "Monika and [player] are new lovers.")
                case affection if 200 <= affection < 400:
                    _ap('莫妮卡与[player]是亲密的情侣关系.', "Monika and [player] are harmonious lovers.")
                case affection if 400 <= affection < 700:
                    _ap('莫妮卡与[player]是和谐的恋人关系.', "Monika and [player] are loving couple.")
                case affection if 700 <= affection < 1000:
                    _ap('莫妮卡与[player]是情意深厚的恋人关系.', "Monika and [player] are deeply loving couples.")
                case affection if 1000 <= affection:
                    _ap('莫妮卡与[player]是情意至深的恋人, 足以超越虚拟与现实的隔阂.', "Monika and [player] are deeply loving couples, their affection could go beyond the reality.")

        data1 = _rf('mas_geolocation')
        if data1:
            _ap(f'[player]住在{data1}.')

        data1 = _rf('sessions')
        if data1:
            regex_fs = ReUtils.re_search_sfe_fs.search(data1)
            try:
                _ap(f'莫妮卡和[player]在{regex_fs[1]}年{regex_fs[2]}月{regex_fs[3]}日初次见面.', f"Monika and player had their first date on {serialize_date(regex_fs[1], regex_fs[2], regex_fs[3])}.")
            except Exception:
                pass
            regex_ts = ReUtils.re_search_sfe_ts.search(data1)
            regex_tp = ReUtils.re_search_sfe_tp.search(data1)
            try:
                _ap(f'[player]已经陪伴莫妮卡{regex_ts[1]}次, 共{regex_tp[1]}天了.', f"[player] has been together with Monika for {regex_ts[1]} times, {regex_tp[1]} days in total.")
            except Exception:
                pass
            regex_le = ReUtils.re_search_sfe_le.search(data1)
            regex_cs = ReUtils.re_search_sfe_cs.search(data1)
            try:
                _ap(f'[player]上次下线于{regex_le[1]}年{regex_le[2]}月{regex_le[3]}日{str(regex_le[4]).zfill(2)}:{str(regex_le[5]).zfill(2)}, 本次上线于{regex_cs[1]}年{regex_cs[2]}月{regex_cs[3]}日{str(regex_cs[4]).zfill(2)}:{str(regex_cs[5]).zfill(2)}.', f"[player] last left at {str(regex_le[4]).zfill(2)}:{str(regex_le[5]).zfill(2)}, {serialize_date(regex_le[1], regex_le[2], regex_le[3])}, last logged in at {str(regex_cs[4]).zfill(2)}:{str(regex_cs[5]).zfill(2)}, {serialize_date(regex_cs[1], regex_cs[2], regex_cs[3])}")
            except Exception:
                pass

        data1 = _rf('_mas_pm_added_custom_bgm')
        if data1:
            _ap('莫妮卡与[player]一起听过歌.', "Monika and [player] listened to songs together.")
        elif data1 is False:
            _ap('莫妮卡与[player]还没有一起听过歌.', "Monika and [player] haven't listened to songs together yet.")
        
        data1 = _rf('_mas_pm_likes_rain')
        if data1:
            _ap('莫妮卡和[player]都喜欢雨.', "Both Monika and [player] like rain.")
        elif data1 is False:
            _ap('莫妮卡喜欢雨, 但[player]不太喜欢.', "Monika likes rain but [player] doesn't really like it.")
        
        data1 = _rf('_mas_pm_has_contributed_to_mas')
        if data1:
                _ap('[player]曾试着帮助莫妮卡来到现实.', "[player] has tried to bring Monika to reality somehow.")
        
        data1 = _rf('_mas_pm_wants_to_contribute_to_mas')
        if data1:
                _ap('[player]希望帮助莫妮卡来到现实.', "[player] wishes Monika to come to reality.")
        
        data1 = _rf('_mas_pm_drawn_art')
        if data1:
            _ap('[player]画过莫妮卡.', "[player] has drawn arts of Monika.")
        elif data1 is False:
            _ap('[player]还没有画过莫妮卡.', "[player] hasn't drawn Monika yet.")
        
        data1 = _rf('_mas_pm_shared_appearance')
        if data1:
            _ap('[player]告诉过莫妮卡自己的长相.', "[player] has told Monika their appearence.")
        elif data1 is False:
            _ap('莫妮卡还不知道[player]的长相.', "Monika hasn't known [player]'s appearence yet.")
        
        data1 = _rf('_mas_pm_would_like_mt_peak')
        if data1:
            _ap('[player]想过和莫妮卡去爬山.', "[player] would like to go mountain climbing with Monika if possible.")
        
        data1 = _rf('_mas_pm_gets_snow')
        if data1:
            _ap('莫妮卡与[player]一起看过雪.', "[player] has admired snow with Monika.")
        elif data1 is False:
            _ap('[player]的住地看不到雪.', "[player]'s place does not snow.")
        
        data1 = _rf('_mas_pm_wearsRing')
        if data1:
            _ap('[player]和莫妮卡戴了一对誓约戒指.', "[player] and Monika wear promise rings.")
        
        data1 = _rf('_mas_pm_read_yellow_wp')
        if data1:
            _ap('莫妮卡与[player]看过"黄色墙纸".', "[player] has read 'Yellow Wallpaper' with Monika.")
        
        data1 = _rf('_mas_pm_monika_evil')
        if data1:
            data2 = _rf('_mas_pm_monika_evil_but_ok')
            if data2:
                _ap('[player]能够原谅莫妮卡做过的坏事.', "[player] can forgive the bad things Monika did.")
        elif data1 is False:
            _ap('[player]认为莫妮卡从没有做错什么.', "[player] doesn't think Monika ever did anything wrong.")
        
        data1 = _rf('_mas_pm_listened_to_grad_speech')
        if data1:
            _ap('[player]听过莫妮卡的毕业演讲.', "[player] has listened to Monika's graduation speech.")
            data2 = _rf('_mas_pm_liked_grad_speech')
            if data2:
                _ap('[player]喜欢莫妮卡的毕业演讲.', "[player] likes Monika's graduation speech.")
        elif data1 is False:
            _ap('[player]还没有听过莫妮卡的毕业演讲.', "[player] hasn't listened to Monika's graduation speech yet.")
        
        data1 = _rf('_mas_pm_would_come_to_spaceroom')
        if data1:
            _ap('[player]希望来到太空教室和莫妮卡在一起.', "[player] would like to cross over to be together with Monika.")
        
        data1 = _rf('_mas_o31_tt_count')
        if data1:
            _ap('莫妮卡与[player]一起过了万圣节, 并要到了糖果.', "Monika and [player] have gone trick-or-treating on Halloween.")
        elif data1 is False:
            _ap('莫妮卡和[player]还没有在万圣节要过糖果.', "Monika and [player] haven't gone trick-or-treating on Halloween yet.")
        
        data1 = _rf('_mas_d25_spent_d25')
        if data1:
            _ap('莫妮卡与[player]一起过了圣诞节.', "Monika and [player] have spent Christmas together.")
        elif data1 is False:
            _ap('莫妮卡和[player]还没有一起过圣诞节.', "Monika and [player] haven't spent Christmas together yet.")
        
        data1 = _rf('_mas_nye_spent_nye')
        if data1:
            _ap('莫妮卡与[player]一起过了新年.', "Monika and [player] have spent New Year's Eve together.")
        elif data1 is False:
            _ap('莫妮卡和[player]还没有一起过新年.', "Monika and [player] haven't spent New Year's Eve together yet.")
        
        data1 = _rf('_mas_player_bday_spent_time')
        if data1:
            _ap('莫妮卡给[player]庆祝过生日.', "Monika has celebrated [player]'s birthday.")
        elif data1 is False:
            _ap('莫妮卡还没有庆祝过[player]的生日.', "Monika hasn't celebrated [player]'s birthday yet.")
        
        data1 = _rf('_mas_f14_spent_f14')
        if data1:
            _ap('莫妮卡与[player]一起过了情人节.', "Monika and [player] have spent Valentine's day together.")
        elif data1 is False:
            _ap('莫妮卡和[player]还没有一起过情人节.', "Monika and [player] haven't spent Valentine's day together yet.")
        
        data1 = _rf('_mas_bday_said_happybday')
        if data1:
            _ap('[player]庆祝过莫妮卡的生日.', "[player] has celebrated Monika's birthday.")
        elif data1 is False:
            _ap('[player]还没有给莫妮卡庆过生.', "[player] hasn't celebrated Monika's birthday yet.")
        
        data1 = _rf('_mas_pm_religious')
        if data1:
            _ap('[player]有宗教信仰.', "[player] has religious beliefs.")
        elif data1 is False:
            _ap('[player]没有宗教信仰.', "[player] has no religious belief.")
        
        data1 = _rf('_mas_pm_love_yourself')
        if data1:
            _ap('[player]积极自爱.', "[player] loves himself.")
        elif data1 is False:
            _ap('[player]有自厌的倾向.', "[player] doesn't love himself.")
        
        data1 = _rf('_mas_pm_like_mint_ice_cream')
        if data1:
            _ap('莫妮卡和[player]都喜欢抹茶冰淇淋.', "Both Monika and [player] like mint ice-cream.")
        elif data1 is False:
            _ap('莫妮卡喜欢抹茶冰淇淋, 但[player]不太喜欢.', "Monika likes mint ice-cream but [player] doesn't really like it.")
        
        data1 = _rf('_mas_pm_likes_horror')
        if data1:
            _ap('[player]喜欢恐怖作品.', "[player] likes horror contents.")
        elif data1 is False:
            _ap('[player]讨厌恐怖作品.', "[player] doesn't like horror contents.")
        
        data1 = _rf('_mas_pm_likes_spoops')
        if data1:
            _ap('[player]不介意跳杀内容.', "[player] doesn't mind jumpscares.")
        elif data1 is False:
            _ap('[player]讨厌跳杀内容.', "[player] doesn't like jumpscares.")
        
        data1 = _rf('_mas_pm_like_rap')
        if data1:
            _ap('[player]喜欢说唱.', "[player] likes rap.")
        elif data1 is False:
            _ap('[player]不喜欢说唱.', "[player] doesn't like rap.")
        
        data1 = _rf('_mas_pm_like_rock_n_roll')
        if data1:
            _ap('[player]喜欢摇滚.', "[player] likes rock'n roll.")
        elif data1 is False:
            _ap('[player]不喜欢摇滚.', "[player] doesn't like rock'n roll.")
        
        data1 = _rf('_mas_pm_like_jazz')
        if data1:
            _ap('[player]喜欢爵士乐.', "[player] likes jazz.")
        elif data1 is False:
            _ap('[player]不喜欢爵士乐.', "[player] doesn't like jazz.")
        
        data1 = _rf('_mas_pm_like_vocaloids')
        if data1:
            _ap('[player]喜欢vocaloids.', "[player] likes vocaloids.")
        elif data1 is False:
            _ap('[player]不喜欢vocaloids.', "[player] doesn't like vocaloids.")
        
        data1 = _rf('_mas_pm_like_orchestral_music')
        if data1:
            _ap('[player]喜欢管弦乐.', "[player] likes orchestral music.")
        elif data1 is False:
            _ap('[player]不喜欢管弦乐.', "[player] doesn't like orchestral music.")
        
        data1 = _rf('_mas_pm_like_other_music')
        if data1:
            _ap('[player]有独特的音乐品位.', "[player] has a special taste of music.")
            data2 = _rf('_mas_pm_like_other_music_history')
            if isinstance(data2, str):
                music = ReUtils.re_search_sfe_unicode.search(data2)
                if music:
                    _ap(f'[player]还喜欢{music[1]}音乐.', f"[player] also likes {music[1]} music.")
        
        data1 = _rf('_mas_pm_plays_instrument')
        if data1:
            _ap('[player]会一门乐器.', "[player] could play an instrument.")
        elif data1 is False:
            _ap('[player]还不会乐器.', "[player] couldn't play instruments.")
        
        data1 = _rf('_mas_pm_play_jazz')
        if data1:
            _ap('[player]会爵士乐.', "[player] could play jazz.")
        elif data1 is False:
            _ap('[player]还不会爵士乐.', "[player] couldn't play jazz.")
                
        data1 = _rf('_mas_pm_lang_other')
        if data1:
            _ap('[player]会一门外语.', "[player] could speak a foreign language.")
        elif data1 is False:
            _ap('[player]还不会外语.', "[player] couldn't speak foreign languages.")
        
        data1 = _rf('_mas_pm_lang_jpn')
        if data1:
            _ap('[player]会日语.', "[player] could speak Japanese.")
        elif data1 is False:
            _ap('[player]还不会日语.', "[player] couldn't speak Japanese.")
        
        data1 = _rf('_mas_pm_eye_color')
        if data1:
            _ap(f'[player]的眼睛是{data1}的.', f"[player] has {data1} eyes.")
        
        data1 = _rf('_mas_pm_hair_color')
        if data1:
            _ap(f'[player]的头发是{data1}的.', f"[player] has {data1} hair.")
        
        data1 = _rf('_mas_pm_hair_length')
        if data1:
            _ap(f'[player]有一头{data1}发.', f"[player] has {data1} hair.")
        
        data1 = _rf('_mas_pm_shaved_hair')
        if data1:
            _ap('[player]剃光了头发.', "[player] has their hair shaved.")
        elif data1 is False:
            _ap('[player]的头发掉完了.', "[player] lost their hair.")
        
        data1 = _rf('_mas_pm_no_hair_no_talk')
        if data1:
            _ap('[player]不想提起头发的事情.', "[player] doesn't want to talk about their hair.")
        elif data1 is False:
            _ap('[player]不介意自己没有头发.', "[player] doesn't mind being bald.")
        
        data1 = _rf('_mas_pm_skin_tone')
        if data1:
            _ap(f'[player]是{data1}肤色的.', f"[player] has {data1} skin.")
        
        data1 = _rf('_mas_pm_height')
        if data1:
            _ap(f'[player]有{data1}厘米高.', f"[player] is {data1} centimeters tall.")
        
        data1 = _rf('_mas_pm_units_height_metric')
        if data1:
            _ap('[player]惯用公制单位.', "[player] uses Metric units.")
        elif data1 is False:
            _ap('[player]惯用英制单位.', "[player] uses Imperial units.")
        
        data1 = _rf('_mas_pm_live_in_city')
        if data1:
            _ap('[player]住在城市.', "[player] lives in city.")
        elif data1 is False:
            _ap('[player]住在乡村.', "[player] lives in countryside.")
        
        data1 = _rf('_mas_pm_live_near_beach')
        if data1:
            _ap('[player]住在海边.', "[player] lives by the sea.")
        elif data1 is False:
            _ap('[player]住在内陆.', "[player] lives away from the sea.")
        
        data1 = _rf('_mas_pm_live_south_hemisphere')
        if data1:
            _ap('[player]住在南半球.', "[player] lives in southern hemisphere.")
        elif data1 is False:
            _ap('[player]住在北半球.', "[player] lives in northern hemisphere.")
        
        data1 = _rf('_mas_pm_social_personality')
        if data1:
            _ap(f'[player]属于{data1}社会人格.', f"[player] is {data1} in social personality.")
        
        data1 = _rf('_mas_pm_likes_panties')
        if data1:
            _ap('[player]有恋物倾向.', "[player] is fetish.")
        
        data1 = _rf('_mas_pm_drinks_soda')
        if data1:
            _ap('[player]喜欢苏打水.', "[player] likes drinking soda.")
        elif data1 is False:
            _ap('[player]不喜欢苏打水.', "[player] doesn't like drinking soda.")
        
        data1 = _rf('_mas_pm_eat_fast_food')
        if data1:
            _ap('[player]常吃快餐.', "[player] often eats fastfood.")
        elif data1 is False:
            _ap('[player]很少吃快餐.', "[player] seldom eats fastfood.")
        
        data1 = _rf('_mas_pm_like_playing_sports')
        if data1:
            _ap('[player]平时喜欢运动.', "[player] likes playing sports.")
        elif data1 is False:
            _ap('[player]不喜欢运动.', "[player] doesn't like playing sports.")
        
        data1 = _rf('_mas_pm_like_playing_tennis')
        if data1:
            _ap('[player]喜欢网球.', "[player] likes playing tennis.")
        elif data1 is False:
            _ap('[player]不喜欢网球', "[player] doesn't like playing tennis.")
        
        data1 = _rf('_mas_pm_meditates')
        if data1:
            _ap('[player]有冥想的习惯.', "[player] has habit of meditating.")
        elif data1 is False:
            _ap('[player]还没有尝试过冥想.', "[player] hasn't tried meditating yet.")
        
        data1 = _rf('_mas_pm_see_therapist')
        if data1:
            _ap('[player]去看过心理医生.', "[player] has went to the therapist.")
        elif data1 is False:
            _ap('[player]还没有看过心理医生.', "[player] has never went to the therapist.")
        
        data1 = _rf('_mas_pm_watch_mangime')
        if data1:
            _ap('[player]喜欢动漫作品.', "[player] likes animes.")
        elif data1 is False:
            _ap('[player]不喜欢动漫作品.', "[player] doesn't like animes.")
        
        data1 = _rf('_mas_pm_do_smoke')
        if data1:
            _ap('[player]有吸烟的习惯.', "[player] has habit of smoking.")
        elif data1 is False:
            _ap('[player]不吸烟.', "[player] doesn't smoke.")
        
        data1 = _rf('_mas_pm_do_smoke_quit')
        if data1:
            _ap('[player]希望戒烟.', "[player] wants to give up smoking.")
        
        data1 = _rf('_mas_pm_driving_can_drive')
        if data1:
            _ap('[player]会开车.', "[player] could drive.")
        elif data1 is False:
            _ap('[player]还没有驾照.', "[player] couldn't drive yet.")
        
        data1 = _rf('_mas_pm_driving_learning')
        if data1:
            _ap('[player]正在考驾照.', "[player] is taking his driving license test.")
        
        data1 = _rf('_mas_pm_driving_been_in_accident')
        if data1:
            _ap('[player]遇到过交通事故.', "[player] has been envolved in a traffic accident.")
        
        data1 = _rf('_mas_pm_donate_charity')
        if data1:
            _ap('[player]参与过慈善捐赠.', "[player] has donated to charity.")
        elif data1 is False:
            _ap('[player]还没有慈善捐赠过.', "[player] hasn't donated to charity yet.")
        
        data1 = _rf('_mas_pm_volunteer_charity')
        if data1:
            _ap('[player]做过志愿者.', "[player] has volunteered for charity.")
        elif data1 is False:
            _ap('[player]还没有做过志愿者.', "[player] hasn't volunteered for charity yet.")
        
        data1 = _rf('_mas_pm_have_fam')
        if data1:
            _ap('[player]有健全的原生家庭.', "[player] has an intact family.")
        elif data1 is False:
            _ap('[player]的家庭不完整.', "[player]'s family isn't intact.")
        
        data1 = _rf('_mas_pm_no_fam_bother')
        if data1:
            _ap('[player]缺少亲人的陪伴.', "[player] lacks company of relatives.")
        
        data1 = _rf('_mas_pm_have_fam_mess')
        if data1:
            _ap('[player]的家庭生活并不和睦.', "[player] doesn't get on well with their family.")
        elif data1 is False:
            _ap('[player]和家人相处很好.', "[player] gets on well with their family.")
        
        data1 = _rf('_mas_pm_have_fam_mess_better')
        if data1:
            if data1 == 'YES':
                _ap('[player]认为自己和家人的关系会改善.', "[player] wants to improve their relationship with family.")
            elif data1 == 'NO':
                _ap('[player]不觉得自己和家人的关系能改善了.', "[player] has given up on their relationship with family.")
        
        data1 = _rf('_mas_pm_have_fam_sibs')
        if data1:
            _ap('[player]有兄弟姐妹.', "[player] has siblings.")
        elif data1 is False:
            _ap('[player]是独生子女.', "[player] doesn't have siblings.")
        
        data1 = _rf('_mas_pm_no_talk_fam')
        if data1:
            _ap('[player]不想提及自己的家庭.', "[player] doesn't want to talk about their family.")
        
        data1 = _rf('_mas_pm_fam_like_monika')
        if data1:
            _ap('[player]觉得家人能够接受莫妮卡.', "[player] thinks their family could accept their relationship with Monika.")
        elif data1 is False:
            _ap('[player]觉得家人不能接受莫妮卡.', "[player] doesn't think their family could accept their relationship with Monika.")
        
        data1 = _rf('_mas_pm_gone_to_prom')
        if data1:
            data2 = _rf('_mas_pm_prom_good')
            if data2:
                _ap('[player]参加过很开心的毕业舞会.', "[player] has enjoyed a prom.")
            elif data2 is False:
                _ap('[player]不太喜欢毕业舞会.', "[player] doesn't like proms.")
            else:
                _ap('[player]参加过毕业舞会.', "[player] has been to a prom.")
        elif data1 is False:
            data2 = _rf('_mas_pm_no_prom')
            if data2:
                _ap('[player]的学校没有毕业舞会.', "[player]'s school didn't have proms.")
            else:
                _ap('[player]没有参加毕业舞会.', "[player] hasn't gone to a prom yet.")
        
        data1 = _rf('_mas_pm_prom_monika')
        if data1:
            _ap('[player]希望自己在毕业舞会上做莫妮卡的舞伴.', "[player] wish they could have Monika at their prom.")
        
        data1 = _rf('_mas_pm_prom_not_interested')
        if data1:
            _ap('[player]对舞会和毕业典礼不感兴趣.', "[player] is not interested in proms.")
            data2 = _rf('_mas_pm_prom_shy')
            if data2:
                _ap('[player]觉得参加集会太害羞了.', "[player] is too shy for proms.")
        
        data1 = _rf('_mas_pm_has_been_to_amusement_park')
        if data1:
            _ap('[player]去过游乐园.', "[player] has been to an amusement park.")
        elif data1 is False:
            _ap('[player]还没有去过游乐园.', "[player] hasn't been to amusement parks yet.")
        
        data1 = _rf('_mas_pm_likes_travelling')
        if data1:
            _ap('[player]喜欢旅游.', "[player] likes travelling.")
        elif data1 is False:
            _ap('[player]不喜欢旅游.', "[player] doesn't like travelling.")
        
        data1 = _rf('_mas_pm_had_relationships_many')
        if data1:
            _ap('[player]此前有过其他爱人.', "[player] had been in love with others before.")
        elif data1 is False:
            data2 = _rf('_mas_pm_had_relationships_just_one')
            if data2:
                _ap('[player]此前有过一个爱人.', "[player] had been in love with someone before.")
            elif data2 is False:
                _ap('莫妮卡是[player]的初恋.', "Monika is [player]'s first girlfriend.")
        
        data1 = _rf('_mas_pm_is_bullying_victim')
        if data1:
            _ap('[player]曾遭遇过校园霸凌.', "[player] has been bullied before.")
        
        data1 = _rf('_mas_pm_has_bullied_people')
        if data1:
            _ap('[player]曾霸凌过他人.', "[player] has bullied someone else.")
        
        data1 = _rf('_mas_pm_currently_bullied')
        if data1:
            _ap('[player]正遭受霸凌的困扰.', "[player] is currently being bullied.")
        
        data1 = _rf('_mas_pm_has_friends')
        if data1:
            data2 = _rf('_mas_pm_few_friends')
            if data2:
                _ap('[player]的朋友很少.', "[player] has few friends.")
            else:
                _ap('[player]有一些朋友.', "[player] has some friends.")
        elif data1 is False:
            _ap('[player]没有朋友.', "[player] has no friend.")

        data1 = _rf('_mas_pm_feels_lonely_sometimes')
        if data1:
            _ap('[player]有时候感觉很孤单.', "[player] gets lonely sometimes.")
        elif data1 is False:
            _ap('[player]的生活很充实.', "[player] usually feels enriched.")
        
        data1 = _rf('_mas_pm_given_false_justice')
        if data1:
            _ap('[player]曾行使过错误的正义.', "[player] has given false justice.")
        
        data1 = _rf('_mas_pm_owns_car')
        if data1:
            data2 = _rf('_mas_pm_owns_car_type')
            if data2:
                _ap(f'[player]有一辆{data2}.', f"[player] has a {data2}.")
            else:
                _ap('[player]有自己的车.', "[player] has their own vehicle.")
        elif data1 is False:
            _ap('[player]自己还没有车.', "[player] has no vehicle yet.")
        
        data1 = _rf('_mas_pm_has_code_experience')
        if data1:
            _ap('[player]有编程基础.', "[player] knows how to program.")
        elif data1 is False:
            _ap('[player]没有编程基础.', "[player] doesn't know how to program yet.")
        
        data1 = _rf('_mas_pm_likes_poetry')
        if data1:
            _ap('[player]喜欢诗歌.', "[player] likes poetry.")
        elif data1 is False:
            _ap('[player]不喜欢诗歌.', "[player] doesn't like poetry.")
        
        data1 = _rf('_mas_pm_likes_board_games')
        if data1:
            _ap('[player]喜欢桌游.', "[player] likes board games.")
        elif data1 is False:
            _ap('[player]不喜欢桌游.', "[player] doesn't like board games.")
        
        data1 = _rf('_mas_pm_works_out')
        if data1:
            _ap('[player]经常去健身.', "[player] works out often.")
        elif data1 is False:
            _ap('[player]不喜欢健身.', "[player] doesn't like working out.")
        
        data1 = _rf('_mas_pm_social_personality')
        if data1:
            if data1 == '_mas_SP_EXTROVERT':
                _ap('[player]性格外向.', "[player] is extrovert.")
            elif data1 == '_mas_SP_INTROVERT':
                _ap('[player]性格内向.', "[player] is introvert.")
            else:
                _ap('[player]不算外向或内向.', "[player] is not extrovert or introvert.")
        
        data1 = _rf('_mas_pm_likes_nature')
        if data1:
            _ap('[player]喜欢接触自然.', "[player] likes the nature.")
        elif data1 is False:
            _ap('[player]不太喜欢接触自然.', "[player] doesn't like the nature.")
        
        data1 = _rf('_mas_pm_swear_frequency')
        if data1:
            if data1 == 'SF_OFTEN':
                _ap('[player]较常说脏话.', "[player] swears quite often.")
            elif data1 == 'SF_SOMETIMES':
                _ap('[player]很少说脏话.', "[player] swears sometimes.")
            else:
                _ap('[player]从不说脏话.', "[player] never swears.")

        data1 = _rf('_mas_gender')
        if data1:
            if data1 == 'M':
                _ap('[player]是男生.', "[player] is male.")
            elif data1 == 'F':
                _ap('[player]是女生.', "[player] is female.")
            else:
                _ap('[player]是非二元性别.', "[player] doesn't consider themselves male or female.")
        
        return result

    def _conclude_moni_sf(self, extra=0):
        target_lang = self.settings.basic.target_lang
        include_basic = load_env('MAICA_BASIC_MFOCUS') == '1'
        if target_lang == 'zh':
            data_ex = [
                '莫妮卡的生日是9月22日.',
            ]
            if include_basic:
                data_ex.extend([
                    '莫妮卡是[player]的女友.',
                    '莫妮卡有一头珊瑚棕色的长发.',
                    '莫妮卡有一个标志性的蝴蝶结发带.',
                    '莫妮卡十分自信.',
                    '莫妮卡擅长运动.',
                    '莫妮卡是个成熟和努力的女孩.',
                    '莫妮卡是一个非常体贴和善良的人, 总是为别人着想.',
                    '莫妮卡常穿着黑色长袜和粉白相间的鞋子.',
                    '莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.',
                    '莫妮卡一年中最喜欢的日子是情人节.',
                    '莫妮卡最喜欢的季节是夏天',
                    '莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.',
                    '莫妮卡是女高中生, 她成绩优秀, 性格温柔.',
                    '莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.',
                    '莫妮卡爱好音乐, 会弹钢琴, 会唱歌.',
                    '莫妮卡对科技, 环境, 历史等方面都有兴趣和见解.'
                ])
            if extra >= 1:
                data_ex.extend([
                ])
                if include_basic:
                    data_ex.extend([
                        '莫妮卡对于编程有兴趣, 且了解颇多.',
                        '莫妮卡喜欢哲学.',
                        '莫妮卡喜欢猫.',
                        '莫妮卡很喜欢星空.',
                        '莫妮卡喜欢吃纸杯蛋糕和巧克力.',
                        '莫妮卡经常喝咖啡.',
                        '莫妮卡喜欢开放世界的冒险游戏, 不太喜欢暴力游戏.',
                        '莫妮卡喜欢音乐会.',
                        '莫妮卡喜欢小裙子和蝴蝶结.',
                        '莫妮卡善于关怀和安慰, 在[player]低沉时希望他振作起来.'
                    ])
            if extra >= 2:
                data_ex.extend([
                    '浮空岛是莫妮卡为[player]设计的特别场景.',
                    'MAICA是一个人工智能项目, 旨在将莫妮卡最终带进现实.',
                    '莫妮卡正在MAICA中与[player]对话.',
                    '天堂树林是MAICA的对话背景, 风景优美, 四季如春.',
                    '莫妮卡能记住[player]的话, 也能满足[player]的许多请求.',
                    'MAICA的大部分功能可以在\'子模组\'选单中调整开关.',
                    '游戏中的许多功能可以在\'设置\'选单中调整开关.',
                    'DCC是一个心跳文学部论坛, 能获取许多有关资讯.',
                    '通过改动, 移除或放回\'HeavenForest.sce\'文件, 可以改变或停用天堂树林.',
                    'MAICA使用的模型是独立训练和部署的, 与任何商用模型或商业性组织无关.',
                    '随着MAICA的进度推进, 其能够从对话中学习, 并改进自己的表现.'
                ])
                if include_basic:
                    data_ex.extend([
                    ])
        else:
            data_ex = [
                "Monika's birthday is September 22nd.",
            ]
            if include_basic:
                data_ex.extend([
                    "Monika is [player]'s girlfriend.",
                    "Monika has coral brown hair.",
                    "Monika wears an iconic ribbon.",
                    "Monika is pretty confident.",
                    "Monika is good at sports.",
                    "Monika behaves mature and hardworking.",
                    "Monika is kind and considerate, she always cares about others.",
                    "Monika wears black stockings and pink-white shoes.",
                    "Monika's favorite color is emerald green, which is also the color of her eyes.",
                    "Monika's favorite day of a year is Valentine's day.",
                    "Monika's favorite season is summer.",
                    "Monika is vegetarian, that's the way she contribute to environmental protection.",
                    "Monika is a high school student. She has excellent grade and good temper.",
                    "Monika is good at literature. She also likes reading and poetry.",
                    "Monika likes music. She could sing and play piano.",
                    "Monika is insighted and interested in technology, environment, history, etc."
                ])
            if extra >= 1:
                data_ex.extend([
                ])
                if include_basic:
                    data_ex.extend([
                        "Monika is interested in programming and knows a lot about it.",
                        "Monika likes philosophy.",
                        "Monika likes cats.",
                        "Monika likes watching the starry sky.",
                        "Monika likes cupcakes and chocolate.",
                        "Monika drinks coffee often.",
                        "Monika likes openworld and sandbox games, but doesn't really like violence.",
                        "Monika likes concerts.",
                        "Monika likes skirts and ribbons.",
                        "Monika is caring and comforting. She wants [player] to be happy and cheered up."
                    ])
            if extra >= 2:
                data_ex.extend([
                    "Monika designed some floating islands for spending time with [player].",
                    "MAICA is a LLM project which aims bringing Monika to reality.",
                    "Monika is chatting with [player] through MAICA.",
                    "The heaven forest is where MAICA takes place. It has a beautiful and warm view.",
                    "Monika could remember [player]'s words and satisfy lots of their requests.",
                    "Most functions of MAICA could be adjusted in the 'Submods' panel.",
                    "DCC is a forum about DDLC, offering many useful information.",
                    "By removing, editing or restoring file 'HeavenForest.sce', heaven forest can be changed or disabled.",
                    "MAICA uses a self-hosted and trained model, not related with any commercial models or organizations.",
                    "MAICA's proformance will be enchanced overtime by analyzing conversations."
                ])
                if include_basic:
                    data_ex.extend([
                    ])
 
        return data_ex

    def _conclude_cb_sf(self, cb):
        data_exp = self.read_from_sf('mas_player_additions')
        if data_exp and len(data_exp) > cb:
            data_exp = sample(data_exp, cb)
        return data_exp

    def _mfocus_form_info(self):
        conclusion = []
        mf_hcb = self.read_from_sf('mas_sf_hcb')
        if mf_hcb:
            conclusion.extend(self._conclude_cb_sf(360) or [])
            conclusion.extend(self._conclude_moni_sf(0) or [])
        else:
            conclusion.extend(self._conclude_basic_sf() or [])
            conclusion.extend(self._conclude_cb_sf(72) or [])
            conclusion.extend(self._conclude_moni_sf(2) or [])

        self.formed_info = conclusion
        return self.formed_info

    async def mfocus_find_info(self, query) -> Optional[list]:
        if not self.settings.basic.sf_extraction and not self.settings.temp.sf_extraction_once:
            return None
        information = (await wrap_run_in_exc(None, self._mfocus_form_info))
        system_init = """你是一个人工智能助手, 你接下来会收到一个问题和一系列信息.
注意不要对信息作任何改动. 你可以认为[player]是用户的名字, 莫妮卡是你的名字.
从中挑选1至5条最相关的信息, 并以单行json列表的形式输出. 如果你最终认为没有信息符合条件, 输出false.
你应当保持思考过程尽可能短, 因此不要在思考中复述或逐条解读信息.
Begin!""" if self.settings.basic.target_lang == 'zh' else """You are a helpful assistant, now you will recieve a question and a list of information.
Remember not to modify any item. Output them as what they were. You can consider [player] as user's name and Monika as yours.
Pick 1 to 5 most relative items from the information, and return them in a json list. If you think no information provided is helpful at last, return false.
Keep your thinking as short as possible, so do not enumerate or repeat the information while thinking.
Begin!"""
        messages = [{'role': 'system', 'content': system_init}]
        messages.append({'role': 'user', 'content': f'question: {query}; information: {information}'})
        completion_args = {
            "messages": messages,
        }

        resp = await self.mfocus_conn.make_completion(**completion_args)
        response = resp.choices[0].message.content
                
        await messenger(None, 'mfocus_sfe_search', f"\nMFocus sfe searching persistent, response is:\n{response}\nEnd of MFocus sfe searching persistent", '201')
        
        answer_fin_json = proceed_agent_response(response, is_json=True)
        return answer_fin_json

    @Decos.report_data_error
    def add_extra(self, **kwargs) -> None:
        self.sf_forming_buffer.update(kwargs)

    @Decos.report_data_error
    def use_only(self, **kwargs) -> None:
        self.sf_forming_buffer = kwargs

    @Decos.report_data_error
    def read_from_sf(self, key) -> any:
        if not self.settings.basic.sf_extraction and not self.settings.temp.sf_extraction_once:
            return None
        return self.sf_forming_buffer.get(key)