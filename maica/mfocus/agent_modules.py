import datetime
import pytz
import json
import re
import traceback

from typing import *
from maica.mtools import *
from .mfocus_main import SfPersistentManager
from maica.maica_utils import *

_Bt = BilingualText

class AgentTools():
    """Packed so more convenient."""
    def __init__(self, fsc: FullSocketsContainer, sp: SessionPersistent):
        self.fsc = fsc
        self.sp = sp

    @property
    def _time_tz(self):
        tz = self.fsc.maica_settings.basic.tz

        if tz == 'zh':
            tz = "Asia/Shanghai"
        elif tz == 'en':
            tz = "America/Indiana/Vincennes"

        try:
            time_now = datetime.datetime.now(tz=pytz.timezone(tz))
        except Exception:
            raise MaicaInputWarning("tz not recognizable")
            
        return time_now

    async def time_acquire(self, *args, **kwargs) -> tuple[str, str]:
        """
        Gets current time.

        Returns:
        - text
        - raw result (datetime)
        """
        target_lang = self.fsc.maica_settings.basic.target_lang

        dt = self._time_tz()
        text = beautify_time(dt, target_lang)
        text = f"现在是{text}" if target_lang == 'zh' else f"It's now {text}"

        return text, dt

    async def date_acquire(self, *args, **kwargs) -> tuple[str, str]:
        """
        Gets current date.
        
        Returns:
        - text
        - raw result (datetime)
        """
        target_lang = self.fsc.maica_settings.basic.target_lang
        
        dt = self._time_tz()
        text = beautify_date(dt, target_lang, 'S' if self.sp.read_key('_mas_pm_live_south_hemisphere') else 'N')
        text = f"现在是{text}" if target_lang == 'zh' else f"Today is {text}"

        return text, dt

    async def weather_acquire(self, location: Optional[str]=None, *args, **kwargs) -> tuple[str, str]:
        """Gets current weather.
        - location: reads from sp if not provided

        Returns:
        - text
        - raw result (dict)
        """
        target_lang = self.fsc.maica_settings.basic.target_lang
        text = "天气未知" if target_lang == 'zh' else "Weather unknown"
        weather = None

        location = location or self.sp.read_key('mas_geolocation')
        if not location:
            await messenger(self.fsc.websocket, 'maica_mfocus_geoloc_absent', "Cannot use weather tool since no geolocation provided, skipping", '404', self.fsc.tracker_id)

        try:
            weather = await weather_api_get(location)
            text = weather.to_friendly(target_lang)

        except CommonMaicaException as ce:
            await messenger(self.fsc.websocket, 'maica_mfocus_weather_failed', tracker_id=self.fsc.rsc.tracker_id, error=ce, no_raise=True)

        return text, weather

    async def event_acquire(self, *args, **kwargs: dict[str: int]) -> tuple[str, str]:
        """Gets meaningful events. Requires fsc and sp, optional ymd and predict and importance."""
        target_lang = self.fsc.maica_settings.basic.target_lang
        tz = self.fsc.maica_settings.extra.tz
        time_today = self._time_tz()
        date_cursor = EventsCollection()

        date_in = []
        for k in 'year', 'month', 'day':
            date_in.append(kwargs[k] if kwargs.get(k) else getattr(time_today, k))

        try:
            player_bday = self.sp.read_key('mas_player_bday')
            player_bday = datetime.datetime(*vali_date(*player_bday))
        except Exception:
            player_bday = None

        major_day_is_today = False
        target_date = datetime.datetime(*vali_date(*date_in))

        predict = kwargs.get('predict')
        if is_today(target_date):
            major_day_is_today = True
            if predict is None:
                predict = 2
        elif predict is None:
            predict = 0

        # The importance mechanism:

        # When major day is today, we want to search a wider range of days, 
        # but ignore the unimportant events since they aren't cared in daily
        # lives

        # But when major day is not today, we assume that user is asking a
        # question about a percise date, so we'll dig deeper on that. The
        # following days are usually not cared about

        # Specifically, when mf_constant_tools is set to >= 3, we enable all
        # importance levels to be represented on major day. This is not
        # recommended

        global_importance = kwargs.get('importance', 2)
        if not major_day_is_today:
            global_importance -= 2
        if self.fsc.maica_settings.extra.mf_constant_tools >= 3:
            global_importance -= 1
        assert isinstance(global_importance, int), "Importance input not valid"

        days_regs_list: list[list[RegEvent]] = []
        days_events_list = []
        for next_days in range(predict + 1):

            target_next_day = target_date + datetime.timedelta(days=next_days)
            days_regs_list.append(date_cursor.find(target_next_day.year, target_next_day.month, target_next_day.day))

        day_seq = 0
        for day_regs_list in days_regs_list:
            day_seq += 1
            is_major_day = day_seq == 1
            local_importance = global_importance if (is_major_day or global_importance >= 2) else global_importance + 1

            if major_day_is_today:
                match day_seq:
                    case 1:
                        today = "今天" if target_lang == 'zh' else "Today"
                    case 2:
                        today = "明天" if target_lang == 'zh' else "Tomorrow"
                    case 3:
                        today = "后天" if target_lang == 'zh' else "The day after tomorrow"
                    case _:
                        today = f"{day_seq - 1}天后" if target_lang == 'zh' else f"{day_seq - 1} days later"
            else:
                match day_seq:
                    case 1:
                        today = "这一天" if target_lang == 'zh' else "This day"
                    case 2:
                        today = f"这一天后{day_seq - 1}天" if target_lang == 'zh' else f"{day_seq - 1} day after this day"
                    case _:
                        today = f"这一天后{day_seq - 1}天" if target_lang == 'zh' else f"{day_seq - 1} days after this day"

            day = target_date + datetime.timedelta(days = day_seq - 1)
            day_events_list = []

            # Here we determine player's bday
            if player_bday:
                player_age = day.year - player_bday.year
                if (day.month, day.day) == (player_bday.month, player_bday.day):
                    # Happy birthday [player]!
                    day_events_list.append(f"[player]的{player_age}岁生日" if target_lang == 'zh' else f"[player]'s {add_seq_suffix(player_age)} birthday")

            # Here we determine Monika's bday
            if (day.month, day.day) == (9, 22):
                # Happy birthday Monika!
                day_events_list.append(f"莫妮卡的生日" if target_lang == 'zh' else f"Monika's birthday")

            # Here we handle every reg for today
            for reg in day_regs_list:

                # We ignore the unimportant regs
                if reg.importance >= local_importance:
                    if target_lang == 'zh':
                        if reg.name:
                            day_events_list.append(reg.name)
                    else:

                        # Most Chinese traditional festivals are not registered with ename
                        # We don't add them since English users likely don't care
                        if reg.ename:
                            day_events_list.append(reg.ename)

            if day_events_list:
                today_is = f"{today}是" if target_lang == 'zh' else f"{today} is "
                joint = ", 也是" if target_lang == 'zh' else ", and also "
                day_event = today_is + joint.join(day_events_list)

                days_events_list.append(day_event)
            elif is_major_day:
                days_events_list.append(f"{today}不是特殊节日" if target_lang == 'zh' else f"{today} is not a special event or holiday")

        if days_events_list:
            content = days_event = '; '.join(days_events_list)
        else:
            match [major_day_is_today, target_lang]:
                case [p, t] if p and t == 'zh':
                    d0_this_day = "今天"
                case [p, t] if p and t != 'zh':
                    d0_this_day = "Today"
                case [p, t] if not p and t == 'zh':
                    d0_this_day = "这一天"
                case [p, t] if not p and t != 'zh':
                    d0_this_day = "This day"
            content = days_event = f"{major_day_is_today}不是特殊节日" if target_lang == 'zh' else f"{major_day_is_today} is not a special event or holiday"

        return content, days_event

    async def persistent_acquire(self, query: str, *args, **kwargs) -> tuple[str, str]:
        """Gets value from persistent. Requires fsc and sp and query."""
        info = self.sp.form_info()



        response_json = await self.sp.mfocus_find_info(query)
        if response_json:
            content = json.dumps(response_json, ensure_ascii=False)
        else:
            content = None
        return content, response_json

    async def search_internet(self, query: str, original_query: str, location_req: Optional[str]=None, *args, **kwargs) -> tuple[str, str]:
        """Searches result from internet. Requires fsc and location_req and query and original_query, optional sp."""
        if location_req:
            try:
                geolocation = self.sp.read_from_sf('mas_geolocation')
            except Exception:
                geolocation = None
        else:
            geolocation = None
        if geolocation:
            query = geolocation + query
            original_query = geolocation + original_query

        try:
            return await internet_search(self.fsc, query, original_query)
        except Exception:
            return None, None
    
    async def vista_acquire(self, img_list: list[str], query: Optional[str]=None, *args, **kwargs) -> tuple[str, str]:
        """Gets information from image. Requires fsc and img_list and query."""
        target_lang = self.fsc.maica_settings.basic.target_lang
        if not query:
            query = "简要地描述图片的整体内容" if target_lang == 'zh' else "Briefly summarize content of the pictures"

        return await query_vlm(self.fsc, query, img_list)

if __name__ == "__main__":
    import asyncio
    import time
    from maica import init
    init()
    async def test():
        fsc = FullSocketsContainer()
        fsc.maica_settings = MaicaSettings()
        fsc.maica_settings.verification.update(user_id=18064, username="edge1")
        fsc.maica_settings.update(target_lang='en')
        fsc.maica_pool = await ConnUtils.maica_pool()
        fsc.mfocus_conn = await ConnUtils.mfocus_conn()
        # fsc.maica_settings.update(esearch_llm_concl=False)
        sp = await SfPersistentManager.async_create(fsc)
        at = AgentTools(fsc, sp)
        time0 = time.time()
        # res_d = asyncio.run(at.date_acquire())
        # res_e = asyncio.run(at.event_acquire(year=2025, month=10, day=1))
        res_i = await at.search_internet('24年奥运会', False, '24年奥运会在哪里')
        
        # res_p = await at.persistent_acquire('你喜欢吃什么')
        print(f'Time consumed: {time.time() - time0}')
        print(res_i)
    asyncio.run(test())