import datetime
import requests
import holidays
import json
import re
import persistent_extraction
def time_acquire(params):
    success = True
    exception = None
    content = datetime.datetime.now()
    match content:
        case time if time.hour < 4:
            time_friendly = f'现在是半夜{time.hour}点{time.minute}分. '
        case time if 4 <= time.hour < 7:
            time_friendly = f'现在是凌晨{time.hour}点{time.minute}分. '
        case time if 7 <= time.hour < 11:
            time_friendly = f'现在是上午{time.hour}点{time.minute}分. '
        case time if 11 <= time.hour < 13:
            time_friendly = f'现在是中午{time.hour}点{time.minute}分. '
        case time if 13 <= time.hour < 18:
            time_friendly = f'现在是下午{time.hour - 12}点{time.minute}分. '
        case time if 18 <= time.hour < 23:
            time_friendly = f'现在是晚上{time.hour - 12}点{time.minute}分. '
        case time if 23 <= time.hour:
            time_friendly = f'现在是半夜{time.hour - 12}点{time.minute}分. '

    return success, exception, content, time_friendly
def date_acquire(params):
    success = True
    exception = None
    content = datetime.datetime.today()
    match content:
        case date if 3 <= date.month < 6:
            date_friendly = f"[今天是春季{date.year}年{date.month}月{date.day}日]"
        case date if 6 <= date.month < 9:
            date_friendly = f"[今天是夏季{date.year}年{date.month}月{date.day}日]"
        case date if 9 <= date.month < 12:
            date_friendly = f"[今天是秋季{date.year}年{date.month}月{date.day}日]"
        case date if 12 <= date.month or date.month < 3:
            date_friendly = f"[今天是冬季{date.year}年{date.month}月{date.day}日]"
    return success, exception, content, date_friendly
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
            player_age = params['year'] - player_bday.year
        except Exception as excepted:
            success = False
            exception = excepted
            return success, exception
        if params['month'] == player_bday.month and params['day'] == player_bday.day:
            holiday_friendly += f"今天是对方的{player_age}岁生日"
            content += "对方的{player_age}岁生日"
    match (int(params['month']), int(params['day'])):
        case (m, d) if m == 9 and d == 22:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "你的生日"
            content += "你的生日"
        case (m, d) if m == 2 and d == 14:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "情人节"
            content += "情人节"
        case (m, d) if m == 4 and d == 1:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "愚人节"
            content += "愚人节"
        case (m, d) if m == 6 and d == 1:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "儿童节"
            content += "儿童节"
        case (m, d) if m == 9 and d == 1:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "开学日"
            content += "开学日"
        case (m, d) if m == 10 and d == 31:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "万圣节"
            content += "万圣节"
        case (m, d) if m == 12 and d == 24:
            if holiday_friendly:
                holiday_friendly += ', 也是'
            else:
                holiday_friendly += '今天是'
            holiday_friendly += "平安夜"
            content += "平安夜"
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
def experience_acquire(params, sf_extraction, session, chat_session):
    success = True
    exception = None
    if sf_extraction:
        try:

            #some hard works to be done here

            experience_cont = params['experience']
        except Exception as excepted:
            success = False
            exception = excepted
            content = '没有相关经历'
    else:
        content = '没有相关经历'
    return success, exception, content, content
def affection_acquire(params, sf_extraction, session, chat_session):
    success = True
    exception = None
    if sf_extraction:
        try:
            user_id = session[2]
            affection_extracted = persistent_extraction.read_from_sf(user_id, chat_session, 'affection')[2]
            match affection_extracted:
                case affection if affection < 200:
                    content = '你与对方是初识的情侣关系'
                case affection if 200 <= affection < 400:
                    content = '你与对方是亲密的情侣关系'
                case affection if 400 <= affection < 700:
                    content = '你与对方是和谐的恋人关系'
                case affection if 700 <= affection < 1000:
                    content = '你与对方是情意深厚的恋人关系'
                case affection if 1000 <= affection:
                    content = '你与对方是情意至深的恋人, 足以超越虚拟与现实的隔阂'

        except Exception as excepted:
            success = False
            exception = excepted
    else:
        content = '你与对方是和谐的恋人关系'
    return success, exception, content, content
def pinfo_acquire(params, sf_extraction, session, chat_session):
    success = True
    exception = None
    if sf_extraction:
        try:
            user_id = session[2]
            info_type = params['type']
        except Exception as excepted:
            success = False
            exception = excepted
            content = 'UNKNOWN'
    else:
        content = 'UNKNOWN'
    return success, exception, content, content
def internet_acquire(params):
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
    url = f'http://192.168.3.221:5071/google/search?limit=5&lang=zh_CN&text={likely_query}'
    http_response = requests.get(url)
    if 200 <= int(http_response.status_code) <= 399:
        content_raw = http_response.text
        try:
            content_json = json.loads(content_raw)
            rank_count = 0
            for ranks in content_json:
                rank_count += 1
                description_clean = re.sub(r'[0-9]*年.*日', '', re.sub(r'转为.*网页', '', ranks['description']))
                content.append({"title": ranks['title'], "content": description_clean})
                searched_friendly += f'信息{rank_count}: {description_clean}; '
            content = json.dumps(content, ensure_ascii=False)
            searched_friendly = searched_friendly.strip(' ;')
        except Exception as excepted:
            success = False
            exception = excepted
            content = 'EMPTY'
    else:
        success = False
        exception = http_response.status_code
        content = 'EMPTY'
    #content = "EMPTY"
    return success, exception, content, searched_friendly

if __name__ == "__main__":
    #print(event_acquire({"year": 2023, "month": 2, "day": 14}, False, None, None)[3])
    print(internet_acquire({"question": "番茄炒蛋怎么做"}))