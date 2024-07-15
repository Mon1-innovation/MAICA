import datetime
import requests
import holidays
import json
import re
import traceback
import persistent_extraction
import mfocus_sfe
from enet_scraping import internet_search_limb
from weather_scraping import weather_api_get
def time_acquire(params):
    success = True
    exception = None
    content = datetime.datetime.now()
    match content:
        case time if time.hour < 4:
            time_friendly = f'现在是半夜{time.hour}点{str(time.minute).zfill(2)}分'
        case time if 4 <= time.hour < 7:
            time_friendly = f'现在是凌晨{time.hour}点{str(time.minute).zfill(2)}分'
        case time if 7 <= time.hour < 11:
            time_friendly = f'现在是上午{time.hour}点{str(time.minute).zfill(2)}分'
        case time if 11 <= time.hour < 13:
            time_friendly = f'现在是中午{time.hour}点{str(time.minute).zfill(2)}分'
        case time if 13 <= time.hour < 18:
            time_friendly = f'现在是下午{time.hour - 12}点{str(time.minute).zfill(2)}分'
        case time if 18 <= time.hour < 23:
            time_friendly = f'现在是晚上{time.hour - 12}点{str(time.minute).zfill(2)}分'
        case time if 23 <= time.hour:
            time_friendly = f'现在是深夜{time.hour - 12}点{str(time.minute).zfill(2)}分'

    return success, exception, content, time_friendly
def date_acquire(params, sf_extraction, session, chat_session):
    success = True
    exception = None
    content = datetime.datetime.today()
    weeklist = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weeklist[content.weekday()]
    if sf_extraction:
        try:
            user_id = session[2]
            south_north = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_live_south_hemisphere')
            if south_north[0]:
                if south_north[2]:
                    match content:
                        case date if 3 <= date.month < 6:
                            date_friendly = f"[今天是{date.year}年秋季{date.month}月{date.day}日{weekday}]"
                        case date if 6 <= date.month < 9:
                            date_friendly = f"[今天是{date.year}年冬季{date.month}月{date.day}日{weekday}]"
                        case date if 9 <= date.month < 12:
                            date_friendly = f"[今天是{date.year}年春季{date.month}月{date.day}日{weekday}]"
                        case date if 12 <= date.month or date.month < 3:
                            date_friendly = f"[今天是{date.year}年夏季{date.month}月{date.day}日{weekday}]"
                    return success, exception, content, date_friendly
        except Exception as excepted:
            exception = excepted
            # continue on failure - hemisphere may not be specified
    match content:
        case date if 3 <= date.month < 6:
            date_friendly = f"[今天是{date.year}年春季{date.month}月{date.day}日{weekday}]"
        case date if 6 <= date.month < 9:
            date_friendly = f"[今天是{date.year}年夏季{date.month}月{date.day}日{weekday}]"
        case date if 9 <= date.month < 12:
            date_friendly = f"[今天是{date.year}年秋季{date.month}月{date.day}日{weekday}]"
        case date if 12 <= date.month or date.month < 3:
            date_friendly = f"[今天是{date.year}年冬季{date.month}月{date.day}日{weekday}]"
    success = True
    return success, exception, content, date_friendly
def weather_acquire(params, sf_extraction, session, chat_session):
    success = True
    exception = None
    if sf_extraction:
        try:
            user_id = session[2]
            weather_location = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_geolocation')
            got_weather = weather_api_get(weather_location)
            content = json.dumps(got_weather[2], ensure_ascii=False)
            weather_friendly = f"当前气温是{got_weather[2]['当前温度']}度, 当前天气是{got_weather[2]['当前天气']}, 当前湿度是{got_weather[2]['当前湿度']}%"
        except Exception as excepted:
            success = False
            exception = excepted
            content = weather_friendly = '天气未知'
    else:
        content = weather_friendly = '天气未知'
    return success, exception, content, weather_friendly
def event_acquire(params, sf_extraction, session, chat_session):
    success = True
    exception = None
    holiday_friendly = ''
    content = ''
    us_holidays = holidays.US(years=datetime.date.today().year)
    cn_holidays = holidays.CN(years=datetime.date.today().year, language='zh-CN')
    tw_holidays = holidays.TW(years=datetime.date.today().year, language='zh-CN')
    time_defined = f'{str(params['year'])}-{str(params['month']).zfill(2)}-{str(params['day']).zfill(2)}'
    if sf_extraction:
        try:
            user_id = session[2]
            player_bday = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_player_bday')[2]
            player_age = params['year'] - int(player_bday[0])
            if int(params['month']) == int(player_bday[1]) and int(params['day']) == int(player_bday[2]):
                holiday_friendly += f"今天是对方的{player_age}岁生日"
                content += f"[对方的{player_age}岁生日]"
        except Exception as excepted:
            exception = excepted
            # continue on failure - birthday may not be specified
    match (int(params['month']), int(params['day'])):
        case (m, d) if m == 9 and d == 22:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "你的生日"
            content += "[你的生日]"
        case (m, d) if m == 2 and d == 14:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "情人节"
            content += "[情人节]"
        case (m, d) if m == 4 and d == 1:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "愚人节"
            content += "[愚人节]"
        case (m, d) if m == 6 and d == 1:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "儿童节"
            content += "[儿童节]"
        case (m, d) if m == 9 and d == 1:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "开学日"
            content += "[开学日]"
        case (m, d) if m == 10 and d == 31:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "万圣节"
            content += "[万圣节]"
        case (m, d) if m == 12 and d == 24:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "平安夜"
            content += "[平安夜]"
    if time_defined in cn_holidays:
        if holiday_friendly:
            holiday_friendly += ', 也是'
        else:
            holiday_friendly += '今天是'
        holiday_friendly += f"中国的{cn_holidays.get(time_defined)}"
        content += f"[{cn_holidays.get(time_defined)}]"
    elif time_defined in tw_holidays:
        if holiday_friendly:
            holiday_friendly += ', 也是'
        else:
            holiday_friendly += '今天是'
        holiday_friendly += f"中国的{tw_holidays.get(time_defined)}"
        content += f"[{tw_holidays.get(time_defined)}]"
    if time_defined in us_holidays:
        if holiday_friendly:
            holiday_friendly += ', 也是'
        else:
            holiday_friendly += '今天是'
        holiday_friendly += f"美国的{us_holidays.get(time_defined)}"
        content += f"[{us_holidays.get(time_defined)}]"
    if not content:
        content = "[None]"
        holiday_friendly = "今天不是特殊节日"
    return success, exception, content, holiday_friendly
def persistent_acquire(params, sf_extraction, session, chat_session):
    #print(params)
    success = True
    exception = None
    for possible_key in {'question', 'query', 'search'}:
        if possible_key in params:
            likely_query = params[possible_key]
            break
    if likely_query:
        query = likely_query
    if sf_extraction:
        try:
            user_id = session[2]
            content = mfocus_sfe.mfocus_find_info(user_id, chat_session, query)
            if content[0]:
                content = content[2]
            else:
                success = False
                exception = content[1]
                content = '没有相关信息'
        except Exception as excepted:
            success = False
            exception = excepted
            content = '没有相关信息'
    else:
        content = '没有相关信息'
    return success, exception, content, content
def internet_acquire(params, sf_extraction, session, chat_session):
    success = True
    exception = None
    searched_friendly = ''
    content = []
    for possible_key in {'question', 'query', 'search'}:
        if possible_key in params:
            likely_query = params[possible_key]
            break
    if not likely_query:
        success = False
        exception = 'NOQUERY'
        content = searched_friendly = '未找到结果'
    if sf_extraction:
        try:
            user_id = session[2]
            loc_caught = False
            geolocation = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_geolocation')
            if geolocation[0]:
                if geolocation[2]:
                    location = geolocation[2]
                    for location_prompt in {'地区', '周边', '附近', '周围'}:
                        if re.search(location_prompt, likely_query, re.I):
                            likely_query = re.sub(rf'{location_prompt}', rf'{location}{location_prompt}', likely_query)
                            loc_caught = True
                    if not loc_caught:
                        for locrelated_prompt in {'天气', '温度', '路况', '降雨', '霾', '店'}:
                            if re.search(locrelated_prompt, likely_query, re.I):
                                likely_query = re.sub('^', rf'{location}', likely_query)
                                break
        except Exception as excepted:
            # We just try to proceed
            pass
    try:
        print(f'Agent modules acquiring Internet search, query is:\n{likely_query}\nEnd of Internet search')
        search_response = internet_search_limb(likely_query)
        if search_response[0]:
            content = json.dumps(search_response[2], ensure_ascii=False)
            searched_friendly = search_response[3]
        else:
            raise Exception('search failed')
    except Exception as excepted:
        success = False
        exception = excepted
        return success, exception
    #content = "EMPTY"
    return success, exception, content, searched_friendly

if __name__ == "__main__":
    #print(event_acquire({"year": 2023, "month": 1, "day": 1}, True, ["0", "0", "23"], 1))
    #print(internet_acquire({"question": "番茄炒蛋怎么做"}))
    print(weather_acquire({}, True, [0, 0, 23], 1))
    #print(persistent_acquire({}, True, [0, 0, 23], 1, '你是谁'))