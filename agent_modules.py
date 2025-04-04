import datetime
import pytz
import json
import re
import traceback
import mfocus_sfe
from enet_scraping import internet_search
from weather_scraping import weather_api_get
from loadenv import load_env
from maica_utils import get_json

def time_tz(tz="zh"):
    if tz == 'zh':
        tz = "Asia/Shanghai"
    elif tz == 'en':
        tz = "America/Indiana/Vincennes"
    try:
        time_now = datetime.datetime.now(tz=pytz.timezone(tz))
    except:
        time_now = datetime.datetime.now()
    return time_now

async def time_acquire(params, target_lang='zh', tz=None):
    success = True
    exception = None
    time = time_tz(tz or target_lang)
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
async def date_acquire(params, sf_extraction, sf_inst, target_lang='zh', tz=None):
    success = True
    exception = None
    date = time_tz(tz or target_lang)
    weeklist = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"] if target_lang == 'zh' else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weeklist[date.weekday()]
    if sf_extraction:
        try:
            south_north = sf_inst.read_from_sf('_mas_pm_live_south_hemisphere')
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
                    content = f'{date.year}.{date.month}.{date.day}, {weekday}'
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
    content = f'{date.year}.{date.month}.{date.day}, {weekday}'
    return success, exception, content, date_friendly
async def weather_acquire(params, sf_extraction, sf_inst, target_lang='zh'):
    success = True
    exception = None
    likely_query = None
    if params:
        for possible_key in {'location', 'query', 'search', 'common'}:
            if possible_key in params:
                likely_query = params[possible_key]
                break
    try:
        if likely_query:
            weather_location = likely_query
        else:
            if sf_extraction:
                weather_location = sf_inst.read_from_sf('mas_geolocation')[2]
            else:
                content = weather_friendly = '天气未知' if target_lang == 'zh' else "Weather unknown"
        if likely_query or sf_extraction:
            got_weather = weather_api_get(weather_location)
            content = json.dumps(got_weather[2], ensure_ascii=False)
            weather_friendly = f"当前气温是{got_weather[2]['temperature']}度, 当前天气是{got_weather[2]['weather']}, 当前湿度是{got_weather[2]['humidity']}%" if target_lang == 'zh' else f"Current temperature is {got_weather[2]['temperature']} degrees celsius, current weather is {got_weather[2]['weather']}, current humidity is {got_weather[2]['humidity']} percent"
    except Exception as excepted:
        success = False
        exception = excepted
        content = weather_friendly = '天气未知' if target_lang == 'zh' else "Weather unknown"
    return success, exception, content, weather_friendly
async def event_acquire(params, sf_extraction, sf_inst, pred_length=-1, small_eves = False, target_lang='zh', tz=None):
    success = True
    exception = None
    holiday_friendly = ''
    content = ''
    time_today = time_tz(tz or target_lang)
    if not isinstance(params, dict):
        # Why didnt I consider this before
        # This is just a patch
        params = {}
    def param_limit(checkparam):
        match checkparam:
            case 'year':
                return 1000, 9999
            case 'month':
                return 1, 12
            case 'day':
                return 1, 31
            case _:
                return 0, 999999
    for checkparam in ['year', 'month', 'day']:
        if (not checkparam in params) or (not str(params[checkparam]).isdigit()) or (not param_limit(checkparam)[0] <= int(params[checkparam]) <= param_limit(checkparam)[1]):
            params[checkparam] = eval(f'time_today.{checkparam}')
    if [int(params['year']), int(params['month']), int(params['day'])] == [time_today.year, time_today.month, time_today.day]:
        is_today = True
        if not pred_length >= 0:
            pred_length = 2
    else:
        is_today = False
        if not pred_length >= 0:
            pred_length = 0
    time_instance_0 = datetime.datetime(int(params['year']), int(params['month']), int(params['day']))
    time_instance_list = []
    time_defined_list = []
    event_days_list = []
    for nextdays in range(pred_length+1):
        time_instance_list.append(time_instance_0 + datetime.timedelta(days=nextdays))
    for time_instance in time_instance_list:
        time_defined_list.append(f'{str(time_instance.year)}-{str(time_instance.month).zfill(2)}-{str(time_instance.day).zfill(2)}')
    if sf_extraction:
        try:
            player_bday = sf_inst.read_from_sf('mas_player_bday')[2]
            player_bday[0], player_bday[1], player_bday[2]
            player_has_bday = True
        except:
            player_has_bday = False
    else:
        player_has_bday = False
    time_defined_combined = ','.join(time_defined_list)
    json_res = await get_json(f"{load_env('MFOCUS_AGENT_TOOLS')}/event/api.php?date={time_defined_combined}")
    thisday = 0
    for evday in json_res:
        event_day_list = []
        thisday_instance = time_instance_0 + datetime.timedelta(days=thisday)
        thisday_defined = evday['date']
        if is_today:
            match thisday:
                case 0:
                    today = "今天" if target_lang == 'zh' else "Today"
                case 1:
                    today = "明天" if target_lang == 'zh' else "Tomorrow"
                case 2:
                    today = "后天" if target_lang == 'zh' else "The day after tomorrow"
                case _:
                    today = f"{thisday}天后" if target_lang == 'zh' else f"{thisday} days later"
        else:
            match thisday:
                case 0:
                    today = "这一天" if target_lang == 'zh' else "This day"
                case 1:
                    today = f"这一天后{thisday}天" if target_lang == 'zh' else f"{thisday} day after this day"
                case _:
                    today = f"这一天后{thisday}天" if target_lang == 'zh' else f"{thisday} days after this day"
        thisday += 1

        # Check player bday
        if player_has_bday:
            player_age = thisday_instance.year - int(player_bday[0])
            if int(thisday_instance.month) == int(player_bday[1]) and int(thisday_instance.day) == int(player_bday[2]):
                match player_age % 10:
                    case 1:
                        st_nd_rd = 'st'
                    case 2:
                        st_nd_rd = 'nd'
                    case 3:
                        st_nd_rd = 'rd'
                    case _:
                        st_nd_rd = 'th'
                bday_sentence = f"[player]的{player_age}岁生日" if target_lang == 'zh' else f"[player]'s {player_age}{st_nd_rd} birthday"
                event_day_list.append(bday_sentence)

        # Check monika bday and extendables
        match (thisday_instance.month, thisday_instance.day):
            case (9,22):
                mbday_sentence = f"莫妮卡的生日" if target_lang == 'zh' else f"Monika's birthday"
                event_day_list.append(mbday_sentence)

        # Check common events
        for desc in evday['describe']:
            if 'Start' in desc and (desc['IsNotWork'] or (thisday == 1 and small_eves)):
                evname = desc['Name'] if target_lang == 'zh' else desc['EnglishName']
                event_day_list.append(evname)

        today_is_exp = f"{today}是" if target_lang == 'zh' else f"{today} is "
        join_exp = ", 也是" if target_lang == 'zh' else ", and also "
        event_day = today_is_exp + join_exp.join(event_day_list) if len(event_day_list) else ''
        if event_day:
            event_days_list.append(event_day)
        elif thisday == 1:
            today_non_spec = f"{today}不是特殊节日" if target_lang == 'zh' else f"{today} is not a special event or holiday"
            event_days_list.append(today_non_spec)
    
    if event_days_list:
        event_days = '; '.join(event_days_list)
        return success, exception, event_days, event_days
    else:
        match [is_today, target_lang]:
            case [p, t] if p and t == 'zh':
                today_or_not = "今天"
            case [p, t] if p and t == 'en':
                today_or_not = "Today"
            case [p, t] if not p and t == 'zh':
                today_or_not = "这一天"
            case [p, t] if not p and t == 'en':
                today_or_not = "This day"
        content = "[None]"
        holiday_friendly = f"{today_or_not}不是特殊节日" if target_lang == 'zh' else f"{today_or_not} is not a special event or holiday"
    return success, exception, content, holiday_friendly
async def persistent_acquire(params, sf_extraction, session, chat_session, sf_inst, target_lang='zh'):
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
            user_id = session['user_id']
            pers_response = await sf_inst.mfocus_find_info(query)
            if pers_response[0]:
                content = pers_response[2]
                persistent_friendly = pers_response[3]
            else:
                success = False
                exception = pers_response[1]
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
async def internet_acquire(params, sf_extraction, sf_inst, original_query, esc_aggressive, target_lang='zh'):
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
            loc_caught = False
            geolocation = sf_inst.read_from_sf('mas_geolocation')
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
        search_response = await internet_search(likely_query, original_query, esc_aggressive, target_lang)
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
    import asyncio
    #print(asyncio.run(time_acquire(None)))
    #print(date_acquire(None, True, [0, 0, 23], 1))
    print(asyncio.run(event_acquire(None, True, ["0", "0", "28028"], -1, True, 'zh')))
    #print(internet_acquire({"question": "番茄炒蛋怎么做"}))
    #print(weather_acquire({}, True, [0, 0, 23], 1, 'zh'))
    #print(asyncio.run(persistent_acquire({}, True, [0, 0, 23], 1, '你是谁')))