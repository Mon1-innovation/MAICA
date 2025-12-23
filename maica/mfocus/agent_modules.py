import datetime
import pytz
import json
import re
import traceback

from typing import *
from maica.mtools import *
from .mfocus_main import SfPersistentManager
from maica.maica_utils import *

class AgentTools():
    """Packed so more convenient."""
    def __init__(self, fsc: FullSocketsContainer, sf_inst: SfPersistentManager):
        self.fsc, self.sf_inst = fsc, sf_inst

    def _time_tz(self, tz="zh"):
        if tz == 'zh':
            tz = "Asia/Shanghai"
        elif tz == 'en':
            tz = "America/Indiana/Vincennes"
        try:
            time_now = datetime.datetime.now(tz=pytz.timezone(tz))
        except Exception:
            time_now = datetime.datetime.now()
        return time_now

    async def time_acquire(self, *args, **kwargs) -> tuple[str, str]:
        """Gets current time. Requires fsc."""
        target_lang = self.fsc.maica_settings.basic.target_lang
        tz = self.fsc.maica_settings.extra.tz
        time = self._time_tz(tz or target_lang)
        match time:
            case time if time.hour < 4:
                time_range = '半夜' if target_lang == 'zh' else 'at midnight'
            case time if 4 <= time.hour < 6:
                time_range = '凌晨' if target_lang == 'zh' else 'before dawn'
            case time if 6 <= time.hour < 8:
                time_range = '早上' if target_lang == 'zh' else 'at dawn'
            case time if 8 <= time.hour < 11:
                time_range = '上午' if target_lang == 'zh' else 'in morning'
            case time if 11 <= time.hour < 13:
                time_range = '中午' if target_lang == 'zh' else 'at noon'
            case time if 13 <= time.hour < 18:
                time_range = '下午' if target_lang == 'zh' else 'in afternoon'
            case time if 18 <= time.hour < 23:
                time_range = '晚上' if target_lang == 'zh' else 'at night'
            case time if 23 <= time.hour:
                time_range = '深夜' if target_lang == 'zh' else 'at midnight'
        time_friendly = f"现在是{time_range}{time.hour}点{str(time.minute).zfill(2)}分" if target_lang == 'zh' else f"It's now {str(time.hour).zfill(2)}:{str(time.minute).zfill(2)} {time_range}"
        content = f'{str(time.hour).zfill(2)}:{str(time.minute).zfill(2)}'
        return content, time_friendly

    async def date_acquire(self, *args, **kwargs) -> tuple[str, str]:
        """Gets current date. Requires fsc and sf_inst."""
        target_lang = self.fsc.maica_settings.basic.target_lang
        tz = self.fsc.maica_settings.extra.tz
        date = self._time_tz(tz or target_lang)
        weeklist = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"] if target_lang == 'zh' else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday = weeklist[date.weekday()]
        south = self.sf_inst.read_from_sf('_mas_pm_live_south_hemisphere')
        if south:
            match date:
                case date if 3 <= date.month < 6:
                    season = '秋季' if target_lang == 'zh' else 'autumn'
                case date if 6 <= date.month < 9:
                    season = '冬季' if target_lang == 'zh' else 'winter'
                case date if 9 <= date.month < 12:
                    season = '春季' if target_lang == 'zh' else 'spring'
                case date if 12 <= date.month or date.month < 3:
                    season = '夏季' if target_lang == 'zh' else 'summer'
        else:
            match date:
                case date if 3 <= date.month < 6:
                    season = '春季' if target_lang == 'zh' else 'spring'
                case date if 6 <= date.month < 9:
                    season = '夏季' if target_lang == 'zh' else 'summer'
                case date if 9 <= date.month < 12:
                    season = '秋季' if target_lang == 'zh' else 'autumn'
                case date if 12 <= date.month or date.month < 3:
                    season = '冬季' if target_lang == 'zh' else 'winter'
        date_friendly = f"今天是{date.year}年{season}{date.month}月{date.day}日{weekday}" if target_lang == 'zh' else f"Today is {date.year}.{date.month}.{date.day} {season}, {weekday}"
        content = f'{date.year}.{date.month}.{date.day}, {weekday}'
        return content, date_friendly

    async def weather_acquire(self, location: Optional[str]=None, *args, **kwargs) -> tuple[str, str]:
        """Gets current weather. Requires fsc and (sf_inst or location)."""
        target_lang = self.fsc.maica_settings.basic.target_lang
        weather = None

        if not location:
            location = self.sf_inst.read_from_sf('mas_geolocation')

        if location:
            try:
                weather = await weather_api_get(location)
                content = json.dumps(weather, ensure_ascii=False)
                weather_friendly = f"当前气温是{weather['temperature']}度, 当前天气是{weather['weather']}, 当前湿度是{weather['humidity']}%" if target_lang == 'zh' else f"Current temperature is {weather['temperature']} degrees celsius, current weather is {weather['weather']}, current humidity is {weather['humidity']} percent"
            except CommonMaicaException as ce:
                await messenger(self.fsc.rsc.websocket, 'maica_mfocus_weather_failed', traceray_id=self.fsc.rsc.traceray_id, error=ce, no_raise=True)

        if not weather:
            content = '天气未知' if target_lang == 'zh' else "Weather unknown"
            weather_friendly = content
        return content, weather_friendly

    async def event_acquire(self, *args, **kwargs: dict[str: int]) -> tuple[str, str]:
        """Gets meaningful events. Requires fsc and sf_inst, optional ymd and predict and importance."""
        target_lang = self.fsc.maica_settings.basic.target_lang
        tz = self.fsc.maica_settings.extra.tz
        time_today = self._time_tz(tz or target_lang)
        date_cursor = EventsCollection()

        date_in = []
        for k in 'year', 'month', 'day':
            date_in.append(kwargs[k] if kwargs.get(k) else getattr(time_today, k))

        try:
            player_bday = self.sf_inst.read_from_sf('mas_player_bday')
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

        # Specifically, when tnd_aggressive is set to >= 3, we enable all
        # importance levels to be represented on major day. This is not
        # recommended

        global_importance = kwargs.get('importance', 2)
        if not major_day_is_today:
            global_importance -= 2
        if self.fsc.maica_settings.extra.tnd_aggressive >= 3:
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
                case [p, t] if p and t == 'en':
                    d0_this_day = "Today"
                case [p, t] if not p and t == 'zh':
                    d0_this_day = "这一天"
                case [p, t] if not p and t == 'en':
                    d0_this_day = "This day"
            content = days_event = f"{major_day_is_today}不是特殊节日" if target_lang == 'zh' else f"{major_day_is_today} is not a special event or holiday"

        return content, days_event

    async def persistent_acquire(self, query: str, *args, **kwargs) -> tuple[str, str]:
        """Gets value from persistent. Requires fsc and sf_inst and query."""
        response_json = await self.sf_inst.mfocus_find_info(query)
        if response_json:
            content = json.dumps(response_json, ensure_ascii=False)
        else:
            content = None
        return content, response_json

    async def search_internet(self, query: str, original_query: str, location_req: Optional[str]=None, *args, **kwargs) -> tuple[str, str]:
        """Searches result from internet. Requires fsc and location_req and query and original_query, optional sf_inst."""
        if location_req:
            try:
                geolocation = self.sf_inst.read_from_sf('mas_geolocation')
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
    async def main():
        fsc = FullSocketsContainer(maica_settings=MaicaSettings())
        fsc.maica_settings.verification.update(user_id=18064, username="edge1")
        fsc.maica_settings.update(target_lang='en')
        fsc.maica_pool = await ConnUtils.maica_pool()
        fsc.mfocus_conn = await ConnUtils.mfocus_conn()
        # fsc.maica_settings.update(esc_aggressive=False)
        sf_inst = await SfPersistentManager.async_create(fsc)
        at = AgentTools(fsc, sf_inst)
        time0 = time.time()
        # res_d = asyncio.run(at.date_acquire())
        # res_e = asyncio.run(at.event_acquire(year=2025, month=10, day=1))
        res_i = await at.search_internet('24年奥运会', False, '24年奥运会在哪里')
        
        # res_p = await at.persistent_acquire('你喜欢吃什么')
        print(f'Time consumed: {time.time() - time0}')
        print(res_i)
    asyncio.run(main())