import json
import datetime
import requests
from maica_utils import *

def weather_api_get(location):
    success = False
    r = requests.get(f"https://restapi.amap.com/v3/geocode/geo?key={load_env('WEATHER_KEY')}&address={location}")
    if not 200 <= int(r.status_code) < 400:
        excepted = r.status_code
        return success, excepted, None
    else:
        json_res = json.loads(r.content.decode('utf-8'))
        adcode = json_res['geocodes'][0]['adcode']
        r2 = requests.get(f"https://restapi.amap.com/v3/weather/weatherInfo?key={load_env('WEATHER_KEY')}&city={adcode}&extensions=base")
        if not 200 <= int(r2.status_code) < 400:
            excepted = r2.status_code
            return success, excepted, None
        else:
            json_res2 = json.loads(r2.content.decode('utf-8'))
            return_val = {}
            return_val['temperature'] = json_res2['lives'][0]['temperature']
            return_val['weather'] = json_res2['lives'][0]['weather']
            return_val['humidity'] = json_res2['lives'][0]['humidity']
            success = True
            return success, None, return_val


if __name__ == '__main__':
    print(weather_api_get('黄石'))