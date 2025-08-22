import datetime
import pytz
import json
import re
import traceback
from .enet_scraping import internet_search
from .weather_scraping import weather_api_get
from mfocus import SfBoundCoroutine
from maica_utils import *

class AgentTools():
    """I didn't intend to make classes everywhere, but they're oh so convenient."""
    def __init__(self, fsc: FullSocketsContainer, sf_inst: SfBoundCoroutine):
        self.fsc, self.sf_inst = fsc, sf_inst

    def _time_tz(tz="zh"):
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

    async def weather_acquire(self, *args: list[str], **kwargs: dict[str: str]) -> tuple[str, str]:
        """Gets current weather. Requires fsc and (sf_inst or location)."""
        location = args[0] if args else kwargs.get('location')
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
                await messenger(None, 'maica_mfocus_weather_failed', traceray_id=self.fsc.rsc.traceray_id, error=ce)

        if not weather:
            content = '天气未知' if target_lang == 'zh' else "Weather unknown"
            weather_friendly = None
        return content, weather_friendly

    async def event_acquire(self, *args, **kwargs: dict[str: int]) -> tuple[str, str]:
        """Gets meaningful events. Requires fsc and sf_inst, optional ymd and predict."""
        target_lang = self.fsc.maica_settings.basic.target_lang
        tz = self.fsc.maica_settings.extra.tz
        time_today = self._time_tz(tz or target_lang)

        date_in = []
        for k in 'year', 'month', 'day':
            date_in.append(kwargs[k] if kwargs.get(k) else getattr(time_today, k))

        try:
            player_bday = self.sf_inst.read_from_sf('mas_player_bday')
            player_bday = datetime.datetime(*vali_date(*player_bday))
        except Exception:
            player_bday = None

        d0_is_today = False
        target_date = datetime.datetime(*vali_date(*date_in))
        predict = kwargs.get('predict')
        if is_today(target_date):
            d0_is_today = True
            if predict is None:
                predict = 2
        elif predict is None:
            predict = 0

        time_query_list = []
        for next_days in range(predict + 1):
            time_query_list.append(strip_date(target_date + datetime.timedelta(days=next_days)))
        time_query = ','.join(time_query_list)

        result = await get_json(f"{load_env('MFOCUS_AGENT_TOOLS')}/event/api.php?date={time_query}")
        days_event_list = []

        day_seq = 0
        for day_result in result:
            day_seq += 1
            detailed_day = (day_seq == 1)
            very_detailed_day = (detailed_day and d0_is_today)

            if d0_is_today:
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

            day = refill_date(result['date'])
            day_event_list = []

            if player_bday:
                player_age = day.year - player_bday.year
                if (day.month, day.day) == (player_bday.month, player_bday.day):
                    # Happy birthday [player]!
                    day_event_list.append(f"[player]的{player_age}岁生日" if target_lang == 'zh' else f"[player]'s {add_seq_suffix(player_age)} birthday")

            if (day.month, day.day) == (9, 22):
                # Happy birthday Monika!
                day_event_list.append(f"莫妮卡的生日" if target_lang == 'zh' else f"Monika's birthday")

            for event in day_result['describe']:
                if (
                    event.get('IsNotWork')
                    or (event.get('Time') and detailed_day)
                    or (event.get('Name') and very_detailed_day)
                    ):
                    if not event.get('EnglishName'):
                        event['EnglishName'] = 'weekday' if event['Name'] is '工作日' else 'weekend'
                    day_event_list.append(event['Name'] if target_lang == 'zh' else event['EnglishName'])

            if day_event_list:
                today_is = f"{today}是" if target_lang == 'zh' else f"{today} is "
                joint = ", 也是" if target_lang == 'zh' else ", and also "
                day_event = today_is + joint.join(day_event_list)

                days_event_list.append(day_event)
            elif detailed_day:
                days_event_list.append(f"{today}不是特殊节日" if target_lang == 'zh' else f"{today} is not a special event or holiday")

        if days_event_list:
            content = days_event = '; '.join(days_event_list)
        else:
            match [d0_is_today, target_lang]:
                case [p, t] if p and t == 'zh':
                    d0_this_day = "今天"
                case [p, t] if p and t == 'en':
                    d0_this_day = "Today"
                case [p, t] if not p and t == 'zh':
                    d0_this_day = "这一天"
                case [p, t] if not p and t == 'en':
                    d0_this_day = "This day"
            content = days_event = f"{d0_is_today}不是特殊节日" if target_lang == 'zh' else f"{d0_is_today} is not a special event or holiday"

        return content, days_event

    async def persistent_acquire(self, *args: list[str], **kwargs: dict[str: str]) -> tuple[str, str]:
        """Gets value from persistent. Requires fsc and sf_inst and query."""
        query = args[0] if args else kwargs.get('query')
        target_lang = self.fsc.maica_settings.basic.target_lang
        response = await self.sf_inst.mfocus_find_info(query)
        if response:
            content = response
            try:
                persistent_friendly = json.loads(content)
            except Exception:
                persistent_friendly = content
        else:
            content = '没有相关信息' if target_lang == 'zh' else "No related information found"
            persistent_friendly = None
        return content, persistent_friendly

    async def search_internet(self, *args: list[str], **kwargs: dict[str: str]) -> tuple[str, str]:
        """Searches result from internet. Requires fsc and location_req and query and original_query, optional sf_inst."""
        query = args[0] if args else kwargs.get('query')
        location_req = args[1] if args else kwargs.get('location_req')
        original_query = args[2] if args else kwargs.get('original_query')
        target_lang = self.fsc.maica_settings.basic.target_lang

        if location_req:
            try:
                geolocation = self.sf_inst.read_from_sf('mas_geolocation')
            except Exception:
                geolocation = None
        if geolocation:
            query = geolocation + query
            original_query = geolocation + original_query

        try:
            result = await internet_search(self.fsc, query, original_query)
        except CommonMaicaException as ce:
            await messenger(None, 'maica_mfocus_search_failed', traceray_id=self.fsc.rsc.traceray_id, error=ce)
        return result

if __name__ == "__main__":
    import asyncio
    #print(asyncio.run(time_acquire(None)))
    # print(date_acquire(None, True, [0, 0, 23], 1))
    #print(asyncio.run(event_acquire(None, True, ["0", "0", "28028"], -1, True, 'zh')))
    #print(internet_acquire({"question": "番茄炒蛋怎么做"}))
    #print(weather_acquire({}, True, [0, 0, 23], 1, 'zh'))
    #print(asyncio.run(persistent_acquire({}, True, {'user_id': 23}, 1, '你是谁')))