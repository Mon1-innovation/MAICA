import json
import datetime
from maica.maica_utils import *

async def weather_api_get(location):

    try:
        d = {
            "temperature": None,
            "weather": None,
            "humidity": None,
        }
        addr_code = (await get_json(f"https://restapi.amap.com/v3/geocode/geo?key={load_env('MAICA_WEATHER_KEY')}&address={location}"))['geocodes'][0]['adcode']
        result = (await get_json(f"https://restapi.amap.com/v3/weather/weatherInfo?key={load_env('MAICA_WEATHER_KEY')}&city={addr_code}&extensions=base"))['lives'][0]
        d['temperature'], d['weather'], d['humidity'] = result['temperature'], result['weather'], result['humidity']
        return d
    
    except CommonMaicaException as ce:
        raise ce
    
    except Exception as e:
        raise MaicaInternetWarning(f'Weather API returned wrong format: {str(e)}', '406')

if __name__ == '__main__':
    print(weather_api_get('黄石'))