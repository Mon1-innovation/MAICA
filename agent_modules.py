import datetime
import requests
import holidays
import json
import persistent_extraction
def time_acquire(params):
    success = True
    exception = None
    content = datetime.time.now()
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
    content = datetime.date.today()
    match content:
        case date if 3 <= date.month < 6:
            date_friendly += f"[今天是春季{date.year}年{date.month}月{date.day}日]"
        case date if 6 <= date.month < 9:
            date_friendly += f"[今天是夏季{date.year}年{date.month}月{date.day}日]"
        case date if 9 <= date.month < 12:
            date_friendly += f"[今天是秋季{date.year}年{date.month}月{date.day}日]"
        case date if 12 <= date.month or date.month < 3:
            date_friendly += f"[今天是冬季{date.year}年{date.month}月{date.day}日]"
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
            player_bday = persistent_extraction.read_from_sf(user_id, chat_session, '_mas_player_bday')[2]
            player_age = params['year'] - player_bday.year
        except Exception as excepted:
            success = False
            exception = excepted
            return success, exception
        if params['month'] == player_bday.month and params['day'] == player_bday.day:
            holiday_friendly += f"今天是对方的{player_age}岁生日"
            content += "对方的{player_age}岁生日"
    match (params['month'], params['day']):
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
    return success, exception, content, holiday_friendly
def experience_acquire(params, sf_extraction, session, chat_session):
    success = True
    exception = None
    if sf_extraction:
        try:
            experience_cont = params['experience']
        except Exception as excepted:
            success = False
            exception = excepted
    else:
        content = 'EMPTY'
    return success, exception, content
def affection_acquire(params):
    success = True
    exception = None
    content = 'Love'
    return success, exception, content


if __name__ == "__main__":
    print(event_acquire({"year": 2023, "month": 12, "day": 25}, False, None, None)[3])