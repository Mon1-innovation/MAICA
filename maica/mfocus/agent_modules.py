import asyncio
import datetime
import pytz
import json
import re
import traceback

from typing import *
from dateutil import parser
from maica.mtools import *
from maica.maica_utils import *

_Bt = BilingualText

class AgentTools():
    """Packed so more convenient."""
    def __init__(self, fsc: FullSocketsContainer, sp: SessionPersistent):
        self.fsc = fsc
        self.sp = sp

    def _time_tz(self):
        tz = self.fsc.maica_settings.basic.tz
        if not tz:
            tz = self.fsc.maica_settings.basic.target_lang

        if tz == 'zh':
            tz = "Asia/Shanghai"
        elif tz in ('en', 'auto'):
            tz = "America/Indiana/Vincennes"

        try:
            time_now = datetime.datetime.now(tz=pytz.timezone(tz))
        except Exception:
            raise MaicaInputWarning("tz not recognizable")
            
        return time_now

    async def time_acquire(self, *args, **kwargs):
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

    async def date_acquire(self, *args, **kwargs):
        """
        Gets current date.
        
        Returns:
        - text
        - raw result (datetime)
        """
        target_lang = self.fsc.maica_settings.basic.target_lang
        
        dt = self._time_tz().date()
        text = beautify_date(dt, target_lang, 'S' if self.sp.read_key('_mas_pm_live_south_hemisphere') else 'N')
        text = f"今天是{text}" if target_lang == 'zh' else f"Today is {text}"

        return text, dt

    async def weather_acquire(self, location: Optional[str] = None, *args, **kwargs):
        """
        Gets current weather.
        - location: reads from sp if not provided

        Returns:
        - text
        - raw result (dict)
        """
        target_lang = self.fsc.maica_settings.basic.target_lang

        location = location or self.sp.read_key('mas_geolocation')
        if not location:
            await messenger(self.fsc.websocket, 'maica_mfocus_geoloc_absent', "Cannot use weather tool since no geolocation provided, skipping", 404, self.fsc.tracker_id)

        try:
            weather = await weather_api_get(location)
            text = weather.to_friendly(target_lang)

        except CommonMaicaException as ce:
            text = "查询不到当前的天气." if target_lang == 'zh' else "Cannot acquire current weather."
            weather = None
            await messenger(self.fsc.websocket, 'maica_mfocus_weather_failed', tracker_id=self.fsc.rsc.tracker_id, error=ce)

        return text, weather

    async def event_acquire(self, dt_str: Optional[str] = None, *args, **kwargs):
        """
        Gets meaningful date events.
        """
        target_lang = self.fsc.maica_settings.basic.target_lang

        dt = parser.parse(dt_str) if dt_str else None

        today_dt = self._time_tz().date()
        dt = dt or today_dt

        ev_collection = EventsCollection()

        pbday = self.sp.pbday
        player_bday = (pbday[1], pbday[2]) if pbday else None

        # If you're asked "What is today" you probably just think if it's nye or birthday or what
        # But if it's "What is 3.22" and you'll think a bit more. Since it's Monika, it isn't weird that she'd know
        # it's world water day or what.
        # So, if we're searching today:
        # - We return today's awareness >= 1 events
        # - We also return tomorrow's awareness >= 2 events
        # - We can determine how many days those events should be awared in advance by awareness level

        # If we're asking a precise date that's not today, we likely don't care its following days
        # So in that case, we only return awareness >= 0 events on the exact day.

        dt_is_today = dt == today_dt
        days_to_search: List[Tuple[datetime.date, int]] = []

        if dt_is_today:
            days_to_search.append((dt, 1))
            for ext in range(1, 4):
                days_to_search.append((dt + datetime.timedelta(ext), 1 + ext))
        else:
            days_to_search.append((dt, 0))

        # Register extras
        bdays = set()
        bdays.add(RegEvent(md=(9, 22), name="莫妮卡的生日", ename="Monika's birthday", awareness=3))
        if player_bday:
            bdays.add(RegEvent(md=player_bday, name="{player_name}的生日", ename="{player_name}'s birthday", awareness=5))

        for bday in bdays:
            ev_collection.add(bday)

        # Search
        search_results = []
        for day in days_to_search:
            search_results.append(
                ev_collection.search(
                    datetime.datetime.combine(day[0], datetime.datetime.min.time())
                )
            )

        # Friendly strings
        def today_is(indice: int):
            if dt_is_today:
                match indice:
                    case 0:
                        today = _Bt(
                            "今天",
                            "Today",
                        )
                    case 1:
                        today = _Bt(
                            "明天",
                            "Tomorrow",
                        )
                    case 2:
                        today = _Bt(
                            "后天",
                            "The day after tomorrow",
                        )
                    case _:
                        today = _Bt(
                            f"{indice}天后",
                            f"{indice} days later"
                        )
            else:
                today = beautify_date(dt + datetime.timedelta(indice), target_lang, include_adj=False)
            return today
        
        def and_is(indice: int):
            """Mind the spaces here."""
            return _Bt(
                "是",
                " is ",
            ) if indice == 0 else _Bt(
                "也是",
                "and also ",
            )

        # Retrieve and filter results
        must_name = "name" if target_lang == 'zh' else "ename"
        search_results = [
            [
                event
                for event in events
                if getattr(event, must_name, None)
            ]
            for events in search_results
        ]

        text = _Bt()
        for day_index, events in enumerate(search_results):

            day_is_last = day_index + 1 == len(search_results)

            for ev_index, event in enumerate(events):

                ev_is_first = ev_index == 0
                ev_is_last = ev_index + 1 == len(events)

                if ev_is_first:
                    text += today_is(day_index)

                text += and_is(ev_index)

                text += getattr(event, must_name)

                if not ev_is_last:
                    text += ", "
                elif not day_is_last:
                    text += "; "
                else:
                    text += "."

        text = text.to_str(target_lang)
        
        if not text:
            if dt_is_today:
                text = "今天没有特殊节日或事件." if target_lang == 'zh' else "Today is not special event or holiday."
            else:
                text = f"{today_is(0)}没有特殊节日或事件." if target_lang == 'zh' else f"{today_is(0)} is not special event or holiday."

            # If called by mf_const_tools and nothing found, we suspend its prompt
            if kwargs.get("is_const"):
                search_results = None

        return text, search_results

    async def persistent_acquire(self, query: str, *args, **kwargs):
        """Gets value from persistent."""
        target_lang = self.fsc.maica_settings.basic.target_lang

        match self.fsc.real_sf_access_impl:
            case 0:
                res = await self.sp.filter_llm(query)
            case 1:
                res = await self.sp.filter_reranker(query)
            case 2:
                res = await self.sp.filter_milvus(query)

        if res:
            text = '; '.join(res)
        else:
            text = "没有找到相关记忆, 可能是没有记录." if target_lang == 'zh' else "Relevant memory not found, possibly not recorded."

        return text, res

    async def search_internet(self, query: str, org_query: Optional[str] = None, *args, **kwargs):
        """Searches result from internet."""
        text, res_m = await internet_search(self.fsc, query)

        if not text:
            res_m = None

        return text, res_m
    
    async def vista_acquire(self, query: Optional[str] = None, *args, **kwargs):
        """Gets information from image."""
        img_list = self.fsc.maica_settings.temp.mvista.mv_imgs

        if not query:
            query = _Bt(
                "简要地描述图片的整体内容",
                "Briefly summarize content of the pictures",
            )

        text = await query_vlm(self.fsc, query, img_list)

        return text, img_list

if __name__ == "__main__":
    from maica import init
    init()
    async def test():
        fsc = FullSocketsContainer()
        fsc.maica_settings.verification.user_id = 18064

        fsc.vector_pool = await ConnUtils.vector_pool()
        fsc.embedding_conn = await ConnUtils.embedding_conn()
        fsc.reranking_conn = await ConnUtils.reranking_conn()

        async with acquire_dbo("persistent", fsc) as sp:
            # await sp.to_milvus(set())

            toolbox = AgentTools(fsc, sp)
            print(fsc.real_sf_access_impl)

            print(await toolbox.persistent_acquire("用户对奶茶的看法"))

    asyncio.run(test())
