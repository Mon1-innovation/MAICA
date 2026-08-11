import asyncio
import datetime
import pytz
import json
import re
import traceback

from abc import ABC, abstractmethod
from typing import *
from dateutil import parser
from maica.mtools import *
from maica.maica_utils import *

_Bt = BilingualText
type DayFormat = Tuple[datetime.date, int]
type DaysFormat = List[DayFormat]


class AgentTools():
    """
    Packed so more convenient.
    Note: some of these tools return a list that implement agent_reparse, those can be combined and re-parsed.
    Note: all tools registered must accept **kwargs, even if not used.
    """
    class TransAdd():
        """Correctly adding."""
        def __add__(self, other):
            add_res = super().__add__(other)
            new_add_res = self.__class__(add_res)

            for possible_attr in (
                "target_lang",
                "reference_date",
                "mark_true",
            ):
                if hasattr(self, possible_attr):
                    setattr(new_add_res, possible_attr, (
                        getattr(other, possible_attr, None)
                        or getattr(self, possible_attr, None)
                    ))

            return new_add_res

    class Reparsable(ABC, TransAdd):
        """
        Result classes inherit from this mixin to enable overlapping.

        Currently using:
        - event_acquire
        - persistent_acquire
        - search_internet
        - vista_acquire
        """

        @abstractmethod
        def agent_reparse():
            ...

    class MarkableBool():
        """
        Result classes inherit from this mixin to enable force displaying.
        
        Currently using:
        - event_acquire
        """
        mark_true = False

        def __bool__(self):
            if self.mark_true:
                return True
            else:
                return super().__bool__()

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
        - raw result (pyd model)
        """
        target_lang = self.fsc.maica_settings.basic.target_lang

        try:
            location = location or self.sp.read_key('mas_geolocation')
            if not location:
                raise MaicaInputWarning("Cannot use weather tool since no geolocation provided, skipping")

            weather = await weather_api_get(location)
            text = weather.to_friendly(target_lang)

        except CommonMaicaException as ce:
            text = "查询不到当前的天气." if target_lang == 'zh' else "Cannot acquire current weather."
            weather = None
            await self.fsc.messenger('maica_mfocus_weather_failed', error=ce)

        return text, weather

    class AgentEvents(Reparsable, MarkableBool, List[
            Tuple[
                DayFormat, list
            ]
        ]
    ):
        target_lang: TargetLangType = "zh"
        reference_date: Optional[datetime.date] = None

        def __bool__(self):
            return self.mark_true or any(i[1] for i in self)
        
        def agent_reparse(self):
            target_lang = self.target_lang
            must_name = "name" if target_lang == 'zh' else "ename"

            search_results = self
            reference_date = self.reference_date or datetime.date.today()
            dt_is_today = any(i[0][0] == reference_date for i in search_results)

            # Friendly strings
            def today_is(dt: datetime.date):
                indice = (dt - reference_date).days

                if dt_is_today and 0 <= indice < 7:
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
                    today = beautify_date(dt, target_lang, include_adj=False)
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

            # Filter the duplications here
            days_dict: Dict[
                Tuple[int, int, int],
                List,
            ] = {}

            days_to_remove = set()
            for day_index, (day, events) in enumerate(search_results):
                # This is for day-in-range level deduplication
                day_date = day[0]
                day_ymd = (day_date.year, day_date.month, day_date.day)

                if day_ymd in days_dict:
                    days_dict[day_ymd] += events
                    days_to_remove.add(day_index)
                else:
                    days_dict[day_ymd] = events

            for i in sorted(days_to_remove, reverse=True):
                self.pop(i)

            for events in days_dict.values():
                # This is for event-in-day level deduplication
                events_exist = set()
                events_pop = set()

                for index, event in enumerate(events):
                    if (event_name := getattr(event, must_name)) in events_exist:
                        events_pop.add(index)
                    else:
                        events_exist.add(event_name)

                for i in sorted(list(events_pop), reverse=True):
                    events.pop(i)

            # And sort
            self.sort(key = lambda x: x[0][0])
            
            text = _Bt()

            for day_index, (day, events) in enumerate(search_results):

                dt = day[0]
                day_is_last = day_index + 1 == len(search_results)

                for ev_index, event in enumerate(events):

                    ev_is_first = ev_index == 0
                    ev_is_last = ev_index + 1 == len(events)

                    if ev_is_first:
                        text += today_is(dt)

                    text += and_is(ev_index)

                    text += getattr(event, must_name)

                    if not ev_is_last:
                        text += ", "
                    elif not day_is_last:
                        text += "; "
                    else:
                        text += "."
            
            if not text:
                if dt_is_today:
                    text = _Bt(
                        "今天没有特殊节日或事件.",
                        "Today is not special event or holiday.",
                    )
                else:
                    text = _Bt(
                        "该日期没有特殊节日或事件.",
                        "This date is not special event or holiday.",
                    )

            text = text.to_str(target_lang)
            return text

    async def event_acquire(self, dt_str: Optional[str] = None, *args, **kwargs):
        """
        Gets meaningful date events.
        """
        target_lang = self.fsc.maica_settings.basic.target_lang

        dt = parser.parse(dt_str).date() if dt_str else None

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
        days_to_search: DaysFormat = []

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
        search_results = self.AgentEvents()
        search_results.target_lang = target_lang
        search_results.reference_date = today_dt

        must_name = "name" if target_lang == 'zh' else "ename"

        for day in days_to_search:
            search_results.append(
                (
                    day,
                    ev_collection.search(*day, must_name=must_name)
                )
            )

        text = search_results.agent_reparse()

        if kwargs.get("force_disp"):
            search_results.mark_true = True

        return text, search_results

    class AgentPersistents(Reparsable, list[str]):
        target_lang: TargetLangType = "zh"

        def agent_reparse(self):
            target_lang = self.target_lang
            res = [i.strip('. ') for i in self]
            res[:] = list(dict.fromkeys(res))

            if res:
                text = '; '.join(res)
                instruction_text = _Bt(
                    "来自存档的查询结果(仅供参考, 不要逐字照抄): ",
                    "Persistent search results (for reference, do not copy word for word): ",
                )
                text = instruction_text + text

            else:
                text = _Bt(
                    "没有找到相关记忆, 可能是没有记录.",
                    "Relevant memory not found, possibly not recorded.",
                )

            text = text.to_str(target_lang)
            return text

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

        res = self.AgentPersistents(res)
        res.target_lang = target_lang

        text = res.agent_reparse()

        return text, res

    class AgentInternets(Reparsable, list[str]):
        target_lang: TargetLangType = "zh"

        def agent_reparse(self):
            target_lang = self.target_lang
            res = [i.strip('. ') for i in self]
            res[:] = list(dict.fromkeys(res))

            if res:
                text = '; '.join(res)
                instruction_text = _Bt(
                    "来自互联网的搜索结果(仅供参考, 不要逐字照抄): ",
                    "Internet search results (for reference, do not copy word for word): ",
                )
                text = instruction_text + text

            else:
                text = _Bt(
                    "未搜索到相关信息.",
                    "No relevant information found.",
                )

            text = text.to_str(target_lang)
            return text

    async def search_internet(self, query: str, org_query: Optional[str] = None, *args, **kwargs):
        """Searches result from internet."""
        target_lang = self.fsc.maica_settings.basic.target_lang
        res = await internet_search(self.fsc, query)

        res = self.AgentInternets(res)
        res.target_lang = target_lang

        text = res.agent_reparse()

        return text, res

    class AgentVistas(Reparsable, list[str]):
        target_lang: TargetLangType = "zh"

        def agent_reparse(self):
            target_lang = self.target_lang
            res = [i.strip('. ') for i in self]
            res[:] = list(dict.fromkeys(res))

            if res:
                text = '; '.join(res)
                instruction_text = _Bt(
                    "来自图片的检视结果(仅供参考, 不要逐字照抄): ",
                    "Image observation results (for reference, do not copy word for word): ",
                )
                text = instruction_text + text

            else:
                text = _Bt(
                    "没有图片与问题相关.",
                    "No image is related with query.",
                )

            text = text.to_str(target_lang)
            return text

    async def vista_acquire(self, query: Optional[str] = None, *args, **kwargs):
        """Gets information from image."""
        img_list = self.fsc.maica_settings.temp.mvista.mv_imgs

        if not query:
            query = _Bt(
                "简要地描述图片的整体内容",
                "Briefly summarize content of the pictures",
            )

        text = await query_vlm(self.fsc, query, img_list)

        res = self.AgentVistas([text])
        res.target_lang = self.fsc.maica_settings.basic.target_lang

        text = res.agent_reparse()

        return text, res

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
            # await sp.to_vector(set())

            toolbox = AgentTools(fsc, sp)
            print(fsc.real_sf_access_impl)

            print(await toolbox.persistent_acquire("用户对奶茶的看法"))

    asyncio.run(test())
