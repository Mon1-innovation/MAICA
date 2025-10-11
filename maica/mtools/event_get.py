
# Announcement:

# The code here is relatively simple, and have a lot of limitations
# I'm not devoting too much into this, since it's just a minor function of MAICA,
# and dealing with all these festivals and events is a massive work

# If you have corrections or improvements, I'd appreciate it a lot if you can PR
# them to me. FRs on improving this will not be considered, unless they're critical

import lunar_python
import datetime
import math
from typing import *
from maica.maica_utils import *

# lm = {
#     1: "正",
#     2: "二",
#     3: "三",
#     4: "四",
#     5: "五",
#     6: "六",
#     7: "七",
#     8: "八",
#     9: "九",
#     10: "十",
#     11: "十一",
#     12: "十二",
# }

# ld = {
#     1: "初一",
#     2: "初二",
#     3: "初三",
#     4: "初四",
#     5: "初五",
#     6: "初六",
#     7: "初七",
#     8: "初八",
#     9: "初九",
#     10: "初十",
#     11: "十一",
#     12: "十二",
#     13: "十三",
#     14: "十四",
#     15: "十五",
#     16: "十六",
#     17: "十七",
#     18: "十八",
#     19: "十九",
#     20: "二十",
#     21: "廿一",
#     22: "廿二",
#     23: "廿三",
#     24: "廿四",
#     25: "廿五",
#     26: "廿六",
#     27: "廿七",
#     28: "廿八",
#     29: "廿九",
#     30: "三十",
# }

# rlm = {v: k for k, v in lm.items()}
# rld = {v: k for k, v in ld.items()}

class RegEvent():

    type = None
    identity = None

    def __init__(self, md: Optional[str]=None, lmd: Optional[str]=None, mwd: Optional[str]=None, name: Optional[str]=None, ename: Optional[str]=None, importance=0, lasts=0):
        """
        md = 10_1 (month & day)
        lmd = 12_29 (lunar month & day)
        mwd = 4_2_3 (month & week & day) ! 0 for Sunday
        Do not present to target_lang == 'en' if no ename
        importance:
        2 => always inform
        1 => inform on target day (Monika likely cares)
        0 => no inform on tnd_aggressive
        lasts indicates how long the legal vacation is, 0 for none.
        The lasts var is only accurate for Chinese mainland.
        """
        if md:
            self.type = 'md'
            self.identity = md
        elif lmd:
            self.type = 'lmd'
            self.identity = lmd
        elif mwd:
            self.type = 'mwd'
            self.identity = mwd
        self.name, self.ename, self.importance, self.lasts = name, ename, importance, lasts

    def __str__(self):
        return self.name or self.ename
    
    def get_ymd(self, y):
        """
        Input ly if lmd, else y.
        Returns in solar.
        """
        match self.type:
            case "md":
                m, d = self.identity.split('_')
                solar = lunar_python.Solar.fromYmd(y, int(m), int(d))
            case "lmd":
                m, d = self.identity.split('_')
                solar = lunar_python.Lunar.fromYmd(y, int(m), int(d)).getSolar()
            case "mwd":
                m, w, wd = self.identity.split('_')
                solar_week: lunar_python.SolarWeek = lunar_python.SolarMonth.fromYm(y, int(m)).getWeeks(0)[int(w) - 1]
                solar = solar_week.getDays()[int(wd)]
        return solar.getYear(), solar.getMonth(), solar.getDay()

class EventsCollection():
    md_dict = {}
    lmd_dict = {}
    mwd_dict = {}

    @classmethod
    def _add_basic(cls, basic_events_list: list[RegEvent]):
        for event in basic_events_list:
            corr_dict = getattr(cls, f'{event.type}_dict')
            if not corr_dict.get(event.identity):
                corr_dict[event.identity] = [event]
            else:
                corr_dict[event.identity].append(event)

    def _add_vacations(self, y, m, d):
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

        all_events_list = events_list + self.temp_events_list
        for event in all_events_list:
            if event.lasts and event.lasts > 1:
                if event.type == 'lmd':
                    y = lunar_python.Solar.fromYmd(y, m, d).getLunar().getYear()
                sy, sm, sd = event.get_ymd(y)
                event_date = datetime.datetime(sy, sm, sd)
                for i in range(1, event.lasts):
                    new_date = event_date + datetime.timedelta(days=i)
                    new_date_str = f"{new_date.month}_{new_date.day}"

                    # Up to now, there's actually no compatibility of vacations out of Chinese mainland, so we just disable their enames
                    new_event = RegEvent(md=new_date_str, name=f"{event.name}假期", ename=f"{event.ename} vacation" if False else None, importance=1, lasts=1)
                    self._add(new_event, vac=True)

    def __init__(self):
        self._reset()

    def _reset(self):
        self.temp_events_list = []
        self.md_dict_temp = {}
        self.lmd_dict_temp = {}
        self.mwd_dict_temp = {}
        self.vac_dict_temp = {}

    def _add(self, event: RegEvent, vac=False):
        corr_dict = getattr(self, f'{event.type}_dict_temp') if not vac else self.vac_dict_temp
        if not corr_dict.get(event.identity):
            corr_dict[event.identity] = [event]
        else:
            corr_dict[event.identity].append(event)

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

    def find(self, y, m, d):
        y, m, d = int(y), int(m), int(d)

        common_date = datetime.datetime(y, m, d)
        ld = lunar_python.Lunar.fromDate(common_date)
        sw = lunar_python.SolarWeek.fromDate(common_date, 0)
        sd = lunar_python.Solar.fromDate(common_date)

        self.temp_events_list = [
            RegEvent(md=f"4_{self._find_qing_ming(y)}", name="清明节", importance=1, lasts=1),
            RegEvent(md=f"11_{self._get_last_weekday(y, 11, 4)}", name="感恩节", ename="Thanksgiving Day", importance=2),
            RegEvent(lmd=f"12_{self._get_last_ld(ld.getYear(), ld.getMonth())}", name="除夕", importance=2, lasts=1),
        ]

        self._add_vacations(y, m, d)

        for event in self.temp_events_list:
            self._add(event)

        md_identity = f"{m}_{d}"
        lmd_identity = f"{ld.getMonth()}_{ld.getDay()}"
        mwd_identity = f"{m}_{sw.getIndex()}_{sd.getWeek()}"

        conclusion = []
        conclusion.extend(self.md_dict.get(md_identity, []))
        conclusion.extend(self.lmd_dict.get(lmd_identity, []))
        conclusion.extend(self.mwd_dict.get(mwd_identity, []))
        conclusion.extend(self.md_dict_temp.get(md_identity, []))
        conclusion.extend(self.lmd_dict_temp.get(lmd_identity, []))
        conclusion.extend(self.mwd_dict_temp.get(mwd_identity, []))
        conclusion.extend(self.vac_dict_temp.get(md_identity, []))
        self._reset()

        return conclusion

# We only want to init them once, so we writing in root
events_list = [
    # By this method we assume the festivals are all year-even, which does not fit for qm, thanksgiving, and cx
    # So we're actually adding them in the find section
    RegEvent(md="1_1", name="元旦", ename="New Year's Day", importance=2, lasts=1),
    RegEvent(md="2_2", name="世界湿地日", ename="World Wetlands Day"),
    RegEvent(md="2_14", name="情人节", ename="Valentine's Day", importance=2),
    RegEvent(md="3_5", name="青年志愿者服务日"),
    RegEvent(md="3_8", name="妇女节", ename="Women's Day", lasts=1),
    RegEvent(md="3_12", name="植树节", ename="Arbor Day", importance=1),
    RegEvent(md="3_14", name="白色情人节", ename="White Day", importance=1),
    RegEvent(md="3_14", name="国际警察日", ename="International Policemen' Day"),
    RegEvent(md="3_15", name="世界消费者权益日", ename="World Consumer Right Day"),
    RegEvent(md="3_21", name="世界森林日", ename="World Forest Day", importance=1),
    RegEvent(md="3_21", name="世界睡眠日", ename="World Sleep Day"),
    RegEvent(md="3_22", name="世界水日", ename="World Water Day", importance=1),
    RegEvent(md="3_23", name="世界气象日", ename="World Meteorological Day", importance=1),
    RegEvent(md="3_24", name="世界防治结核病日", ename="World Tuberculosis Day"),
    RegEvent(md="4_1", name="愚人节", ename="April Fools' Day", importance=2),
    # RegEvent(md="4_5", name="清明节", importance=1, lasts=1),
    RegEvent(md="4_7", name="世界卫生日", ename="World Health Day", importance=1),
    RegEvent(md="4_22", name="世界地球日", ename="World Earth Day", importance=1),
    RegEvent(md="4_26", name="世界知识产权日", ename="World Intellectual Property Day"),
    RegEvent(md="5_1", name="劳动节", ename="Labour Day", importance=1, lasts=1),
    RegEvent(md="5_3", name="世界哮喘日", ename="World Asthma Day"),
    RegEvent(md="5_4", name="青年节", importance=1),
    RegEvent(md="5_8", name="世界红十字日", ename="World Red Cross Day", importance=1),
    RegEvent(md="5_12", name="国际护士节", ename="International Nurse Day"),
    RegEvent(md="5_15", name="国际家庭日", ename="International Family Day"),
    RegEvent(md="5_17", name="世界电信日", ename="World Telecommunications Day"),
    RegEvent(md="5_22", name="国际生物多样性日", ename="International Biodiversity Day", importance=1),
    RegEvent(md="5_23", name="国际牛奶日", ename="International Milk Day"),
    RegEvent(md="5_31", name="世界无烟日", ename="World No Smoking Day", importance=1),
    RegEvent(md="6_1", name="儿童节", ename="Children's Day", importance=1),
    RegEvent(md="6_5", name="世界环境日", ename="International Environment Day", importance=1),
    RegEvent(md="6_17", name="世界防治荒漠化和干旱日", ename="World Day to combat desertification"),
    RegEvent(md="6_23", name="国际奥林匹克日", ename="International Olympic Day", importance=1),
    RegEvent(md="6_26", name="国际禁毒日", ename="International Day Against Drug Abuse and Illicit Trafficking"),
    RegEvent(md="7_1", name="建党节"),
    RegEvent(md="7_1", name="国际建筑日", ename="International Architecture Day"),
    RegEvent(md="7_7", name="中国人民抗日战争纪念日"),
    RegEvent(md="7_11", name="世界人口日", ename="World Population Day"),
    RegEvent(md="8_1", name="建军节"),
    RegEvent(md="8_12", name="国际青年节", ename="International Youth Day", importance=1),
    RegEvent(md="9_10", name="教师节", importance=1),
    RegEvent(md="9_16", name="国际臭氧层保护日", ename="International Day for the Preservation of the Ozone Layer"),
    RegEvent(md="9_21", name="世界停火日", ename="World Ceasefire Day", importance=1),
    RegEvent(md="9_27", name="世界旅游日", ename="World Tourism Day"),
    RegEvent(md="10_1", name="国庆节", importance=2, lasts=7),
    RegEvent(md="10_1", name="国际音乐日", ename="International Music Day", importance=1),
    RegEvent(md="10_1", name="国际老年人日", ename="International Day of Older Persons"),
    RegEvent(md="10_4", name="世界动物日", ename="World Animal Day"),
    RegEvent(md="10_5", name="世界教师日", ename="World Teachers' Day"),
    RegEvent(md="10_9", name="世界邮政日", ename="World Post Day"),
    RegEvent(md="10_10", name="世界精神卫生日", ename="World Mental Health Day", importance=1),
    RegEvent(md="10_14", name="世界标准日", ename="World Standards Day"),
    RegEvent(md="10_15", name="国际盲人节", ename="International Day of the Blind"),
    RegEvent(md="10_16", name="世界粮食日", ename="World Food Day", importance=1),
    RegEvent(md="10_17", name="国际消除贫困日", ename="International Day for the Eradication of Poverty"),
    RegEvent(md="10_24", name="联合国日", ename="United Nations Day"),
    RegEvent(md="10_24", name="世界发展新闻日", ename="World Development Information Day"),
    RegEvent(md="10_31", name="万圣节", ename="Halloween", importance=2),
    RegEvent(md="11_8", name="中国记者节"),
    RegEvent(md="11_9", name="消防宣传日"),
    RegEvent(md="11_14", name="世界糖尿病日", ename="World Diabetes Day"),
    RegEvent(md="11_17", name="国际大学生节", ename="International Students' Day"),
    # RegEvent(md="11_24", name="感恩节", ename="Thanksgiving Day", importance=2),
    RegEvent(md="11_25", name="国际消除对妇女的暴力日", ename="International Day For the elimination of Violence against Women"),
    RegEvent(md="12_1", name="世界爱滋病日", ename="World AIDS Day"),
    RegEvent(md="12_3", name="世界残疾人日", ename="World Disabled Day"),
    RegEvent(md="12_9", name="世界足球日", ename="World Football Day"),
    RegEvent(md="12_24", name="平安夜", ename="Christmas Eve", importance=2),
    RegEvent(md="12_25", name="圣诞节", ename="Christmas Day", importance=1), # We give it importance 1 since it's just one day after importance 2
    RegEvent(mwd="5_2_0", name="母亲节", ename="Mother's Day", importance=1),
    RegEvent(mwd="6_3_0", name="父亲节", ename="Father's Day", importance=1),
    RegEvent(mwd="9_3_2", name="国际和平日", ename="International Peace Day", importance=1),
    RegEvent(mwd="10_1_1", name="世界住房日", ename="World Habitat Day"),
    RegEvent(mwd="10_2_1", ename="Canadian Thanksgiving Day", importance=1), # This is too religion specific so we don't represent it to Chinese users
    RegEvent(mwd="10_2_3", name="国际减轻自然灾害日", ename="International Day for Natural Disaster Reduction"),
    RegEvent(mwd="10_2_4", name="世界爱眼日", ename="World Sight Day", importance=1),
    RegEvent(lmd="1_1", name="春节", ename="Chinese Spring Festival", importance=1, lasts=7), # We give it importance 1 since it's just one day after importance 2
    RegEvent(lmd="1_15", name="元宵节", importance=1),
    RegEvent(lmd="5_5", name="端午节", importance=1),
    RegEvent(lmd="7_7", name="七夕节", ename="Chinese Valentine's Day", importance=1),
    RegEvent(lmd="8_15", name="中秋节", importance=1),
    RegEvent(lmd="9_9", name="重阳节", importance=1),
    RegEvent(lmd="12_8", name="腊八节", importance=1),
    # RegEvent(lmd="12_30", name="除夕", importance=2, lasts=1),
]

EventsCollection._add_basic(events_list)

if __name__ == '__main__':

    e = EventsCollection()
    print(e._find_qing_ming(2026))
    # print(e._get_last_weekday(2025, 11, 4))
    # print(e._get_last_ld(2025, 12))
    # days = e.find(2025, 1, 31)
    # print(days)
    # for day in days:
    #     print(str(day))