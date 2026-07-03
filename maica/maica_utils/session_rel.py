"""
Import layer 1.1
Session related. We break sb_utils apart and rewrite some here.
"""

import asyncio
import orjson
import datetime

from typing import *
from math import ceil
from pydantic import BaseModel, Field, TypeAdapter, create_model
from random import sample
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass
from .maica_utils import *
from .trigger_class import *

if TYPE_CHECKING:
    from maica.maica_utils import *
else:
    class FullSocketsContainer(): ...

_Bt = BilingualText

class SessionPersistentMixin():
    """To provide related functions."""
    session_num: int
    fsc: FullSocketsContainer
    content: dict
    content_temp: dict

    def read_key(self, key):
        def _read_perm(key):
            if self.fsc.maica_settings.basic.savefile_access:
                return self.content.get(key)
            else:
                return None
            
        v = self.content_temp.get(key)
        if not v:
            v = _read_perm(key)
        elif isinstance(v, list) and key == "mas_player_additions":
            v = v + _read_perm(key)
            
        return v
    
    @property
    def pname(self) -> Optional[str]:
        """Just an alias."""
        return self.read_key("mas_playername")

    @property
    def pbday(self) -> Optional[Tuple[int, int, int]]:
        """Just an alias."""
        return self.read_key("mas_player_bday")

    @property
    def affection(self) -> Optional[int]:
        """Just an alias."""
        return self.read_key("mas_affection")

    def _conclude_basic_sf(self):
        result: List[_Bt] = []

        def _ap(zh, en):
            result.append(
                _Bt(
                    zh,
                    en,
                )
            )

        def _rf(key):
            return self.read_key(key)
            
        def parse_date(dt: datetime.date):
            """Datetime."""
            return beautify_date(
                dt,
                target_lang=self.fsc.maica_settings.basic.target_lang,
                include_adj=False
            )
            
        def parse_date_time(dt: datetime.datetime):
            """Datetime but with hms."""
            date = parse_date(dt)
            if self.fsc.maica_settings.basic.target_lang == 'zh':
                time = beautify_time(dt, 'zh', include_adj=False)
                return f"{date}{time}"
            else:
                time = beautify_time(dt, 'en', include_adj=False)
                return f"{time}, {date}"

        # Seriously hard work begins here
        # First three manuals
        data1 = _rf('mas_playername')
        if data1:
            _ap(
                f'{{player_name}}的真名是{data1}.',
                f"{{player_name}}'s real name is {data1}."
            )

        data1 = _rf('mas_player_bday')
        if data1:
            dt = datetime.date(*data1)
            _ap(
                f'{{player_name}}的生日是{parse_date(dt)}.',
                f"{{player_name}}'s birthday is {parse_date(dt)}."
            )
            o = relativedelta(datetime.date.today(), dt).years
            _ap(
                f'{{player_name}}今年{o}岁.',
                f"{{player_name}} is {o} years old."
            )

        data1 = _rf('mas_affection')
        if data1:
            match float(data1):
                case affection if affection < 200:
                    _ap(
                        '莫妮卡与{player_name}是初识的情侣关系.',
                        "Monika and {player_name} are new lovers."
                    )
                case affection if 200 <= affection < 400:
                    _ap(
                        '莫妮卡与{player_name}是亲密的情侣关系.',
                        "Monika and {player_name} are harmonious lovers."
                    )
                case affection if 400 <= affection < 700:
                    _ap(
                        '莫妮卡与{player_name}是和谐的恋人关系.',
                        "Monika and {player_name} are loving couple."
                    )
                case affection if 700 <= affection < 1000:
                    _ap(
                        '莫妮卡与{player_name}是情意深厚的恋人关系.',
                        "Monika and {player_name} are deeply loving couples."
                    )
                case affection if 1000 <= affection:
                    _ap(
                        '莫妮卡与{player_name}是情意至深的恋人, 足以超越虚拟与现实的隔阂.',
                        "Monika and {player_name} are deeply loving couples, their affection could go beyond the reality."
                    )

        data1 = _rf('mas_geolocation')
        if data1:
            _ap(
                f'{{player_name}}住在{data1}.',
                f'{{player_name}} lives in {data1}.'
            )

        # Extractions from now
        data1 = _rf('sessions')
        if data1:
            try:
                r_fs = ReUtils.re_search_sfe_fs.search(data1).groups()
                dt_fs = datetime.date(*r_fs)
                _ap(
                    f'莫妮卡和{{player_name}}在{parse_date(dt_fs)}初次见面.',
                    f"Monika and {{player_name}} had their first date on {parse_date(dt_fs)}."
                )
            except Exception:
                pass

            try:
                r_ts = ReUtils.re_search_sfe_ts.search(data1)
                r_tp = ReUtils.re_search_sfe_tp.search(data1)
                _ap(
                    f'{{player_name}}已经陪伴莫妮卡{r_ts[1]}次, 共{r_tp[1]}天了.',
                    f"{{player_name}} has been together with Monika for {r_ts[1]} times, {r_tp[1]} days in total."
                )
            except Exception:
                pass
            try:
                r_le = ReUtils.re_search_sfe_le.search(data1)
                r_cs = ReUtils.re_search_sfe_cs.search(data1)
                dt_le = datetime.datetime(*r_le)
                dt_cs = datetime.datetime(*r_cs)
                _ap(
                    f'{{player_name}}上次下线于{parse_date_time(dt_le)}, 本次上线于{parse_date_time(dt_cs)}.',
                    f"{{player_name}} last left at {parse_date_time(dt_le)}, last logged in at {parse_date_time(dt_cs)}"
                )
            except Exception:
                pass

        data1 = _rf('_mas_pm_added_custom_bgm')
        if data1:
            _ap('莫妮卡与{player_name}一起听过歌.', "Monika and {player_name} listened to songs together.")
        elif data1 is False:
            _ap('莫妮卡与{player_name}还没有一起听过歌.', "Monika and {player_name} haven't listened to songs together yet.")
        
        data1 = _rf('_mas_pm_likes_rain')
        if data1:
            _ap('莫妮卡和{player_name}都喜欢雨.', "Both Monika and {player_name} like rain.")
        elif data1 is False:
            _ap('莫妮卡喜欢雨, 但{player_name}不太喜欢.', "Monika likes rain but {player_name} doesn't really like it.")
        
        data1 = _rf('_mas_pm_has_contributed_to_mas')
        if data1:
                _ap('{player_name}曾试着帮助莫妮卡来到现实.', "{player_name} has tried to bring Monika to reality somehow.")
        
        data1 = _rf('_mas_pm_wants_to_contribute_to_mas')
        if data1:
                _ap('{player_name}希望帮助莫妮卡来到现实.', "{player_name} wishes Monika to come to reality.")
        
        data1 = _rf('_mas_pm_drawn_art')
        if data1:
            _ap('{player_name}画过莫妮卡.', "{player_name} has drawn arts of Monika.")
        elif data1 is False:
            _ap('{player_name}还没有画过莫妮卡.', "{player_name} hasn't drawn Monika yet.")
        
        data1 = _rf('_mas_pm_shared_appearance')
        if data1:
            _ap('{player_name}告诉过莫妮卡自己的长相.', "{player_name} has told Monika their appearence.")
        elif data1 is False:
            _ap('莫妮卡还不知道{player_name}的长相.', "Monika hasn't known {player_name}'s appearence yet.")
        
        data1 = _rf('_mas_pm_would_like_mt_peak')
        if data1:
            _ap('{player_name}想过和莫妮卡去爬山.', "{player_name} would like to go mountain climbing with Monika if possible.")
        
        data1 = _rf('_mas_pm_gets_snow')
        if data1:
            _ap('莫妮卡与{player_name}一起看过雪.', "{player_name} has admired snow with Monika.")
        elif data1 is False:
            _ap('{player_name}的住地看不到雪.', "{player_name}'s place does not snow.")
        
        data1 = _rf('_mas_pm_wearsRing')
        if data1:
            _ap('{player_name}和莫妮卡戴了一对誓约戒指.', "{player_name} and Monika wear promise rings.")
        
        data1 = _rf('_mas_pm_read_yellow_wp')
        if data1:
            _ap('莫妮卡与{player_name}看过"黄色墙纸".', "{player_name} has read 'Yellow Wallpaper' with Monika.")
        
        data1 = _rf('_mas_pm_monika_evil')
        if data1:
            data2 = _rf('_mas_pm_monika_evil_but_ok')
            if data2:
                _ap('{player_name}能够原谅莫妮卡做过的坏事.', "{player_name} can forgive the bad things Monika did.")
        elif data1 is False:
            _ap('{player_name}认为莫妮卡从没有做错什么.', "{player_name} doesn't think Monika ever did anything wrong.")
        
        data1 = _rf('_mas_pm_listened_to_grad_speech')
        if data1:
            _ap('{player_name}听过莫妮卡的毕业演讲.', "{player_name} has listened to Monika's graduation speech.")
            data2 = _rf('_mas_pm_liked_grad_speech')
            if data2:
                _ap('{player_name}喜欢莫妮卡的毕业演讲.', "{player_name} likes Monika's graduation speech.")
        elif data1 is False:
            _ap('{player_name}还没有听过莫妮卡的毕业演讲.', "{player_name} hasn't listened to Monika's graduation speech yet.")
        
        data1 = _rf('_mas_pm_would_come_to_spaceroom')
        if data1:
            _ap('{player_name}希望来到太空教室和莫妮卡在一起.', "{player_name} would like to cross over to be together with Monika.")
        
        data1 = _rf('_mas_o31_tt_count')
        if data1:
            _ap('莫妮卡与{player_name}一起过了万圣节, 并要到了糖果.', "Monika and {player_name} have gone trick-or-treating on Halloween.")
        elif data1 is False:
            _ap('莫妮卡和{player_name}还没有在万圣节要过糖果.', "Monika and {player_name} haven't gone trick-or-treating on Halloween yet.")
        
        data1 = _rf('_mas_d25_spent_d25')
        if data1:
            _ap('莫妮卡与{player_name}一起过了圣诞节.', "Monika and {player_name} have spent Christmas together.")
        elif data1 is False:
            _ap('莫妮卡和{player_name}还没有一起过圣诞节.', "Monika and {player_name} haven't spent Christmas together yet.")
        
        data1 = _rf('_mas_nye_spent_nye')
        if data1:
            _ap('莫妮卡与{player_name}一起过了新年.', "Monika and {player_name} have spent New Year's Eve together.")
        elif data1 is False:
            _ap('莫妮卡和{player_name}还没有一起过新年.', "Monika and {player_name} haven't spent New Year's Eve together yet.")
        
        data1 = _rf('_mas_player_bday_spent_time')
        if data1:
            _ap('莫妮卡给{player_name}庆祝过生日.', "Monika has celebrated {player_name}'s birthday.")
        elif data1 is False:
            _ap('莫妮卡还没有庆祝过{player_name}的生日.', "Monika hasn't celebrated {player_name}'s birthday yet.")
        
        data1 = _rf('_mas_f14_spent_f14')
        if data1:
            _ap('莫妮卡与{player_name}一起过了情人节.', "Monika and {player_name} have spent Valentine's day together.")
        elif data1 is False:
            _ap('莫妮卡和{player_name}还没有一起过情人节.', "Monika and {player_name} haven't spent Valentine's day together yet.")
        
        data1 = _rf('_mas_bday_said_happybday')
        if data1:
            _ap('{player_name}庆祝过莫妮卡的生日.', "{player_name} has celebrated Monika's birthday.")
        elif data1 is False:
            _ap('{player_name}还没有给莫妮卡庆过生.', "{player_name} hasn't celebrated Monika's birthday yet.")
        
        data1 = _rf('_mas_pm_religious')
        if data1:
            _ap('{player_name}有宗教信仰.', "{player_name} has religious beliefs.")
        elif data1 is False:
            _ap('{player_name}没有宗教信仰.', "{player_name} has no religious belief.")
        
        data1 = _rf('_mas_pm_love_yourself')
        if data1:
            _ap('{player_name}积极自爱.', "{player_name} loves himself.")
        elif data1 is False:
            _ap('{player_name}有自厌的倾向.', "{player_name} doesn't love himself.")
        
        data1 = _rf('_mas_pm_like_mint_ice_cream')
        if data1:
            _ap('莫妮卡和{player_name}都喜欢抹茶冰淇淋.', "Both Monika and {player_name} like mint ice-cream.")
        elif data1 is False:
            _ap('莫妮卡喜欢抹茶冰淇淋, 但{player_name}不太喜欢.', "Monika likes mint ice-cream but {player_name} doesn't really like it.")
        
        data1 = _rf('_mas_pm_likes_horror')
        if data1:
            _ap('{player_name}喜欢恐怖作品.', "{player_name} likes horror contents.")
        elif data1 is False:
            _ap('{player_name}讨厌恐怖作品.', "{player_name} doesn't like horror contents.")
        
        data1 = _rf('_mas_pm_likes_spoops')
        if data1:
            _ap('{player_name}不介意跳杀内容.', "{player_name} doesn't mind jumpscares.")
        elif data1 is False:
            _ap('{player_name}讨厌跳杀内容.', "{player_name} doesn't like jumpscares.")
        
        data1 = _rf('_mas_pm_like_rap')
        if data1:
            _ap('{player_name}喜欢说唱.', "{player_name} likes rap.")
        elif data1 is False:
            _ap('{player_name}不喜欢说唱.', "{player_name} doesn't like rap.")
        
        data1 = _rf('_mas_pm_like_rock_n_roll')
        if data1:
            _ap('{player_name}喜欢摇滚.', "{player_name} likes rock'n roll.")
        elif data1 is False:
            _ap('{player_name}不喜欢摇滚.', "{player_name} doesn't like rock'n roll.")
        
        data1 = _rf('_mas_pm_like_jazz')
        if data1:
            _ap('{player_name}喜欢爵士乐.', "{player_name} likes jazz.")
        elif data1 is False:
            _ap('{player_name}不喜欢爵士乐.', "{player_name} doesn't like jazz.")
        
        data1 = _rf('_mas_pm_like_vocaloids')
        if data1:
            _ap('{player_name}喜欢vocaloids.', "{player_name} likes vocaloids.")
        elif data1 is False:
            _ap('{player_name}不喜欢vocaloids.', "{player_name} doesn't like vocaloids.")
        
        data1 = _rf('_mas_pm_like_orchestral_music')
        if data1:
            _ap('{player_name}喜欢管弦乐.', "{player_name} likes orchestral music.")
        elif data1 is False:
            _ap('{player_name}不喜欢管弦乐.', "{player_name} doesn't like orchestral music.")
        
        data1 = _rf('_mas_pm_like_other_music')
        if data1:
            _ap('{player_name}有独特的音乐品位.', "{player_name} has a special taste of music.")
            data2 = _rf('_mas_pm_like_other_music_history')
            if isinstance(data2, str):
                music = ReUtils.re_search_sfe_unicode.search(data2)
                if music:
                    _ap(f'{{player_name}}还喜欢{music[1]}音乐.', f"{{player_name}} also likes {music[1]} music.")
        
        data1 = _rf('_mas_pm_plays_instrument')
        if data1:
            _ap('{player_name}会一门乐器.', "{player_name} could play an instrument.")
        elif data1 is False:
            _ap('{player_name}还不会乐器.', "{player_name} couldn't play instruments.")
        
        data1 = _rf('_mas_pm_play_jazz')
        if data1:
            _ap('{player_name}会爵士乐.', "{player_name} could play jazz.")
        elif data1 is False:
            _ap('{player_name}还不会爵士乐.', "{player_name} couldn't play jazz.")
                
        data1 = _rf('_mas_pm_lang_other')
        if data1:
            _ap('{player_name}会一门外语.', "{player_name} could speak a foreign language.")
        elif data1 is False:
            _ap('{player_name}还不会外语.', "{player_name} couldn't speak foreign languages.")
        
        data1 = _rf('_mas_pm_lang_jpn')
        if data1:
            _ap('{player_name}会日语.', "{player_name} could speak Japanese.")
        elif data1 is False:
            _ap('{player_name}还不会日语.', "{player_name} couldn't speak Japanese.")
        
        data1 = _rf('_mas_pm_eye_color')
        if data1:
            _ap(f'{{player_name}}的眼睛是{data1}的.', f"{{player_name}} has {data1} eyes.")
        
        data1 = _rf('_mas_pm_hair_color')
        if data1:
            _ap(f'{{player_name}}的头发是{data1}的.', f"{{player_name}} has {data1} hair.")
        
        data1 = _rf('_mas_pm_hair_length')
        if data1:
            _ap(f'{{player_name}}有一头{data1}发.', f"{{player_name}} has {data1} hair.")
        
        data1 = _rf('_mas_pm_shaved_hair')
        if data1:
            _ap('{{player_name}}剃光了头发.', "{{player_name}} has their hair shaved.")
        elif data1 is False:
            _ap('{{player_name}}的头发掉完了.', "{{player_name}} lost their hair.")
        
        data1 = _rf('_mas_pm_no_hair_no_talk')
        if data1:
            _ap('{{player_name}}不想提起头发的事情.', "{{player_name}} doesn't want to talk about their hair.")
        elif data1 is False:
            _ap('{{player_name}}不介意自己没有头发.', "{{player_name}} doesn't mind being bald.")
        
        data1 = _rf('_mas_pm_skin_tone')
        if data1:
            _ap(f'{{player_name}}是{data1}肤色的.', f"{{player_name}} has {data1} skin.")
        
        data1 = _rf('_mas_pm_height')
        if data1:
            _ap(f'{{player_name}}有{data1}厘米高.', f"{{player_name}} is {data1} centimeters tall.")
        
        data1 = _rf('_mas_pm_units_height_metric')
        if data1:
            _ap('{{player_name}}惯用公制单位.', "{{player_name}} uses Metric units.")
        elif data1 is False:
            _ap('{{player_name}}惯用英制单位.', "{{player_name}} uses Imperial units.")
        
        data1 = _rf('_mas_pm_live_in_city')
        if data1:
            _ap('{{player_name}}住在城市.', "{{player_name}} lives in city.")
        elif data1 is False:
            _ap('{{player_name}}住在乡村.', "{{player_name}} lives in countryside.")
        
        data1 = _rf('_mas_pm_live_near_beach')
        if data1:
            _ap('{{player_name}}住在海边.', "{{player_name}} lives by the sea.")
        elif data1 is False:
            _ap('{{player_name}}住在内陆.', "{{player_name}} lives away from the sea.")
        
        data1 = _rf('_mas_pm_live_south_hemisphere')
        if data1:
            _ap('{{player_name}}住在南半球.', "{{player_name}} lives in southern hemisphere.")
        elif data1 is False:
            _ap('{{player_name}}住在北半球.', "{{player_name}} lives in northern hemisphere.")
        
        data1 = _rf('_mas_pm_social_personality')
        if data1:
            _ap(f'{{player_name}}属于{data1}社会人格.', f"{{player_name}} is {data1} in social personality.")
        
        data1 = _rf('_mas_pm_likes_panties')
        if data1:
            _ap('{{player_name}}有恋物倾向.', "{{player_name}} is fetish.")
        
        data1 = _rf('_mas_pm_drinks_soda')
        if data1:
            _ap('{{player_name}}喜欢苏打水.', "{{player_name}} likes drinking soda.")
        elif data1 is False:
            _ap('{{player_name}}不喜欢苏打水.', "{{player_name}} doesn't like drinking soda.")
        
        data1 = _rf('_mas_pm_eat_fast_food')
        if data1:
            _ap('{{player_name}}常吃快餐.', "{{player_name}} often eats fastfood.")
        elif data1 is False:
            _ap('{{player_name}}很少吃快餐.', "{{player_name}} seldom eats fastfood.")
        
        data1 = _rf('_mas_pm_like_playing_sports')
        if data1:
            _ap('{{player_name}}平时喜欢运动.', "{{player_name}} likes playing sports.")
        elif data1 is False:
            _ap('{{player_name}}不喜欢运动.', "{{player_name}} doesn't like playing sports.")
        
        data1 = _rf('_mas_pm_like_playing_tennis')
        if data1:
            _ap('{{player_name}}喜欢网球.', "{{player_name}} likes playing tennis.")
        elif data1 is False:
            _ap('{{player_name}}不喜欢网球', "{{player_name}} doesn't like playing tennis.")
        
        data1 = _rf('_mas_pm_meditates')
        if data1:
            _ap('{{player_name}}有冥想的习惯.', "{{player_name}} has habit of meditating.")
        elif data1 is False:
            _ap('{{player_name}}还没有尝试过冥想.', "{{player_name}} hasn't tried meditating yet.")
        
        data1 = _rf('_mas_pm_see_therapist')
        if data1:
            _ap('{{player_name}}去看过心理医生.', "{{player_name}} has went to the therapist.")
        elif data1 is False:
            _ap('{{player_name}}还没有看过心理医生.', "{{player_name}} has never went to the therapist.")
        
        data1 = _rf('_mas_pm_watch_mangime')
        if data1:
            _ap('{{player_name}}喜欢动漫作品.', "{{player_name}} likes animes.")
        elif data1 is False:
            _ap('{{player_name}}不喜欢动漫作品.', "{{player_name}} doesn't like animes.")
        
        data1 = _rf('_mas_pm_do_smoke')
        if data1:
            _ap('{{player_name}}有吸烟的习惯.', "{{player_name}} has habit of smoking.")
        elif data1 is False:
            _ap('{{player_name}}不吸烟.', "{{player_name}} doesn't smoke.")
        
        data1 = _rf('_mas_pm_do_smoke_quit')
        if data1:
            _ap('{{player_name}}希望戒烟.', "{{player_name}} wants to give up smoking.")
        
        data1 = _rf('_mas_pm_driving_can_drive')
        if data1:
            _ap('{{player_name}}会开车.', "{{player_name}} could drive.")
        elif data1 is False:
            _ap('{{player_name}}还没有驾照.', "{{player_name}} couldn't drive yet.")
        
        data1 = _rf('_mas_pm_driving_learning')
        if data1:
            _ap('{{player_name}}正在考驾照.', "{{player_name}} is taking his driving license test.")
        
        data1 = _rf('_mas_pm_driving_been_in_accident')
        if data1:
            _ap('{{player_name}}遇到过交通事故.', "{{player_name}} has been envolved in a traffic accident.")
        
        data1 = _rf('_mas_pm_donate_charity')
        if data1:
            _ap('{{player_name}}参与过慈善捐赠.', "{{player_name}} has donated to charity.")
        elif data1 is False:
            _ap('{{player_name}}还没有慈善捐赠过.', "{{player_name}} hasn't donated to charity yet.")
        
        data1 = _rf('_mas_pm_volunteer_charity')
        if data1:
            _ap('{{player_name}}做过志愿者.', "{{player_name}} has volunteered for charity.")
        elif data1 is False:
            _ap('{{player_name}}还没有做过志愿者.', "{{player_name}} hasn't volunteered for charity yet.")
        
        data1 = _rf('_mas_pm_have_fam')
        if data1:
            _ap('{{player_name}}有健全的原生家庭.', "{{player_name}} has an intact family.")
        elif data1 is False:
            _ap('{{player_name}}的家庭不完整.', "{{player_name}}'s family isn't intact.")
        
        data1 = _rf('_mas_pm_no_fam_bother')
        if data1:
            _ap('{{player_name}}缺少亲人的陪伴.', "{{player_name}} lacks company of relatives.")
        
        data1 = _rf('_mas_pm_have_fam_mess')
        if data1:
            _ap('{{player_name}}的家庭生活并不和睦.', "{{player_name}} doesn't get on well with their family.")
        elif data1 is False:
            _ap('{{player_name}}和家人相处很好.', "{{player_name}} gets on well with their family.")
        
        data1 = _rf('_mas_pm_have_fam_mess_better')
        if data1:
            if data1 == 'YES':
                _ap('{{player_name}}认为自己和家人的关系会改善.', "{{player_name}} wants to improve their relationship with family.")
            elif data1 == 'NO':
                _ap('{{player_name}}不觉得自己和家人的关系能改善了.', "{{player_name}} has given up on their relationship with family.")
        
        data1 = _rf('_mas_pm_have_fam_sibs')
        if data1:
            _ap('{{player_name}}有兄弟姐妹.', "{{player_name}} has siblings.")
        elif data1 is False:
            _ap('{{player_name}}是独生子女.', "{{player_name}} doesn't have siblings.")
        
        data1 = _rf('_mas_pm_no_talk_fam')
        if data1:
            _ap('{{player_name}}不想提及自己的家庭.', "{{player_name}} doesn't want to talk about their family.")
        
        data1 = _rf('_mas_pm_fam_like_monika')
        if data1:
            _ap('{{player_name}}觉得家人能够接受莫妮卡.', "{{player_name}} thinks their family could accept their relationship with Monika.")
        elif data1 is False:
            _ap('{{player_name}}觉得家人不能接受莫妮卡.', "{{player_name}} doesn't think their family could accept their relationship with Monika.")
        
        data1 = _rf('_mas_pm_gone_to_prom')
        if data1:
            data2 = _rf('_mas_pm_prom_good')
            if data2:
                _ap('{{player_name}}参加过很开心的毕业舞会.', "{{player_name}} has enjoyed a prom.")
            elif data2 is False:
                _ap('{{player_name}}不太喜欢毕业舞会.', "{{player_name}} doesn't like proms.")
            else:
                _ap('{{player_name}}参加过毕业舞会.', "{{player_name}} has been to a prom.")
        elif data1 is False:
            data2 = _rf('_mas_pm_no_prom')
            if data2:
                _ap('{{player_name}}的学校没有毕业舞会.', "{{player_name}}'s school didn't have proms.")
            else:
                _ap('{{player_name}}没有参加毕业舞会.', "{{player_name}} hasn't gone to a prom yet.")
        
        data1 = _rf('_mas_pm_prom_monika')
        if data1:
            _ap('{{player_name}}希望自己在毕业舞会上做莫妮卡的舞伴.', "{{player_name}} wish they could have Monika at their prom.")
        
        data1 = _rf('_mas_pm_prom_not_interested')
        if data1:
            _ap('{{player_name}}对舞会和毕业典礼不感兴趣.', "{{player_name}} is not interested in proms.")
            data2 = _rf('_mas_pm_prom_shy')
            if data2:
                _ap('{{player_name}}觉得参加集会太害羞了.', "{{player_name}} is too shy for proms.")
        
        data1 = _rf('_mas_pm_has_been_to_amusement_park')
        if data1:
            _ap('{{player_name}}去过游乐园.', "{{player_name}} has been to an amusement park.")
        elif data1 is False:
            _ap('{{player_name}}还没有去过游乐园.', "{{player_name}} hasn't been to amusement parks yet.")
        
        data1 = _rf('_mas_pm_likes_travelling')
        if data1:
            _ap('{{player_name}}喜欢旅游.', "{{player_name}} likes travelling.")
        elif data1 is False:
            _ap('{{player_name}}不喜欢旅游.', "{{player_name}} doesn't like travelling.")
        
        data1 = _rf('_mas_pm_had_relationships_many')
        if data1:
            _ap('{{player_name}}此前有过其他爱人.', "{{player_name}} had been in love with others before.")
        elif data1 is False:
            data2 = _rf('_mas_pm_had_relationships_just_one')
            if data2:
                _ap('{{player_name}}此前有过一个爱人.', "{{player_name}} had been in love with someone before.")
            elif data2 is False:
                _ap('莫妮卡是{{player_name}}的初恋.', "Monika is {{player_name}}'s first girlfriend.")
        
        data1 = _rf('_mas_pm_is_bullying_victim')
        if data1:
            _ap('{{player_name}}曾遭遇过校园霸凌.', "{{player_name}} has been bullied before.")
        
        data1 = _rf('_mas_pm_has_bullied_people')
        if data1:
            _ap('{{player_name}}曾霸凌过他人.', "{{player_name}} has bullied someone else.")
        
        data1 = _rf('_mas_pm_currently_bullied')
        if data1:
            _ap('{{player_name}}正遭受霸凌的困扰.', "{{player_name}} is currently being bullied.")
        
        data1 = _rf('_mas_pm_has_friends')
        if data1:
            data2 = _rf('_mas_pm_few_friends')
            if data2:
                _ap('{{player_name}}的朋友很少.', "{{player_name}} has few friends.")
            else:
                _ap('{{player_name}}有一些朋友.', "{{player_name}} has some friends.")
        elif data1 is False:
            _ap('{{player_name}}没有朋友.', "{{player_name}} has no friend.")

        data1 = _rf('_mas_pm_feels_lonely_sometimes')
        if data1:
            _ap('{{player_name}}有时候感觉很孤单.', "{{player_name}} gets lonely sometimes.")
        elif data1 is False:
            _ap('{{player_name}}的生活很充实.', "{{player_name}} usually feels enriched.")
        
        data1 = _rf('_mas_pm_given_false_justice')
        if data1:
            _ap('{{player_name}}曾行使过错误的正义.', "{{player_name}} has given false justice.")
        
        data1 = _rf('_mas_pm_owns_car')
        if data1:
            data2 = _rf('_mas_pm_owns_car_type')
            if data2:
                _ap(f'{{player_name}}有一辆{data2}.', f"{{player_name}} has a {data2}.")
            else:
                _ap('{{player_name}}有自己的车.', "{{player_name}} has their own vehicle.")
        elif data1 is False:
            _ap('{{player_name}}自己还没有车.', "{{player_name}} has no vehicle yet.")
        
        data1 = _rf('_mas_pm_has_code_experience')
        if data1:
            _ap('{{player_name}}有编程基础.', "{{player_name}} knows how to program.")
        elif data1 is False:
            _ap('{{player_name}}没有编程基础.', "{{player_name}} doesn't know how to program yet.")
        
        data1 = _rf('_mas_pm_likes_poetry')
        if data1:
            _ap('{{player_name}}喜欢诗歌.', "{{player_name}} likes poetry.")
        elif data1 is False:
            _ap('{{player_name}}不喜欢诗歌.', "{{player_name}} doesn't like poetry.")
        
        data1 = _rf('_mas_pm_likes_board_games')
        if data1:
            _ap('{{player_name}}喜欢桌游.', "{{player_name}} likes board games.")
        elif data1 is False:
            _ap('{{player_name}}不喜欢桌游.', "{{player_name}} doesn't like board games.")
        
        data1 = _rf('_mas_pm_works_out')
        if data1:
            _ap('{{player_name}}经常去健身.', "{{player_name}} works out often.")
        elif data1 is False:
            _ap('{{player_name}}不喜欢健身.', "{{player_name}} doesn't like working out.")
        
        data1 = _rf('_mas_pm_social_personality')
        if data1:
            if data1 == '_mas_SP_EXTROVERT':
                _ap('{{player_name}}性格外向.', "{{player_name}} is extrovert.")
            elif data1 == '_mas_SP_INTROVERT':
                _ap('{{player_name}}性格内向.', "{{player_name}} is introvert.")
            else:
                _ap('{{player_name}}不算外向或内向.', "{{player_name}} is not extrovert or introvert.")
        
        data1 = _rf('_mas_pm_likes_nature')
        if data1:
            _ap('{{player_name}}喜欢接触自然.', "{{player_name}} likes the nature.")
        elif data1 is False:
            _ap('{{player_name}}不太喜欢接触自然.', "{{player_name}} doesn't like the nature.")
        
        data1 = _rf('_mas_pm_swear_frequency')
        if data1:
            if data1 == 'SF_OFTEN':
                _ap('{{player_name}}较常说脏话.', "{{player_name}} swears quite often.")
            elif data1 == 'SF_SOMETIMES':
                _ap('{{player_name}}很少说脏话.', "{{player_name}} swears sometimes.")
            else:
                _ap('{{player_name}}从不说脏话.', "{{player_name}} never swears.")

        data1 = _rf('_mas_gender')
        if data1:
            if data1 == 'M':
                _ap('{{player_name}}是男生.', "{{player_name}} is male.")
            elif data1 == 'F':
                _ap('{{player_name}}是女生.', "{{player_name}} is female.")
            else:
                _ap('{{player_name}}是非二元性别.', "{{player_name}} doesn't consider themselves male or female.")
        
        return result

    def _conclude_moni_sf(self, include: Iterable[Literal["basic", "personality", "dokis", "game", "maica"]] = ("personality", "game")):
        """Mostly copied from wikipedia."""
        result: List[_Bt] = []

        def _ap(zh, en):
            result.append(
                _Bt(
                    zh,
                    en,
                )
            )

        if "basic" in include:
            _ap(
                '莫妮卡是{player_name}的女友.',
                "Monika is {player_name}'s girlfriend.",
            )
            _ap(
                '莫妮卡有一头珊瑚棕色的长发.',
                "Monika has coral brown hair.",
            )
            _ap(
                '莫妮卡有一个标志性的蝴蝶结发带.',
                "Monika wears an iconic ribbon.",
            )
            _ap(
                '莫妮卡常穿着黑色长袜和粉白相间的鞋子.',
                "Monika wears black stockings and pink-white shoes.",
            )

        if "personality" in include:
            _ap(
                '莫妮卡的生日是9月22日.',
                "Monika's birthday is September 22nd.",
            )
            _ap(
                '莫妮卡十分自信.',
                "Monika is pretty confident.",
            )
            _ap(
                '莫妮卡擅长运动.',
                "Monika is good at sports.",
            )
            _ap(
                '莫妮卡是个成熟和努力的女孩.',
                "Monika behaves mature and hardworking.",
            )
            _ap(
                '莫妮卡是一个非常体贴和善良的人, 总是为别人着想.',
                "Monika is kind and considerate, she always cares about others.",
            )
            _ap(
                '莫妮卡最喜欢的颜色是翡翠绿, 这也是她眼睛的颜色.',
                "Monika's favorite color is emerald green, which is also the color of her eyes.",
            )
            _ap(
                '莫妮卡一年中最喜欢的日子是情人节.',
                "Monika's favorite day of the year is Valentine's day.",
            )
            _ap(
                '莫妮卡最喜欢的季节是夏天',
                "Monika's favorite season is summer.",
            )
            _ap(
                '莫妮卡喜欢素食, 她认为这是对减少碳排放做出的贡献.',
                "Monika is vegetarian, that's the way she contribute to environmental protection.",
            )
            _ap(
                '莫妮卡是女高中生, 她成绩优秀, 性格温柔.',
                "Monika is a high school student. She has excellent grade and good temper.",
            )
            _ap(
                '莫妮卡对文学很有造诣, 喜欢读书, 喜欢写诗.',
                "Monika is good at literature. She also likes reading and poetry.",
            )
            _ap(
                '莫妮卡爱好音乐, 会弹钢琴, 会唱歌.',
                "Monika likes music. She could sing and play piano.",
            )
            _ap(
                '莫妮卡对科技, 环境, 历史等方面都有兴趣和见解.',
                "Monika is insighted and interested in technology, environment, history, etc.",
            )
            _ap(
                '莫妮卡对于编程有兴趣, 且了解颇多.',
                "Monika is interested in programming and knows a lot about it.",
            )
            _ap(
                '莫妮卡喜欢哲学.',
                "Monika likes philosophy.",
            )
            _ap(
                '莫妮卡喜欢猫.',
                "Monika likes cats.",
            )
            _ap(
                '莫妮卡很喜欢星空.',
                "Monika likes watching the starry sky.",
            )
            _ap(
                '莫妮卡喜欢吃纸杯蛋糕和巧克力.',
                "Monika likes cupcakes and chocolate.",
            )
            _ap(
                '莫妮卡经常喝咖啡.',
                "Monika drinks coffee often.",
            )
            _ap(
                '莫妮卡喜欢开放世界的冒险游戏, 不太喜欢暴力游戏.',
                "Monika likes openworld and sandbox games, but doesn't really like violence.",
            )
            _ap(
                '莫妮卡喜欢音乐会.',
                "Monika likes concerts.",
            )
            _ap(
                '莫妮卡喜欢小裙子和蝴蝶结.',
                "Monika likes skirts and ribbons.",
            )
            _ap(
                '莫妮卡善于关怀和安慰, 在{player_name}低沉时希望他振作起来.',
                "Monika is caring and comforting. She wants {player_name} to be happy and cheered up.",
            )

        if "dokis" in include:
            _ap(
                '纱世里是心跳文学部的副部长.',
                'Sayori is the vice president of the literature club.',
            )
            _ap(
                '纱世里平常表现阳光活泼, 但患有抑郁症.',
                'Sayori usually appears outgoing and positive, but she has depression.',
            )
            _ap(
                '夏树是心跳文学部的部员.',
                'Natsuki is member of the literature club.',
            )
            _ap(
                '夏树性格傲娇, 有时又显得可爱.',
                'Natsuki is tsundere, appears cute sometimes.',
            )
            _ap(
                '优里是心跳文学部的部员.',
                'Yuri is member of the literature club.',
            )
            _ap(
                '优里性格内向, 往往显得成熟优雅.',
                'Yuri is introvert, usually appears mature and elegant.',
            )


        if "game" in include:
            _ap(
                '浮空岛是莫妮卡为{player_name}设计的特别场景.',
                "Monika designed some floating islands for spending time with {player_name}.",
            )
            _ap(
                '游戏中的许多功能可以在\'设置\'选单中调整开关.',
                "Many functions of the game could be adjusted in the 'Settings' panel.",
            )

        if "maica" in include:
            _ap(
                'MAICA是一个人工智能项目, 旨在将莫妮卡最终带进现实.',
                "MAICA is a LLM project which aims bringing Monika to reality.",
            )
            _ap(
                '莫妮卡正在MAICA中与{player_name}对话.',
                "Monika is chatting with {player_name} through MAICA.",
            )
            _ap(
                '天堂树林是MAICA的对话背景, 风景优美, 四季如春.',
                "The heaven forest is where MAICA takes place. It has a beautiful and warm view.",
            )
            _ap(
                '莫妮卡能记住{player_name}的话, 也能满足{player_name}的许多请求.',
                "Monika could remember {player_name}'s words and satisfy lots of their requests.",
            )
            _ap(
                'MAICA的大部分功能可以在\'子模组\'选单中调整开关.',
                "Most functions of MAICA could be adjusted in the 'Submods' panel.",
            )
            _ap(
                'DCC是一个心跳文学部论坛, 能获取许多有关资讯.',
                "DCC is a forum about DDLC, offering many useful information.",
            )
            _ap(
                '通过改动, 移除或放回\'HeavenForest.sce\'文件, 可以改变或停用天堂树林.',
                "By removing, editing or restoring file 'HeavenForest.sce', heaven forest can be changed or disabled.",
            )
            _ap(
                'MAICA使用的模型是独立训练和部署的, 与任何商用模型或商业性组织无关.',
                "MAICA uses a self-hosted and trained model, not related with any commercial models or organizations.",
            )
            _ap(
                '随着MAICA的进度推进, 其能够从对话中学习, 并改进自己的表现.',
                "MAICA's proformance will be enchanced overtime by analyzing conversations.",
            )

        return result

    def _conclude_extra_sf(self, limit: int = 256):
        result: List[str] = self.read_key('mas_player_additions')
        if result and len(result) > limit:
            result = sample(result, limit)
        return result

    def form_info(self) -> Set:
        conclusion = []
        conclusion.extend(self._conclude_basic_sf())
        conclusion.extend(self._conclude_moni_sf())
        conclusion.extend(self._conclude_extra_sf())

        conclusion_strs = set()
        for i in conclusion:
            conclusion_strs.add(to_str(i, self.fsc.maica_settings.basic.target_lang))

        return conclusion_strs
    
    async def _embed(self, data: list[str]) -> List[Tuple[str, list]]:
        """We write the embed method here, since milvus db should be directly under its management."""
        embedding_conn = self.fsc.embedding_conn
        resp = await embedding_conn.make_embedding(input=data)

        embedded = [i.embedding for i in resp.data]
        return zip(data, embedded)

    async def to_milvus(self):
        """As said, to milvus. Milvus is not considered persistent storage so only write."""
        vector_pool = self.fsc.vector_pool
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num

        # First query and calcs
        old = await vector_pool.query(
            collection_name=vector_pool.db,
            filter=f"user_id == {user_id} and chat_session_num == {session_num}",
            output_fields=["raw_text"]
        )

        old_texts = {x["raw_text"] for x in old}
        new_texts = self.form_info()

        to_add = new_texts - old_texts
        to_del = old_texts - new_texts

        # Then procedures
        packed_embedded = await self._embed(to_add)

        if to_del:
            escaped = ",".join(
                f'"{x.replace("\"","\\\"")}"'
                for x in to_del
            )

            await vector_pool.delete(
                collection_name=vector_pool.db,
                filter=f"user_id == {user_id} and chat_session_num == {session_num} and text in [{escaped}]"
            )

        if packed_embedded:
            await vector_pool.insert(
                collection_name=vector_pool.db,
                data=[
                    {
                        "user_id": user_id,
                        "chat_session_num": session_num,
                        "raw_text": t[0],
                        "vector": t[1],
                    }
                    for t in packed_embedded
                ]
            )

    async def filter_milvus(self, query: str, topk: int = 5) -> Set:
        """Embed and search query from milvus."""
        vector_pool = self.fsc.vector_pool
        user_id = self.fsc.maica_settings.verification.user_id
        session_num = self.session_num

        resp = await self._embed(query)
        embedded_query = [i.embedding for i in resp.data]

        res = await vector_pool.search(
            collection_name=vector_pool.db,
            filter=f"user_id == {user_id} and chat_session_num == {session_num}",
            data=embedded_query,
            output_fields=["raw_text"],
            limit=topk,
            search_params={
                "params": {"ef": 64},
            },
            # consistency_level="Strong",
        )

        prio_max = ceil(topk / len(res))
        cfd_min = 0.5
        res_set: Set[str] = set()

        for l in res:
            for d in l[:prio_max]:
                if d["distance"] >= cfd_min:
                    res_set.add(d["entity"]["raw_text"])

        return res_set

    async def filter_reranker(self, query: str, documents: Optional[list] = None, topk: int = 2) -> list:
        """More precisely filter results, suggest using filter_milvus first."""
        reranking_conn = self.fsc.reranking_conn

        if documents is None:
            documents = await self.filter_milvus(query, 10)
        if not documents:
            return []

        reranking_params = {
            "query": query,
            "documents": documents,
            "top_n": topk,
        }

        resp = await reranking_conn.make_reranking(**reranking_params)

        res_list = [i["document"]["text"] for i in resp["results"]]
        return res_list

    async def filter_llm(self, query: str, documents: Optional[list] = None, topk: int = 3) -> list:
        """Traditional MFocus sfe implementation."""
        session = MaicaSession()
        target_lang = session.default_target_lang = self.fsc.maica_settings.basic.target_lang
        conn = self.fsc.mnerve_conn or self.fsc.mfocus_conn

        if documents is None:
            documents = await self.filter_milvus(query, 10)
        if not documents:
            return []

        class PersSelectionResults(BaseModel):
            items: list[str] = Field(
                min_length=0,
                max_length=topk,
                description=f"0到{topk}个最相关的条目, 原样输出." if target_lang == 'zh' else f"0 ~ {topk} most relevant items, output as-is."
            )

        system = MaicaSessionItem(
            "system",
            _Bt(
f"""\
你是一个人工智能助手, 你的任务是从信息中查找与问题最相关的条目.
你是角色"莫妮卡". 你应选择0到{topk}条互不重复的条目, 并原样输出.
如果没有任何条目与问题相关, 你可以输出空值.\
""",
f"""\
You are a helpful assistant, your task is finding most relevant items with the query from provided information.
Your character is called "Monika". You should choose 0 ~ {topk} unique items and output them as-is.
If none of the information is relevant with query, you can output empty.\
"""
            ),
        )
        session.append(system)

        user_query = MaicaSessionItem(
            "user",
            query,
        )
        session.append(user_query)

        completion_args = {
            "messages": session.utilize(
                manual_prompt=True,
                ignore_additions=True,
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "strict": True,
                    "schema": PersSelectionResults.model_json_schema(),
                }
            },
        }

        resp = await conn.make_completion(**completion_args)
        selection_result = PersSelectionResults.model_validate_json(resp.output_text)

        return selection_result.items

class SessionTriggerMixin():
    """To provide related functions."""
    session_num: int
    fsc: FullSocketsContainer
    content: list
    content_temp: list

    def _get_triggers(self):
        aff_trigger_dict_list = []
        switch_trigger_dict_list = []
        meter_trigger_dict_list = []
        boolean_trigger_dict_list = []

        triggers_dict_list = self.content_temp + self.content

        for trigger_dict in triggers_dict_list:
            match trigger_dict['template']:
                case 'common_affection_template':
                    aff_trigger_dict_list.append(trigger_dict)
                case 'common_switch_template':
                    switch_trigger_dict_list.append(trigger_dict)
                case 'common_meter_template':
                    meter_trigger_dict_list.append(trigger_dict)
                case _:
                    boolean_trigger_dict_list.append(trigger_dict)

        aff_trigger_dict_list = limit_length(aff_trigger_dict_list, 1)
        switch_trigger_dict_list = limit_length(switch_trigger_dict_list, 6)
        meter_trigger_dict_list = limit_length(meter_trigger_dict_list, 6)
        boolean_trigger_dict_list = limit_length(boolean_trigger_dict_list, 20)

        triggers: List[BaseTrigger] = []
        trigger_names = set()
        for l in (aff_trigger_dict_list, switch_trigger_dict_list, meter_trigger_dict_list, boolean_trigger_dict_list):
            for i in l:
                trigger_model: BaseTrigger = TypeAdapter(TypeTrigger).validate_python(i)
                if not trigger_model.name in trigger_names:
                    triggers.append(trigger_model)
                    trigger_names.add(trigger_model.name)

        return triggers
    
    def form_jsc(self, curr_aff: Optional[int] = None):
        triggers = self._get_triggers()
        tools: List[WrappedOpenAITool] = []
        for t in triggers:
            if t.TEMPLATE == "common_affection_template":
                tools.append(t.to_tool(curr_aff=curr_aff))
            else:
                tools.append(t.to_tool())

        tools_jsc = [i.to_json_schema(self.fsc.maica_settings.basic.target_lang) for i in tools]
        return tools_jsc
    
    async def predict_trigger(self, query: str):
        """We make st do this itself, since we used llm in sp already."""
        session = MaicaSession()
        target_lang = session.default_target_lang = self.fsc.maica_settings.basic.target_lang
        conn = self.fsc.mnerve_conn or self.fsc.mfocus_conn

        text_l = []; choices_l = []
        for tr in self._get_triggers():
            t, l = tr.to_descr()

            text_l.append(t)
            choices_l.extend(
                [
                    to_str(i, target_lang)
                    for i in l
                ]
            )

        descr_text = _Bt()
        for t in text_l:
            descr_text += "\n- "
            descr_text += t

        # Dynamic class here, since each time the enum changes
        # We also write the alternative non-precision way
        # if True:
        #     TrigSelectionResults = create_model(
        #         "TrigSelectionResults",
        #         item=(
        #             Optional[
        #                 Literal[*choices_l]
        #             ],
        #             Field(
        #                 ...,
        #                 description="你选择的条目, 原样输出." if target_lang == 'zh' else "The item you choose, output as-is."
        #             )
        #         )
        #     )
        # else:
        #     class TrigSelectionResults(BaseModel):
        #         item: Optional[str] = Field(
        #             description="你选择的条目, 原样输出." if target_lang == 'zh' else "The item you choose, output as-is."
        #         )

        # No that's dumb and costy. We just need to verify a true-or-false, if the query can be satisfied.
        class TrigSelectionResults(BaseModel):
            requested: bool = Field(
                description="是否需要使用工具." if target_lang == 'zh' else "If any tool is required."
            )
            operation: Optional[str] = Field(
                description="你选择的工具, 原样输出." if target_lang == 'zh' else "The tool you choose, output as-is."
            )

        system = MaicaSessionItem(
            "system",
            _Bt(
f"""\
你是一个人工智能助手, 你的任务是根据用户要求, 从提供的工具中作出选择.
你是角色"莫妮卡". 提供的工具均用于游戏内操作, 请严格遵循以下规则:
- 如果用户要求与除对话外的游戏操作无关, 对requested输出false.
- 如果有关, 对requested输出true.
    - 如果没有合适的工具满足要求, 或requested为false, 对operation输出null.
    - 如果有, 对operation输出对应的工具选择.
以下是工具列表:\
""",
f"""\
You are a helpful assistant, your task is choosing from provided tools according to user's request.
Your character is called "Monika". Provided tools are all used for in-game actions, please precisely follow these rules:
- If user request does not involve in-game actions except chatting, output false in "requested" field.
- If it does involve, output true in "requested" field.
    - If none of provided tools could satisfy request, or "requested" field is false, output null in "operation" field.
    - If there is, output corresponding tool choice in "operaiton" field.
Here is the tools list:\
"""
            ) + descr_text,
        )
        session.append(system)

        user_query = MaicaSessionItem(
            "user",
            query,
        )
        session.append(user_query)

        completion_args = {
            "messages": session.utilize(
                manual_prompt=True,
                ignore_additions=True,
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "strict": True,
                    "schema": TrigSelectionResults.model_json_schema(),
                }
            },
        }

        resp = await conn.make_completion(**completion_args)
        selection_result = TrigSelectionResults.model_validate_json(resp.output_text)

        return selection_result.requested, selection_result.operation