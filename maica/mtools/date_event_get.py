import lunar_python
import datetime
import math
from typing import *
from maica.maica_utils import *

class RegEvent():

    type = None
    index = None

    def __init__(
            self,
            md: Optional[Tuple[int, int]] = None,
            lmd: Optional[Tuple[int, int]] = None,
            mwd: Optional[Tuple[int, int, int]] = None,
            name: Optional[str] = None,
            ename: Optional[str] = None,
            awareness=0,
            lasts=0,
        ):
        """
        md = (10, 1) (month & day)
        lmd = (12, 29) (lunar month & day)
        mwd = (4, 2, 3) (month & week & day) # 0 for Sunday
        Do not present to target_lang == 'en' if no ename, vice-versa

        awareness:
        1 => inform only if today
        2 => inform a day earlier
        3 => two days earlier, etc
        ... ...
        0 => no inform unless explicitly searching
        lasts indicates how long the legal vacation is, 0 for none.
        We fill this according to Chinese calendar.
        """
        if md:
            self.type = 'md'
            self.index = md
        elif lmd:
            self.type = 'lmd'
            self.index = lmd
        elif mwd:
            self.type = 'mwd'
            self.index = mwd
        self.name, self.ename, self.awareness, self.lasts = name, ename, awareness, lasts

    def __str__(self):
        return self.name or self.ename
    
    def get_solar(self, y):
        """
        Input ly if lmd, else y.
        Returns in solar.
        """
        match self.type:
            case "md":
                m, d = self.index
                solar = lunar_python.Solar.fromYmd(y, int(m), int(d))
            case "lmd":
                m, d = self.index
                solar = lunar_python.Lunar.fromYmd(y, int(m), int(d)).getSolar()
            case "mwd":
                m, w, wd = self.index
                solar_week: lunar_python.SolarWeek = lunar_python.SolarMonth.fromYm(y, int(m)).getWeeks(0)[int(w) - 1]
                solar = solar_week.getDays()[int(wd)]
        return datetime.datetime(solar.getYear(), solar.getMonth(), solar.getDay())

class EventsCollection():
    md_dict = {}
    lmd_dict = {}
    mwd_dict = {}

    @classmethod
    def _add_basic(cls, basic_events_list: list[RegEvent]):
        """This is only used once, to add all fixed events to cls in init phase."""
        for event in basic_events_list:
            ev_index = getattr(cls, f'{event.type}_dict')
            if not ev_index.get(event.index):
                ev_index[event.index] = [event]
            else:
                ev_index[event.index].append(event)

    def _add_vacations(self, dt: datetime.datetime):
        """Note that this is ONLY valid for the target date!"""

        # Caution: This function may produce wrong results under certain circumstances:
        # - Target date in early January
        # - A long lunar vacation starts from late December and ends next year
        # - The vacation days registered early this solar year are actually from next year, 
        # which differs from the correct dates specifically for lunar events

        # Why we ignore this case:
        # - It's technically impossible to happen, since Spring festival is the only lunar
        # event with a long enough vacation, which never start before Solar 1.21
        # - It will be complex to design a prevention

        # If you want to customize this function, be aware of the mentioned possibility

        all_events_list = events_list + self.flex_events_list

        for event in all_events_list:
            if event.lasts and event.lasts > 1:

                if event.type == 'lmd':
                    y = lunar_python.Solar.fromDate(dt).getLunar().getYear()
                else:
                    y = dt.year

                sdt = event.get_solar(y)

                for i in range(1, event.lasts):
                    nd = sdt + datetime.timedelta(days=i)

                    # Up to now, there's actually no compatibility of vacations out of Chinese mainland, so we just disable their enames
                    new_event = RegEvent(md=(nd.month, nd.day), name=f"{event.name}假期", ename=f"{event.ename} vacation" if False else None, awareness=1, lasts=1)
                    self.add(new_event, _vacation=True)

    def _reset_vacations(self):
        self.vac_dict_temp = {}

    def reset(self):
        self.flex_events_list = []
        self.md_dict_temp = {}
        self.lmd_dict_temp = {}
        self.mwd_dict_temp = {}
        self._reset_vacations()

    def __init__(self):
        self.reset()

    def add(self, event: RegEvent, _vacation = False):
        """Ignore the vacation param, it's only used inner."""
        ev_index = getattr(self, f'{event.type}_dict_temp') if not _vacation else self.vac_dict_temp

        if not ev_index.get(event.index):
            ev_index[event.index] = [event]
        else:
            ev_index[event.index].append(event)

    def _find_qing_ming(self, y) -> int:
        """Gets qm day."""
        d = lunar_python.Lunar.fromSolar(lunar_python.Solar.fromYmd(y, 4, 5))
        qm = d.getJieQiTable()['清明']
        return qm.getDay()
    
    def _get_last_weekday(self, y, m, wd) -> int:
        """Gets the last target weekday of a month."""
        month_last_day: lunar_python.Solar = lunar_python.SolarMonth.fromYm(y, m).getDays()[-1]
        month_last_week: lunar_python.SolarWeek = lunar_python.SolarWeek.fromYmd(month_last_day.getYear(), month_last_day.getMonth(), month_last_day.getDay(), 0)
        if len(month_last_week.getDaysInMonth()) < wd + 1:
            # So we move a week forwards
            month_last_2_week: lunar_python.SolarWeek = month_last_week.next(-1, separate_month=False)
            day: lunar_python.Solar = month_last_2_week.getDays()[wd]
        else:
            # Use last week
            day: lunar_python.Solar = month_last_week.getDays()[wd]
        return day.getDay()
    
    def _get_last_ld(self, y, m) -> int:
        """Gets the last day of a lunar month."""
        month: lunar_python.LunarMonth = lunar_python.LunarMonth.fromYm(y, m)
        return month.getDayCount()

    def search(self, dt: datetime.datetime):

        ld = lunar_python.Lunar.fromDate(dt)
        sw = lunar_python.SolarWeek.fromDate(dt, 0)
        sd = lunar_python.Solar.fromDate(dt)

        self.flex_events_list = [
            RegEvent(md=(4, self._find_qing_ming(dt.year)), name="清明节", awareness=1, lasts=1),
            RegEvent(md=(11, self._get_last_weekday(dt.year, 11, 4)), name="感恩节", ename="Thanksgiving Day", awareness=2),
            RegEvent(lmd=(12, self._get_last_ld(ld.getYear(), ld.getMonth())), name="除夕", awareness=4, lasts=1),
        ]

        self._add_vacations(dt)

        for event in self.flex_events_list:
            self.add(event)

        md_identity = (dt.month, dt.day)
        lmd_identity = (ld.getMonth(), ld.getDay())
        mwd_identity = (dt.month, sw.getIndex(), sd.getWeek())

        conclusion = []
        for results in (
            self.md_dict.get(md_identity, []),
            self.lmd_dict.get(lmd_identity, []),
            self.mwd_dict.get(mwd_identity, []),
            self.md_dict_temp.get(md_identity, []),
            self.lmd_dict_temp.get(lmd_identity, []),
            self.mwd_dict_temp.get(mwd_identity, []),
            self.vac_dict_temp.get(md_identity, []),
        ):
            conclusion.extend(results)

        self._reset_vacations()

        return conclusion

# We only want to init them once, so we writing in root
events_list = [
    # By this method we assume the festivals are all year-even, which does not fit for qm, thanksgiving, and cx
    # So we're actually adding them in the find section
    RegEvent(md=(1, 1), name="元旦", ename="New Year's Day", awareness=3, lasts=1),
    RegEvent(md=(2, 2), name="世界湿地日", ename="World Wetlands Day"),
    RegEvent(md=(2, 14), name="情人节", ename="Valentine's Day", awareness=3),
    RegEvent(md=(3, 5), name="青年志愿者服务日"),
    RegEvent(md=(3, 8), name="妇女节", ename="Women's Day", awareness=1, lasts=1),
    RegEvent(md=(3, 12), name="植树节", ename="Arbor Day", awareness=1),
    RegEvent(md=(3, 14), name="白色情人节", ename="White Day", awareness=1),
    RegEvent(md=(3, 14), name="国际警察日", ename="International Policemen' Day"),
    RegEvent(md=(3, 15), name="世界消费者权益日", ename="World Consumer Right Day"),
    RegEvent(md=(3, 21), name="世界森林日", ename="World Forest Day", awareness=1),
    RegEvent(md=(3, 21), name="世界睡眠日", ename="World Sleep Day"),
    RegEvent(md=(3, 22), name="世界水日", ename="World Water Day", awareness=1),
    RegEvent(md=(3, 23), name="世界气象日", ename="World Meteorological Day", awareness=1),
    RegEvent(md=(3, 24), name="世界防治结核病日", ename="World Tuberculosis Day"),
    RegEvent(md=(4, 1), name="愚人节", ename="April Fools' Day", awareness=2),
    # RegEvent(md=(4, 5), name="清明节", awareness=1, lasts=1),
    RegEvent(md=(4, 7), name="世界卫生日", ename="World Health Day", awareness=1),
    RegEvent(md=(4, 22), name="世界地球日", ename="World Earth Day", awareness=1),
    RegEvent(md=(4, 26), name="世界知识产权日", ename="World Intellectual Property Day"),
    RegEvent(md=(5, 1), name="劳动节", ename="Labour Day", awareness=1, lasts=1),
    RegEvent(md=(5, 3), name="世界哮喘日", ename="World Asthma Day"),
    RegEvent(md=(5, 4), name="青年节", awareness=1),
    RegEvent(md=(5, 8), name="世界红十字日", ename="World Red Cross Day", awareness=1),
    RegEvent(md=(5, 12), name="国际护士节", ename="International Nurse Day"),
    RegEvent(md=(5, 15), name="国际家庭日", ename="International Family Day"),
    RegEvent(md=(5, 17), name="世界电信日", ename="World Telecommunications Day"),
    RegEvent(md=(5, 22), name="国际生物多样性日", ename="International Biodiversity Day", awareness=1),
    RegEvent(md=(5, 23), name="国际牛奶日", ename="International Milk Day"),
    RegEvent(md=(5, 31), name="世界无烟日", ename="World No Smoking Day", awareness=1),
    RegEvent(md=(6, 1), name="儿童节", ename="Children's Day", awareness=1),
    RegEvent(md=(6, 5), name="世界环境日", ename="International Environment Day", awareness=1),
    RegEvent(md=(6, 17), name="世界防治荒漠化和干旱日", ename="World Day to combat desertification"),
    RegEvent(md=(6, 23), name="国际奥林匹克日", ename="International Olympic Day", awareness=1),
    RegEvent(md=(6, 26), name="国际禁毒日", ename="International Day Against Drug Abuse and Illicit Trafficking"),
    RegEvent(md=(7, 1), name="建党节"),
    RegEvent(md=(7, 1), name="国际建筑日", ename="International Architecture Day"),
    RegEvent(md=(7, 7), name="中国人民抗日战争纪念日"),
    RegEvent(md=(7, 11), name="世界人口日", ename="World Population Day"),
    RegEvent(md=(8, 1), name="建军节"),
    RegEvent(md=(8, 12), name="国际青年节", ename="International Youth Day", awareness=1),
    RegEvent(md=(9, 10), name="教师节", awareness=1),
    RegEvent(md=(9, 16), name="国际臭氧层保护日", ename="International Day for the Preservation of the Ozone Layer"),
    RegEvent(md=(9, 21), name="世界停火日", ename="World Ceasefire Day", awareness=1),
    RegEvent(md=(9, 27), name="世界旅游日", ename="World Tourism Day"),
    RegEvent(md=(10, 1), name="国庆节", awareness=2, lasts=7),
    RegEvent(md=(10, 1), name="国际音乐日", ename="International Music Day", awareness=1),
    RegEvent(md=(10, 1), name="国际老年人日", ename="International Day of Older Persons"),
    RegEvent(md=(10, 4), name="世界动物日", ename="World Animal Day"),
    RegEvent(md=(10, 5), name="世界教师日", ename="World Teachers' Day"),
    RegEvent(md=(10, 9), name="世界邮政日", ename="World Post Day"),
    RegEvent(md=(10, 10), name="世界精神卫生日", ename="World Mental Health Day", awareness=1),
    RegEvent(md=(10, 14), name="世界标准日", ename="World Standards Day"),
    RegEvent(md=(10, 15), name="国际盲人节", ename="International Day of the Blind"),
    RegEvent(md=(10, 16), name="世界粮食日", ename="World Food Day", awareness=1),
    RegEvent(md=(10, 17), name="国际消除贫困日", ename="International Day for the Eradication of Poverty"),
    RegEvent(md=(10, 24), name="联合国日", ename="United Nations Day"),
    RegEvent(md=(10, 24), name="世界发展新闻日", ename="World Development Information Day"),
    RegEvent(md=(10, 31), name="万圣节", ename="Halloween", awareness=2),
    RegEvent(md=(11, 8), name="中国记者节"),
    RegEvent(md=(11, 9), name="消防宣传日"),
    RegEvent(md=(11, 14), name="世界糖尿病日", ename="World Diabetes Day"),
    RegEvent(md=(11, 17), name="国际大学生节", ename="International Students' Day"),
    # RegEvent(md=(11, 24), name="感恩节", ename="Thanksgiving Day", awareness=2),
    RegEvent(md=(11, 25), name="国际消除对妇女的暴力日", ename="International Day For the elimination of Violence against Women"),
    RegEvent(md=(12, 1), name="世界爱滋病日", ename="World AIDS Day"),
    RegEvent(md=(12, 3), name="世界残疾人日", ename="World Disabled Day"),
    RegEvent(md=(12, 9), name="世界足球日", ename="World Football Day"),
    RegEvent(md=(12, 24), name="平安夜", ename="Christmas Eve", awareness=4),
    RegEvent(md=(12, 25), name="圣诞节", ename="Christmas Day", awareness=1), # We give it awareness 1 since it's just one day after awareness 2
    RegEvent(mwd=(5, 2, 0), name="母亲节", ename="Mother's Day", awareness=1),
    RegEvent(mwd=(6, 3, 0), name="父亲节", ename="Father's Day", awareness=1),
    RegEvent(mwd=(9, 3, 2), name="国际和平日", ename="International Peace Day", awareness=1),
    RegEvent(mwd=(10, 1, 1), name="世界住房日", ename="World Habitat Day"),
    RegEvent(mwd=(10, 2, 1), ename="Canadian Thanksgiving Day", awareness=1), # This is too religion specific so we don't represent it to Chinese users
    RegEvent(mwd=(10, 2, 3), name="国际减轻自然灾害日", ename="International Day for Natural Disaster Reduction"),
    RegEvent(mwd=(10, 2, 4), name="世界爱眼日", ename="World Sight Day", awareness=1),
    RegEvent(lmd=(1, 1), name="春节", ename="Chinese Spring Festival", awareness=1, lasts=7), # We give it awareness 1 since it's just one day after awareness 2
    RegEvent(lmd=(1, 15), name="元宵节", awareness=1),
    RegEvent(lmd=(5, 5), name="端午节", awareness=1),
    RegEvent(lmd=(7, 7), name="七夕节", ename="Chinese Valentine's Day", awareness=1),
    RegEvent(lmd=(8, 15), name="中秋节", awareness=1),
    RegEvent(lmd=(9, 9), name="重阳节", awareness=1),
    RegEvent(lmd=(12, 8), name="腊八节", awareness=1),
    # RegEvent(lmd=(12, 30), name="除夕", awareness=2, lasts=1),
]

EventsCollection._add_basic(events_list)

if __name__ == '__main__':

    e = EventsCollection()
    print(e._find_qing_ming(2026))
    # print(e._get_last_weekday(2025, 11, 4))
    # print(e._get_last_ld(2025, 12))
    # days = e.search(2025, 1, 31)
    # print(days)
    # for day in days:
    #     print(str(day))