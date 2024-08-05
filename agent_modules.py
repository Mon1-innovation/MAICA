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
def time_acquire(params, target_lang='zh'):
    success = True
    exception = None
    time = datetime.datetime.now()
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
    return success, exception, content, time_friendly
def date_acquire(params, sf_extraction, session, chat_session, target_lang='zh'):
    success = True
    exception = None
    date = datetime.datetime.today()
    weeklist = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"] if target_lang == 'zh' else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weeklist[date.weekday()]
    if sf_extraction:
        try:
            user_id = session[2]
            south_north = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_pm_live_south_hemisphere')
            if south_north[0]:
                if south_north[2]:
                    match date:
                        case date if 3 <= date.month < 6:
                            season = '秋季' if target_lang == 'zh' else 'autumn'
                        case date if 6 <= date.month < 9:
                            season = '冬季' if target_lang == 'zh' else 'winter'
                        case date if 9 <= date.month < 12:
                            season = '春季' if target_lang == 'zh' else 'spring'
                        case date if 12 <= date.month or date.month < 3:
                            season = '夏季' if target_lang == 'zh' else 'summer'
                    date_friendly = f"今天是{date.year}年{season}{date.month}月{date.day}日{weekday}" if target_lang == 'zh' else f"Today is {date.year}.{date.month}.{date.day} {season}, {weekday}"
                    content = f'{date.year}.{date.month}.{date.day}'
                    return success, exception, content, date_friendly
        except Exception as excepted:
            exception = excepted
            # continue on failure - hemisphere may not be specified
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
    content = f'{date.year}.{date.month}.{date.day}'
    return success, exception, content, date_friendly
def weather_acquire(params, sf_extraction, session, chat_session, target_lang='zh'):
    success = True
    exception = None
    likely_query = None
    if params:
        for possible_key in {'location', 'query', 'search', 'common'}:
            if possible_key in params:
                likely_query = params[possible_key]
                break
    try:
        user_id = session[2]
        if likely_query:
            weather_location = likely_query
        else:
            if sf_extraction:
                weather_location = persistent_extraction.read_from_sf(user_id, chat_session, 'mas_geolocation')[2]
            else:
                content = weather_friendly = '天气未知'
        if likely_query or sf_extraction:
            got_weather = weather_api_get(weather_location)
            content = json.dumps(got_weather[2], ensure_ascii=False)
            weather_friendly = f"当前气温是{got_weather[2]['temperature']}度, 当前天气是{got_weather[2]['weather']}, 当前湿度是{got_weather[2]['humidity']}%" if target_lang == 'zh' else f"Current temperature is {got_weather[2]['temperature']} degrees celsius, current weather is {got_weather[2]['weather']}, current humidity is {got_weather[2]['humidity']} percent"
    except Exception as excepted:
        success = False
        exception = excepted
        content = weather_friendly = '天气未知'
    return success, exception, content, weather_friendly
def event_acquire(params, sf_extraction, session, chat_session, target_lang='zh'):
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
                match player_age % 10:
                    case 1:
                        st_nd_rd = 'st'
                    case 2:
                        st_nd_rd = 'nd'
                    case 3:
                        st_nd_rd = 'rd'
                    case _:
                        st_nd_rd = 'th'
                holiday_friendly += f"今天是[player]的{player_age}岁生日" if target_lang == 'zh' else f"Today is [player]'s {player_age}{st_nd_rd} birthday"
                content += f"[今天是对方的{player_age}岁生日]" if target_lang == 'zh' else f"[Today is user's {player_age}{st_nd_rd} birthday]"
        except Exception as excepted:
            exception = excepted
            # continue on failure - birthday may not be specified
    match (int(params['month']), int(params['day'])):
        case (m, d) if m == 9 and d == 22:
            if holiday_friendly:
                holiday_friendly += ', 也是' if target_lang == 'zh' else ' and '
            else:
                holiday_friendly += '今天是' if target_lang == 'zh' else 'Today is '
            holiday_friendly += "你的生日"  if target_lang == 'zh' else "your birthday"
            content += "[今天是你的生日]" if target_lang == 'zh' else "[Today is your birthday]"
        case (m, d) if m == 2 and d == 14:
            if holiday_friendly:
                holiday_friendly += ', 也是' if target_lang == 'zh' else ' and '
            else:
                holiday_friendly += '今天是' if target_lang == 'zh' else 'Today is '
            holiday_friendly += "情人节" if target_lang == 'zh' else "Valentine's day"
            content += "[今天是情人节]" if target_lang == 'zh' else "[Today is Valentine's day]"
        case (m, d) if m == 4 and d == 1:
            if holiday_friendly:
                holiday_friendly += ', 也是' if target_lang == 'zh' else ' and '
            else:
                holiday_friendly += '今天是' if target_lang == 'zh' else 'Today is '
            holiday_friendly += "愚人节" if target_lang == 'zh' else "April fool's day"
            content += "[今天是愚人节]" if target_lang == 'zh' else "[Today is April fool's day]"
        case (m, d) if m == 6 and d == 1:
            if holiday_friendly:
                holiday_friendly += ', 也是' if target_lang == 'zh' else ' and '
            else:
                holiday_friendly += '今天是' if target_lang == 'zh' else 'Today is '
            holiday_friendly += "儿童节" if target_lang == 'zh' else "children's day"
            content += "[今天是儿童节]" if target_lang == 'zh' else "[Today is children's day]"
        case (m, d) if m == 9 and d == 1:
            if player_age <= 22:
                if holiday_friendly:
                    holiday_friendly += ', 也是' if target_lang == 'zh' else ' and '
                else:
                    holiday_friendly += '今天是' if target_lang == 'zh' else 'Today is '
                holiday_friendly += "开学日"  if target_lang == 'zh' else "the semester beginning day"
                content += "[今天是开学日]" if target_lang == 'zh' else "[Today is the semester beginning day]"
        case (m, d) if m == 10 and d == 31:
            if holiday_friendly:
                holiday_friendly += ', 也是' if target_lang == 'zh' else ' and '
            else:
                holiday_friendly += '今天是' if target_lang == 'zh' else 'Today is '
            holiday_friendly += "万圣节" if target_lang == 'zh' else "Halloween"
            content += "[今天是万圣节]" if target_lang == 'zh' else "[Today is Halloween]"
        case (m, d) if m == 12 and d == 24:
            if holiday_friendly:
                holiday_friendly += ', 也是' if target_lang == 'zh' else ' and '
            else:
                holiday_friendly += '今天是' if target_lang == 'zh' else 'Today is '
            holiday_friendly += "平安夜" if target_lang == 'zh' else "Christmas eve"
            content += "[今天是平安夜]"  if target_lang == 'zh' else "[Today is Christmas eve]"
    if time_defined in cn_holidays and target_lang == 'zh':
        if holiday_friendly:
            holiday_friendly += ', 也是'
        else:
            holiday_friendly += '今天是'
        holiday_friendly += f"中国的{cn_holidays.get(time_defined)}"
        content += f"[今天是{cn_holidays.get(time_defined)}]"
    elif time_defined in tw_holidays and target_lang == 'zh':
        if holiday_friendly:
            holiday_friendly += ', 也是'
        else:
            holiday_friendly += '今天是'
        holiday_friendly += f"中国的{tw_holidays.get(time_defined)}"
        content += f"[今天是{tw_holidays.get(time_defined)}]"
    if time_defined in us_holidays:
        if holiday_friendly:
            holiday_friendly += ', 也是'  if target_lang == 'zh' else ' and '
        else:
            holiday_friendly += '今天是' if target_lang == 'zh' else 'Today is '
        holiday_friendly += f"美国的{us_holidays.get(time_defined)}"  if target_lang == 'zh' else us_holidays.get(time_defined)
        content += f"[今天是{us_holidays.get(time_defined)}]" if target_lang == 'zh' else f"[Today is {us_holidays.get(time_defined)}]"
    if not content:
        content = "[None]"
        holiday_friendly = "今天不是特殊节日" if target_lang == 'zh' else "Today is not a special event or holiday"
    return success, exception, content, holiday_friendly
def persistent_acquire(params, sf_extraction, session, chat_session, target_lang='zh'):
    #print(params)
    success = True
    exception = None
    likely_query = None
    for possible_key in {'question', 'query', 'search', 'common'}:
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
                content = persistent_friendly = content[2]
            else:
                success = False
                exception = content[1]
                content = '没有相关信息' if target_lang == 'zh' else "No related information found"
                persistent_friendly = ''
        except Exception as excepted:
            success = False
            exception = excepted
            content = '没有相关信息' if target_lang == 'zh' else "No related information found"
            persistent_friendly = ''
    else:
        content = '没有相关信息' if target_lang == 'zh' else "No related information found"
        persistent_friendly = ''
    return success, exception, content, persistent_friendly
def internet_acquire(params, sf_extraction, session, chat_session, original_query, esc_aggressive, target_lang='zh'):
    success = True
    exception = None
    likely_query = None
    searched_friendly = ''
    content = []
    for possible_key in {'question', 'query', 'search', 'common'}:
        if possible_key in params:
            likely_query = params[possible_key]
            break
    if not likely_query:
        success = False
        exception = 'NOQUERY'
        content = '未找到结果' if target_lang == 'zh' else "No result found"
        searched_friendly = ''
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
                                likely_query = re.sub('^', rf'{location} ', likely_query)
                                break
        except Exception as excepted:
            # We just try to proceed
            pass
    try:
        print(f'Agent modules acquiring Internet search, query is:\n{likely_query}\nEnd of Internet search')
        search_response = internet_search_limb(likely_query, original_query, esc_aggressive)
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
    print(time_acquire(None))
    #print(date_acquire(None, True, [0, 0, 23], 1))
    #print(event_acquire({"year": 2023, "month": 1, "day": 1}, True, ["0", "0", "23"], 1))
    #print(internet_acquire({"question": "番茄炒蛋怎么做"}))
    #print(weather_acquire({}, True, [0, 0, 23], 1, 'zh'))
    #print(persistent_acquire({}, True, [0, 0, 23], 1, '你是谁'))