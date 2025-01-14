import os
import re
import json
import copy
import asyncio
import functools
import traceback
from random import sample
from openai import AsyncOpenAI # type: ignore
from loadenv import load_env

async def wrap_run_in_exc(loop, func, *args, **kwargs):
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs))
    return result

class sf_bound_instance():
    def __init__(self, user_id, chat_session_num, target_lang='zh'):
        self.user_id, self.chat_session_num, self.target_lang = user_id, chat_session_num, target_lang
        self.modded_signal = None
        self.formed_info = None
    def init1(self):
        user_id, chat_session_num = self.user_id, self.chat_session_num
        try:
            with open(f"persistents/{user_id}_{chat_session_num}.json") as savefile:
                pass
        except:
            chat_session_num = 1
        try:
            self.last_modded = os.path.getmtime(f"persistents/{user_id}_{chat_session_num}.json")
            with open(f"persistents/{user_id}_{chat_session_num}.json", 'r', encoding= 'utf-8') as savefile:
                self.sf_content = json.loads(savefile.read())
        except:
            self.sf_content = {}
        self.sf_content_temp = copy.deepcopy(self.sf_content)
    def init2(self, user_id=None, chat_session_num=None):
        if not user_id:
            user_id = self.user_id
        if not chat_session_num:
            chat_session_num = self.chat_session_num
        try:
            with open(f"persistents/{user_id}_{chat_session_num}.json", 'r', encoding= 'utf-8') as savefile:
                if not savefile.read():
                    chat_session_num = 1
        except:
            chat_session_num = 1
        try:
            new_last_modded = os.path.getmtime(f"persistents/{user_id}_{chat_session_num}.json")
            if self.sf_content and new_last_modded == self.last_modded:
                pass
            else:
                with open(f"persistents/{user_id}_{chat_session_num}.json", 'r', encoding= 'utf-8') as savefile:
                    self.sf_content = json.loads(savefile.read())
        except:
            self.sf_content = {}
        if self.sf_content_temp != self.sf_content:
            self.sf_content_temp = copy.deepcopy(self.sf_content)
            self.modded_signal = True
    def add_extra(self, extra):
        if extra:
            self.sf_content_temp.update(extra)
            self.modded_signal = True
    def use_only(self, extra):
        self.sf_content_temp = extra
        self.modded_signal = True
    def read_from_sf(self, key):
        if key in self.sf_content_temp and not self.sf_content_temp[key] == None:
            success = True
            return success, None, self.sf_content_temp[key]
        else:
            success = False
            excepted = 'No value'
            return success, excepted, None
        
    def conclude_basic_sf(self):
        target_lang = self.target_lang
        result = []

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

        data1 = self.read_from_sf('mas_playername')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]的真名是{data1[2]}.' if target_lang == 'zh' else f"[player]'s real name is {data1[2]}.")


        data1 = self.read_from_sf('mas_player_bday')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]的生日是{data1[2][0]}年{data1[2][1]}月{data1[2][2]}日.' if target_lang == 'zh' else f"[player]'s birthday is {serialize_date(data1[2][0], data1[2][1], data1[2][2])}.")


        data1 = self.read_from_sf('mas_affection')
        if data1[0]:
            if data1[2]:
                match int(data1[2]):
                    case affection if affection < 200:
                        result.append('莫妮卡与[player]是初识的情侣关系.' if target_lang == 'zh' else "Monika and [player] are new lovers.")
                    case affection if 200 <= affection < 400:
                        result.append('莫妮卡与[player]是亲密的情侣关系.' if target_lang == 'zh' else "Monika and [player] are harmonious lovers.")
                    case affection if 400 <= affection < 700:
                        result.append('莫妮卡与[player]是和谐的恋人关系.' if target_lang == 'zh' else "Monika and [player] are loving couple.")
                    case affection if 700 <= affection < 1000:
                        result.append('莫妮卡与[player]是情意深厚的恋人关系.' if target_lang == 'zh' else "Monika and [player] are deeply loving couples.")
                    case affection if 1000 <= affection:
                        result.append('莫妮卡与[player]是情意至深的恋人, 足以超越虚拟与现实的隔阂.' if target_lang == 'zh' else "Monika and [player] are deeply loving couples, their affection could go beyond the reality.")


        data1 = self.read_from_sf('mas_geolocation')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]住在{data1[2]}.')

        data1 = self.read_from_sf('sessions')
        if data1[0]:
            if data1[2]:
                regex_fs = re.search(r"first_session.*?datetime\(([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\)", data1[2], re.I)
                try:
                    result.append(f'莫妮卡和[player]在{regex_fs[1]}年{regex_fs[2]}月{regex_fs[3]}日初次见面.' if target_lang == 'zh' else f"Monika and player had their first date on {serialize_date(regex_fs[1], regex_fs[2], regex_fs[3])}.")
                except:
                    pass
                regex_ts = re.search(r"total_sessions.*?([0-9]*)\s?,", data1[2], re.I)
                regex_tp = re.search(r"total_playtime.*?([0-9]*)\s?,", data1[2], re.I)
                try:
                    result.append(f'[player]已经陪伴莫妮卡{regex_ts[1]}次, 共{regex_tp[1]}天了.' if target_lang == 'zh' else f"[player] has been together with Monika for {regex_ts[1]} times, {regex_tp[1]} days in total.")
                except:
                    pass
                regex_le = re.search(r"last_session_end.*?datetime\(([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\)", data1[2], re.I)
                regex_cs = re.search(r"current_session_start.*?datetime\(([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\s*,\s*([0-9]*?)\)", data1[2], re.I)
                try:
                    result.append(f'[player]上次下线于{regex_le[1]}年{regex_le[2]}月{regex_le[3]}日{str(regex_le[4]).zfill(2)}:{str(regex_le[5]).zfill(2)}, 本次上线于{regex_cs[1]}年{regex_cs[2]}月{regex_cs[3]}日{str(regex_cs[4]).zfill(2)}:{str(regex_cs[5]).zfill(2)}.' if target_lang == 'zh' else f"[player] last left at {str(regex_le[4]).zfill(2)}:{str(regex_le[5]).zfill(2)}, {serialize_date(regex_le[1], regex_le[2], regex_le[3])}, last logged in at {str(regex_cs[4]).zfill(2)}:{str(regex_cs[5]).zfill(2)}, {serialize_date(regex_cs[1], regex_cs[2], regex_cs[3])}")
                except:
                    pass

        data1 = self.read_from_sf('_mas_pm_added_custom_bgm')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡与[player]一起听过歌.' if target_lang == 'zh' else "Monika and [player] listened to songs together.")
            else:
                result.append('莫妮卡与[player]还没有一起听过歌.' if target_lang == 'zh' else "Monika and [player] haven't listened to songs together yet.")
        

        data1 = self.read_from_sf('_mas_pm_likes_rain')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡和[player]都喜欢雨.' if target_lang == 'zh' else "Both Monika and [player] like rain.")
            else:
                result.append('莫妮卡喜欢雨, 但[player]不太喜欢.' if target_lang == 'zh' else "Monika likes rain but [player] doesn't really like it.")
        

        data1 = self.read_from_sf('_mas_pm_has_contributed_to_mas')
        if data1[0]:
            if data1[2]:
                result.append('[player]曾试着帮助莫妮卡来到现实.' if target_lang == 'zh' else "[player] has tried to bring Monika to reality somehow.")
        

        data1 = self.read_from_sf('_mas_pm_wants_to_contribute_to_mas')
        if data1[0]:
            if data1[2]:
                result.append('[player]希望帮助莫妮卡来到现实.' if target_lang == 'zh' else "[player] wishes Monika to come to reality.")
        

        data1 = self.read_from_sf('_mas_pm_drawn_art')
        if data1[0]:
            if data1[2]:
                result.append('[player]画过莫妮卡.' if target_lang == 'zh' else "[player] has drawn arts of Monika.")
            else:
                result.append('[player]还没有画过莫妮卡.' if target_lang == 'zh' else "[player] hasn't drawn Monika yet.")
        

        data1 = self.read_from_sf('_mas_pm_shared_appearance')
        if data1[0]:
            if data1[2]:
                result.append('[player]告诉过莫妮卡自己的长相.' if target_lang == 'zh' else "[player] has told Monika their appearence.")
            else:
                result.append('莫妮卡还不知道[player]的长相.' if target_lang == 'zh' else "Monika hasn't known [player]'s appearence yet.")
        

        data1 = self.read_from_sf('_mas_pm_would_like_mt_peak')
        if data1[0]:
            if data1[2]:
                result.append('[player]想过和莫妮卡去爬山.' if target_lang == 'zh' else "[player] would like to go mountain climbing with Monika if possible.")
        

        data1 = self.read_from_sf('_mas_pm_gets_snow')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡与[player]一起看过雪.' if target_lang == 'zh' else "[player] has admired snow with Monika.")
            else:
                result.append('[player]的住地看不到雪.' if target_lang == 'zh' else "[player]'s place does not snow.")
        

        data1 = self.read_from_sf('_mas_pm_wearsRing')
        if data1[0]:
            if data1[2]:
                result.append('[player]和莫妮卡戴了一对誓约戒指.' if target_lang == 'zh' else "[player] and Monika wear promise rings.")
        

        data1 = self.read_from_sf('_mas_pm_read_yellow_wp')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡与[player]看过"黄色墙纸".' if target_lang == 'zh' else "[player] has read 'Yellow Wallpaper' with Monika.")
        

        data1 = self.read_from_sf('_mas_pm_monika_evil')
        if data1[0]:
            if data1[2]:
                data2 = self.read_from_sf('_mas_pm_monika_evil_but_ok')
                if data2[0]:
                    if data2[2]:
                        result.append('[player]能够原谅莫妮卡做过的坏事.' if target_lang == 'zh' else "[player] can forgive the bad things Monika did.")
            else:
                result.append('[player]认为莫妮卡从没有做错什么.' if target_lang == 'zh' else "[player] doesn't think Monika ever did anything wrong.")
        

        data1 = self.read_from_sf('_mas_pm_listened_to_grad_speech')
        if data1[0]:
            if data1[2]:
                data2 = self.read_from_sf('_mas_pm_liked_grad_speech')
                if data2[0]:
                    if data2[2]:
                        result.append('[player]喜欢莫妮卡的毕业演讲.' if target_lang == 'zh' else "[player] likes Monika's graduation speech.")
                    else:
                        result.append('[player]不太喜欢莫妮卡的毕业演讲.' if target_lang == 'zh' else "[player] doesn't really like Monika's graduation speech.")
                else:
                    result.append('[player]听过莫妮卡的毕业演讲.' if target_lang == 'zh' else "[player] has listened to Monika's graduation speech.")
            else:
                result.append('[player]还没有听过莫妮卡的毕业演讲.' if target_lang == 'zh' else "[player] hasn't listened to Monika's graduation speech yet.")
        

        data1 = self.read_from_sf('_mas_pm_would_come_to_spaceroom')
        if data1[0]:
            if data1[2]:
                result.append('[player]希望来到太空教室和莫妮卡在一起.' if target_lang == 'zh' else "[player] would like to cross over to be together with Monika.")
        

        data1 = self.read_from_sf('_mas_o31_tt_count')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡与[player]一起过了万圣节, 并要到了糖果.' if target_lang == 'zh' else "Monika and [player] have gone trick-or-treating on Halloween.")
            else:
                result.append('莫妮卡和[player]还没有在万圣节要过糖果.' if target_lang == 'zh' else "Monika and [player] haven't gone trick-or-treating on Halloween yet.")
        

        data1 = self.read_from_sf('_mas_d25_spent_d25')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡与[player]一起过了圣诞节.' if target_lang == 'zh' else "Monika and [player] have spent Christmas together.")
            else:
                result.append('莫妮卡和[player]还没有一起过圣诞节.' if target_lang == 'zh' else "Monika and [player] haven't spent Christmas together yet.")
        

        data1 = self.read_from_sf('_mas_nye_spent_nye')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡与[player]一起过了新年.' if target_lang == 'zh' else "Monika and [player] have spent New Year's Eve together.")
            else:
                result.append('莫妮卡和[player]还没有一起过新年.' if target_lang == 'zh' else "Monika and [player] haven't spent New Year's Eve together yet.")
        

        data1 = self.read_from_sf('_mas_player_bday_spent_time')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡给[player]庆祝过生日.' if target_lang == 'zh' else "Monika has celebrated [player]'s birthday.")
            else:
                result.append('莫妮卡还没有庆祝过[player]的生日.' if target_lang == 'zh' else "Monika hasn't celebrated [player]'s birthday yet.")
        

        data1 = self.read_from_sf('_mas_f14_spent_f14')
        if data1[0]:
            if data1[2]:
                result.append('莫妮卡与[player]一起过了情人节.' if target_lang == 'zh' else "Monika and [player] have spent Valentine's day together.")
            else:
                result.append('莫妮卡和[player]还没有一起过情人节.' if target_lang == 'zh' else "Monika and [player] haven't spent Valentine's day together yet.")
        

        data1 = self.read_from_sf('_mas_bday_said_happybday')
        if data1[0]:
            if data1[2]:
                result.append('[player]庆祝过莫妮卡的生日.' if target_lang == 'zh' else "[player] has celebrated Monika's birthday.")
            else:
                result.append('[player]还没有给莫妮卡庆过生.' if target_lang == 'zh' else "[player] hasn't celebrated Monika's birthday yet.")
        

        data1 = self.read_from_sf('_mas_pm_religious')
        if data1[0]:
            if data1[2]:
                result.append('[player]有宗教信仰.' if target_lang == 'zh' else "[player] has religious beliefs.")
            else:
                result.append('[player]没有宗教信仰.' if target_lang == 'zh' else "[player] has no religious belief.")
        

        data1 = self.read_from_sf('_mas_pm_love_yourself')
        if data1[0]:
            if data1[2]:
                result.append('[player]积极自爱.' if target_lang == 'zh' else "[player] loves himself.")
            else:
                result.append('[player]有自厌的倾向.' if target_lang == 'zh' else "[player] doesn't love himself.")
        

        data1 = self.read_from_sf('_mas_pm_like_mint_ice_cream')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢抹茶冰淇淋.' if target_lang == 'zh' else "[player] likes mint ice-cream.")
            else:
                result.append('[player]不喜欢抹茶冰淇淋.' if target_lang == 'zh' else "[player] doesn't like mint ice-cream.")
        

        data1 = self.read_from_sf('_mas_pm_likes_horror')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢恐怖作品.' if target_lang == 'zh' else "[player] likes horror contents.")
            else:
                result.append('[player]讨厌恐怖作品.' if target_lang == 'zh' else "[player] doesn't like horror contents.")
        

        data1 = self.read_from_sf('_mas_pm_likes_spoops')
        if data1[0]:
            if data1[2]:
                result.append('[player]不介意跳杀内容.' if target_lang == 'zh' else "[player] doesn't mind jumpscares.")
            else:
                result.append('[player]讨厌跳杀内容.' if target_lang == 'zh' else "[player] doesn't like jumpscares.")
        

        data1 = self.read_from_sf('_mas_pm_like_rap')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢说唱.' if target_lang == 'zh' else "[player] likes rap.")
            else:
                result.append('[player]不喜欢说唱.' if target_lang == 'zh' else "[player] doesn't like rap.")
        

        data1 = self.read_from_sf('_mas_pm_like_rock_n_roll')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢摇滚.' if target_lang == 'zh' else "[player] likes rock'n roll.")
            else:
                result.append('[player]不喜欢摇滚.' if target_lang == 'zh' else "[player] doesn't like rock'n roll.")
        

        data1 = self.read_from_sf('_mas_pm_like_jazz')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢爵士乐.' if target_lang == 'zh' else "[player] likes jazz.")
            else:
                result.append('[player]不喜欢爵士乐.' if target_lang == 'zh' else "[player] doesn't like jazz.")
        

        data1 = self.read_from_sf('_mas_pm_like_vocaloids')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢vocaloids.' if target_lang == 'zh' else "[player] likes vocaloids.")
            else:
                result.append('[player]不喜欢vocaloids.' if target_lang == 'zh' else "[player] doesn't like vocaloids.")
        

        data1 = self.read_from_sf('_mas_pm_like_orchestral_music')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢管弦乐.' if target_lang == 'zh' else "[player] likes orchestral music.")
            else:
                result.append('[player]不喜欢管弦乐.' if target_lang == 'zh' else "[player] doesn't like orchestral music.")
        

        data1 = self.read_from_sf('_mas_pm_like_other_music')
        if data1[0]:
            if data1[2]:
                result.append('[player]有独特的音乐品位.' if target_lang == 'zh' else "[player] has a special taste of music.")
                data2 = self.read_from_sf('_mas_pm_like_other_music_history')
                if data2[0] and re.search("u'(.*)'", data2[2]):
                    result.append(f'[player]还喜欢{re.search("u'(.*)'", data2[2])[1]}音乐.' if target_lang == 'zh' else f"[player] also likes {re.search("u'(.*)'", data2[2])[1]} music.")
        

        data1 = self.read_from_sf('_mas_pm_plays_instrument')
        if data1[0]:
            if data1[2]:
                result.append('[player]会一门乐器.' if target_lang == 'zh' else "[player] could play an instrument.")
            else:
                result.append('[player]还不会乐器.' if target_lang == 'zh' else "[player] couldn't play instruments.")
        

        data1 = self.read_from_sf('_mas_pm_play_jazz')
        if data1[0]:
            if data1[2]:
                result.append('[player]会爵士乐.' if target_lang == 'zh' else "[player] could play jazz.")
            else:
                result.append('[player]还不会爵士乐.' if target_lang == 'zh' else "[player] couldn't play jazz.")
                

        data1 = self.read_from_sf('_mas_pm_lang_other')
        if data1[0]:
            if data1[2]:
                result.append('[player]会一门外语.' if target_lang == 'zh' else "[player] could speak a foreign language.")
            else:
                result.append('[player]还不会外语.' if target_lang == 'zh' else "[player] couldn't speak foreign languages.")
        

        data1 = self.read_from_sf('_mas_pm_lang_jpn')
        if data1[0]:
            if data1[2]:
                result.append('[player]会日语.' if target_lang == 'zh' else "[player] could speak Japanese.")
            else:
                result.append('[player]还不会日语.' if target_lang == 'zh' else "[player] couldn't speak Japanese.")
        

        data1 = self.read_from_sf('_mas_pm_eye_color')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]的眼睛是{data1[2]}的.' if target_lang == 'zh' else f"[player] has {data1[2]} eyes.")
        

        data1 = self.read_from_sf('_mas_pm_hair_color')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]的头发是{data1[2]}的.' if target_lang == 'zh' else f"[player] has {data1[2]} hair.")
        

        data1 = self.read_from_sf('_mas_pm_hair_length')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]有一头{data1[2]}发.' if target_lang == 'zh' else f"[player] has {data1[2]} hair.")
        

        data1 = self.read_from_sf('_mas_pm_shaved_hair')
        if data1[0]:
            if data1[2]:
                result.append('[player]剃光了头发.' if target_lang == 'zh' else "[player] has their hair shaved.")
            else:
                result.append('[player]的头发掉完了.' if target_lang == 'zh' else "[player] lost their hair.")
        

        data1 = self.read_from_sf('_mas_pm_no_hair_no_talk')
        if data1[0]:
            if data1[2]:
                result.append('[player]不想提起头发的事情.' if target_lang == 'zh' else "[player] doesn't want to talk about their hair.")
            else:
                result.append('[player]不介意自己没有头发.' if target_lang == 'zh' else "[player] doesn't mind being bald.")
        

        data1 = self.read_from_sf('_mas_pm_skin_tone')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]是{data1[2]}肤色的.' if target_lang == 'zh' else f"[player] has {data1[2]} skin.")
        

        data1 = self.read_from_sf('_mas_pm_height')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]有{data1[2]}厘米高.' if target_lang == 'zh' else f"[player] is {data1[2]} centimeters tall.")
        

        data1 = self.read_from_sf('_mas_pm_units_height_metric')
        if data1[0]:
            if data1[2]:
                result.append('[player]惯用公制单位.' if target_lang == 'zh' else "[player] uses Metric units.")
            else:
                result.append('[player]惯用英制单位.' if target_lang == 'zh' else "[player] uses Imperial units.")
        

        data1 = self.read_from_sf('_mas_pm_live_in_city')
        if data1[0]:
            if data1[2]:
                result.append('[player]住在城市.' if target_lang == 'zh' else "[player] lives in city.")
            else:
                result.append('[player]住在乡村.' if target_lang == 'zh' else "[player] lives in countryside.")
        

        data1 = self.read_from_sf('_mas_pm_live_near_beach')
        if data1[0]:
            if data1[2]:
                result.append('[player]住在海边.' if target_lang == 'zh' else "[player] lives by the sea.")
            else:
                result.append('[player]住在内陆.' if target_lang == 'zh' else "[player] lives away from the sea.")
        

        data1 = self.read_from_sf('_mas_pm_live_south_hemisphere')
        if data1[0]:
            if data1[2]:
                result.append('[player]住在南半球.' if target_lang == 'zh' else "[player] lives in southern hemisphere.")
            else:
                result.append('[player]住在北半球.' if target_lang == 'zh' else "[player] lives in northern hemisphere.")
        

        data1 = self.read_from_sf('_mas_pm_social_personality')
        if data1[0]:
            if data1[2]:
                result.append(f'[player]属于{data1[2]}社会人格.' if target_lang == 'zh' else f"[player] is {data1[2]} in social personality.")
        

        data1 = self.read_from_sf('_mas_pm_likes_panties')
        if data1[0]:
            if data1[2]:
                result.append('[player]有恋物倾向.' if target_lang == 'zh' else "[player] is fetish.")
        

        data1 = self.read_from_sf('_mas_pm_drinks_soda')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢苏打水.' if target_lang == 'zh' else "[player] likes drinking soda.")
            else:
                result.append('[player]不喜欢苏打水.' if target_lang == 'zh' else "[player] doesn't like drinking soda.")
        

        data1 = self.read_from_sf('_mas_pm_eat_fast_food')
        if data1[0]:
            if data1[2]:
                result.append('[player]常吃快餐.' if target_lang == 'zh' else "[player] often eats fastfood.")
            else:
                result.append('[player]很少吃快餐.' if target_lang == 'zh' else "[player] seldom eats fastfood.")
        

        data1 = self.read_from_sf('_mas_pm_like_playing_sports')
        if data1[0]:
            if data1[2]:
                result.append('[player]平时喜欢运动.' if target_lang == 'zh' else "[player] likes playing sports.")
            else:
                result.append('[player]不喜欢运动.' if target_lang == 'zh' else "[player] doesn't like playing sports.")
        

        data1 = self.read_from_sf('_mas_pm_like_playing_tennis')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢网球.' if target_lang == 'zh' else "[player] likes playing tennis.")
            else:
                result.append('[player]不喜欢网球' if target_lang == 'zh' else "[player] doesn't like playing tennis.")
        

        data1 = self.read_from_sf('_mas_pm_meditates')
        if data1[0]:
            if data1[2]:
                result.append('[player]有冥想的习惯.' if target_lang == 'zh' else "[player] has habit of meditating.")
            else:
                result.append('[player]还没有尝试过冥想.' if target_lang == 'zh' else "[player] hasn't tried meditating yet.")
        

        data1 = self.read_from_sf('_mas_pm_see_therapist')
        if data1[0]:
            if data1[2]:
                result.append('[player]去看过心理医生.' if target_lang == 'zh' else "[player] has went to the therapist.")
            else:
                result.append('[player]还没有看过心理医生.' if target_lang == 'zh' else "[player] has never went to the therapist.")
        

        data1 = self.read_from_sf('_mas_pm_watch_mangime')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢动漫作品.' if target_lang == 'zh' else "[player] likes animes.")
            else:
                result.append('[player]不喜欢动漫作品.' if target_lang == 'zh' else "[player] doesn't like animes.")
        

        data1 = self.read_from_sf('_mas_pm_do_smoke')
        if data1[0]:
            if data1[2]:
                result.append('[player]有吸烟的习惯.' if target_lang == 'zh' else "[player] has habit of smoking.")
            else:
                result.append('[player]不吸烟.' if target_lang == 'zh' else "[player] doesn't smoke.")
        

        data1 = self.read_from_sf('_mas_pm_do_smoke_quit')
        if data1[0]:
            if data1[2]:
                result.append('[player]希望戒烟.' if target_lang == 'zh' else "[player] wants to give up smoking.")
        

        data1 = self.read_from_sf('_mas_pm_driving_can_drive')
        if data1[0]:
            if data1[2]:
                result.append('[player]会开车.' if target_lang == 'zh' else "[player] could drive.")
            else:
                result.append('[player]还没有驾照.' if target_lang == 'zh' else "[player] couldn't drive yet.")
        

        data1 = self.read_from_sf('_mas_pm_driving_learning')
        if data1[0]:
            if data1[2]:
                result.append('[player]正在考驾照.' if target_lang == 'zh' else "[player] is taking his driving license test.")
        

        data1 = self.read_from_sf('_mas_pm_driving_been_in_accident')
        if data1[0]:
            if data1[2]:
                result.append('[player]遇到过交通事故.' if target_lang == 'zh' else "[player] has been envolved in a traffic accident.")
        

        data1 = self.read_from_sf('_mas_pm_donate_charity')
        if data1[0]:
            if data1[2]:
                result.append('[player]参与过慈善捐赠.' if target_lang == 'zh' else "[player] has donated to charity.")
            else:
                result.append('[player]还没有慈善捐赠过.' if target_lang == 'zh' else "[player] hasn't donated to charity yet.")
        

        data1 = self.read_from_sf('_mas_pm_volunteer_charity')
        if data1[0]:
            if data1[2]:
                result.append('[player]做过志愿者.' if target_lang == 'zh' else "[player] has volunteered for charity.")
            else:
                result.append('[player]还没有做过志愿者.' if target_lang == 'zh' else "[player] hasn't volunteered for charity yet.")
        

        data1 = self.read_from_sf('_mas_pm_have_fam')
        if data1[0]:
            if data1[2]:
                result.append('[player]有健全的原生家庭.' if target_lang == 'zh' else "[player] has an intact family.")
            else:
                result.append('[player]的家庭不完整.' if target_lang == 'zh' else "[player]'s family isn't intact.")
        

        data1 = self.read_from_sf('_mas_pm_no_fam_bother')
        if data1[0]:
            if data1[2]:
                result.append('[player]缺少亲人的陪伴.' if target_lang == 'zh' else "[player] lacks company of relatives.")
        

        data1 = self.read_from_sf('_mas_pm_have_fam_mess')
        if data1[0]:
            if data1[2]:
                result.append('[player]的家庭生活并不和睦.' if target_lang == 'zh' else "[player] doesn't get on well with their family.")
            else:
                result.append('[player]和家人相处很好.' if target_lang == 'zh' else "[player] gets on well with their family.")
        

        data1 = self.read_from_sf('_mas_pm_have_fam_mess_better')
        if data1[0]:
            if data1[2] == 'YES':
                result.append('[player]认为自己和家人的关系会改善.' if target_lang == 'zh' else "[player] wants to improve their relationship with family.")
            elif data1[2] == 'NO':
                result.append('[player]不觉得自己和家人的关系能改善了.' if target_lang == 'zh' else "[player] has given up on their relationship with family.")
        

        data1 = self.read_from_sf('_mas_pm_have_fam_sibs')
        if data1[0]:
            if data1[2]:
                result.append('[player]有兄弟姐妹.' if target_lang == 'zh' else "[player] has siblings.")
            else:
                result.append('[player]是独生子女.' if target_lang == 'zh' else "[player] doesn't have siblings.")
        

        data1 = self.read_from_sf('_mas_pm_no_talk_fam')
        if data1[0]:
            if data1[2]:
                result.append('[player]不想提及自己的家庭.' if target_lang == 'zh' else "[player] doesn't want to talk about their family.")
        

        data1 = self.read_from_sf('_mas_pm_fam_like_monika')
        if data1[0]:
            if data1[2]:
                result.append('[player]觉得家人能够接受莫妮卡.' if target_lang == 'zh' else "[player] thinks their family could accept their relationship with Monika.")
            else:
                result.append('[player]觉得家人不能接受莫妮卡.' if target_lang == 'zh' else "[player] doesn't think their family could accept their relationship with Monika.")
        

        data1 = self.read_from_sf('_mas_pm_gone_to_prom')
        if data1[0]:
            if data1[2]:
                data2 = self.read_from_sf('_mas_pm_prom_good')
                if data2[0]:
                    if data2[2]:
                        result.append('[player]参加过很开心的毕业舞会.' if target_lang == 'zh' else "[player] has enjoyed a prom.")
                    else:
                        result.append('[player]不太喜欢毕业舞会.' if target_lang == 'zh' else "[player] doesn't like proms.")
                else:
                    result.append('[player]参加过毕业舞会.' if target_lang == 'zh' else "[player] has been to a prom.")
            else:
                data2 = self.read_from_sf('_mas_pm_no_prom')
                if data2[0]:
                    if data2[2]:
                        result.append('[player]的学校没有毕业舞会.' if target_lang == 'zh' else "[player]'s school didn't have proms.")
                    else:
                        result.append('[player]没有参加毕业舞会.' if target_lang == 'zh' else "[player] hasn't gone to a prom yet.")
        

        data1 = self.read_from_sf('_mas_pm_prom_monika')
        if data1[0]:
            if data1[2]:
                result.append('[player]希望自己在毕业舞会上做莫妮卡的舞伴.' if target_lang == 'zh' else "[player] wish they could have Monika at their prom.")
        

        data1 = self.read_from_sf('_mas_pm_prom_not_interested')
        if data1[0]:
            if data1[2]:
                result.append('[player]对舞会和毕业典礼不感兴趣.' if target_lang == 'zh' else "[player] is not interested in proms.")
                data2 = self.read_from_sf('_mas_pm_prom_shy')
                if data2[0]:
                    if data2[2]:
                        result.append('[player]觉得参加集会太害羞了.' if target_lang == 'zh' else "[player] is too shy for proms.")
        

        data1 = self.read_from_sf('_mas_pm_has_been_to_amusement_park')
        if data1[0]:
            if data1[2]:
                result.append('[player]去过游乐园.' if target_lang == 'zh' else "[player] has been to an amusement park.")
            else:
                result.append('[player]还没有去过游乐园.' if target_lang == 'zh' else "[player] hasn't been to amusement parks yet.")
        

        data1 = self.read_from_sf('_mas_pm_likes_travelling')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢旅游.' if target_lang == 'zh' else "[player] likes travelling.")
            else:
                result.append('[player]不喜欢旅游.' if target_lang == 'zh' else "[player] doesn't like travelling.")
        

        data1 = self.read_from_sf('_mas_pm_had_relationships_many')
        if data1[0]:
            if data1[2]:
                result.append('[player]此前有过其他爱人.' if target_lang == 'zh' else "[player] had been in love with others before.")
            else:
                data2 = self.read_from_sf('_mas_pm_had_relationships_just_one')
                if data2[0]:
                    if data2[2]:
                        result.append('[player]此前有过其他爱人.' if target_lang == 'zh' else "[player] had been in love with someone before.")
                    else:
                        result.append('莫妮卡是[player]的初恋.' if target_lang == 'zh' else "Monika is [player]'s first girlfriend.")
                else:
                    result.append('莫妮卡是[player]的初恋.' if target_lang == 'zh' else "Monika is [player]'s first girlfriend.")
        

        data1 = self.read_from_sf('_mas_pm_is_bullying_victim')
        if data1[0]:
            if data1[2]:
                result.append('[player]曾遭遇过校园霸凌.' if target_lang == 'zh' else "[player] has been bullied before.")
        

        data1 = self.read_from_sf('_mas_pm_has_bullied_people')
        if data1[0]:
            if data1[2]:
                result.append('[player]曾霸凌过他人.' if target_lang == 'zh' else "[player] has bullied someone else.")
        

        data1 = self.read_from_sf('_mas_pm_currently_bullied')
        if data1[0]:
            if data1[2]:
                result.append('[player]正遭受霸凌的困扰.' if target_lang == 'zh' else "[player] is currently being bullied.")
        

        data1 = self.read_from_sf('_mas_pm_has_friends')
        if data1[0]:
            if data1[2]:
                data2 = self.read_from_sf('_mas_pm_few_friends')
                if data2[0]:
                    if data2[2]:
                        result.append('[player]的朋友很少.' if target_lang == 'zh' else "[player] has few friends.")
                    else:
                        result.append('[player]有一些朋友.' if target_lang == 'zh' else "[player] has some friends.")
                else:
                    result.append('[player]有一些朋友.' if target_lang == 'zh' else "[player] has some friends.")
            else:
                result.append('[player]没有朋友.' if target_lang == 'zh' else "[player] has no friend.")
        

        data1 = self.read_from_sf('_mas_pm_feels_lonely_sometimes')
        if data1[0]:
            if data1[2]:
                result.append('[player]有时候感觉很孤单.' if target_lang == 'zh' else "[player] gets lonely sometimes.")
            else:
                result.append('[player]的生活很充实.' if target_lang == 'zh' else "[player] usually feels enriched.")
        

        data1 = self.read_from_sf('_mas_pm_given_false_justice')
        if data1[0]:
            if data1[2]:
                result.append('[player]曾行使过错误的正义.' if target_lang == 'zh' else "[player] has given false justice.")
        

        data1 = self.read_from_sf('_mas_pm_owns_car')
        if data1[0]:
            if data1[2]:
                data2 = self.read_from_sf('_mas_pm_owns_car_type')
                if data2[0]:
                    if data2[2]:
                        result.append(f'[player]有一辆{data2[2]}.' if target_lang == 'zh' else f"[player] has a {data2[2]}.")
                    else:
                        result.append('[player]有自己的车.' if target_lang == 'zh' else "[player] has their own vehicle.")
                else:
                    result.append('[player]有自己的车.' if target_lang == 'zh' else "[player] has their own vehicle.")
            else:
                result.append('[player]自己还没有车.' if target_lang == 'zh' else "[player] has no vehicle yet.")
        

        data1 = self.read_from_sf('_mas_pm_has_code_experience')
        if data1[0]:
            if data1[2]:
                result.append('[player]有编程基础.' if target_lang == 'zh' else "[player] knows how to program.")
            else:
                result.append('[player]没有编程基础.' if target_lang == 'zh' else "[player] doesn't know how to program yet.")
        

        data1 = self.read_from_sf('_mas_pm_likes_poetry')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢诗歌.' if target_lang == 'zh' else "[player] likes poetry.")
            else:
                result.append('[player]不喜欢诗歌.' if target_lang == 'zh' else "[player] doesn't like poetry.")
        

        data1 = self.read_from_sf('_mas_pm_likes_board_games')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢桌游.')
        

        data1 = self.read_from_sf('_mas_pm_works_out')
        if data1[0]:
            if data1[2]:
                result.append('[player]经常去健身.')
            else:
                result.append('[player]不喜欢健身.')
        

        data1 = self.read_from_sf('_mas_pm_social_personality')
        if data1[0]:
            if data1[2]:
                if data1[2] == '_mas_SP_EXTROVERT':
                    result.append('[player]性格外向.')
                elif data1[2] == '_mas_SP_INTROVERT':
                    result.append('[player]性格内向.')
                else:
                    result.append('[player]性格中和.')
        

        data1 = self.read_from_sf('_mas_pm_likes_nature')
        if data1[0]:
            if data1[2]:
                result.append('[player]喜欢接触自然.')
            else:
                result.append('[player]不太喜欢接触自然.')
        

        data1 = self.read_from_sf('_mas_pm_swear_frequency')
        if data1[0]:
            if data1[2]:
                if data1[2] == 'SF_OFTEN':
                    result.append('[player]较常说脏话.')
                elif data1[2] == 'SF_SOMETIMES':
                    result.append('[player]很少说脏话.')
                else:
                    result.append('[player]从不说脏话.')
        

        data1 = self.read_from_sf('_mas_gender')
        if data1[0]:
            if data1[2]:
                if data1[2] == 'M':
                    result.append('[player]是男生.')
                elif data1[2] == 'F':
                    result.append('[player]是女生.')
                else:
                    result.append('[player]是非二元性别.')
        

        return result

    def conclude_moni_sf(self):
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
        return data_ex

    def conclude_cb_sf(self, cb):
        data_exp = self.read_from_sf('mas_player_additions')[2]
        if data_exp and len(data_exp) > cb:
            data_exp = sample(data_exp, cb)
        return data_exp

    def mfocus_form_info(self):
        success = True
        exception = None
        if not self.modded_signal and self.formed_info:
            return success, exception, self.formed_info
        conclusion = []
        mf_hcb = self.read_from_sf('mas_sf_hcb')
        if mf_hcb[0]:
            if mf_hcb[2]:
                conclusion.extend(self.conclude_cb_sf(360) or [])
            else:
                conclusion.extend(self.conclude_basic_sf() or [])
                conclusion.extend(self.conclude_cb_sf(72) or [])
        else:
            conclusion.extend(self.conclude_basic_sf() or [])
            conclusion.extend(self.conclude_cb_sf(72) or [])
        conclusion.extend(self.conclude_moni_sf() or [])

        with open(f'persistents/{self.user_id}_{self.chat_session_num}_friendly.json', 'w+', encoding = 'utf-8') as sf_friendly:
            sf_friendly.write(json.dumps(conclusion, ensure_ascii=False))

        self.formed_info = conclusion
        self.modded_signal = False
        return success, exception, self.formed_info

    async def mfocus_find_info(self, query):
        success = True
        exception = ''
        try:
            information = (await wrap_run_in_exc(None, self.mfocus_form_info))[2]
            async with AsyncOpenAI(
                api_key='EMPTY',
                base_url=load_env('MFOCUS_ADDR'),
                ) as client:
                model_list = await client.models.list()
                model_type = model_list.data[0].id
                print(f'MFocus sfe addressing model, response is:\n{model_type}\nEnd of MFocus sfe addressing model')
                system_init = """你是一个人工智能助手, 名为[player], 你的任务是检索信息. 你接下来会收到一个来自'莫妮卡'的问题和一系列信息, 这些信息是Python列表的形式.
请你作为[player], 从信息中挑选1至5条最能用于回答的信息, 互不重复, 并以单行Python列表的形式返回. 如果你最终认为没有信息符合条件, 回答None.
注意不要对信息作任何改动.
使用以下格式回答:
Thought: 简要地思考如何选取信息, 以及这些信息与句子有何关联.
Answer: 将你认为有用的信息作为一个单行Python列表返回. 如果你最终认为没有信息符合条件, 回答None.
Begin!
"""
                messages = [{'role': 'system', 'content': system_init}]
                messages.append({'role': 'user', 'content': f'sentence: [{query}], information: {information}'})
                completion_args = {
                    "model": model_type,
                    "messages": messages,
                    "temperature": 0.1,
                    "top_p": 0.6,
                    "presence_penalty": -0.5,
                    "frequency_penalty": 0.5,
                    "seed": 42
                }
                resp = await client.chat.completions.create(**completion_args)
                response = resp.choices[0].message.content
            print(f"MFocus sfe searching persistent, response is:\n{response}\nEnd of MFocus sfe searching persistent")
            answer_re = re.search(r'Answer\s*:\s*(\[.*\])', response, re.I)
            if answer_re and not re.match(r'\s*none', answer_re[1], re.I):
                response = answer_re[1]
            else:
                return success, exception, '[None]', ''
            return success, exception, response, response
        except Exception as excepted:
            traceback.print_exc()
            success = False
            exception = excepted
            return success, exception, '[None]', ''

if __name__ == "__main__":
    ins = sf_bound_instance(4, 1, 'en')
    ins.init1()
    print(ins.mfocus_form_info()[2])
    ins.init2()
    print(ins.mfocus_form_info()[2])
    #print(ins.read_from_sf("sessions"))
    #print(asyncio.run(ins.mfocus_find_info('你喜欢吃什么')))
    #print(asyncio.run(mfocus_find_info(22398, 1, '你喜欢吃什么')))