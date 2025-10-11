import json
import datetime
import asyncio
from maica.maica_utils import *
from .api_keys import TpAPIKeys

async def weather_api_get(location):
    try:
        wkey = TpAPIKeys.GAODE_WEATHER
        d = {
            "temperature": None,
            "weather": None,
            "humidity": None,
        }
        addr_code = (await get_json(f"https://restapi.amap.com/v3/geocode/geo?key={wkey}&address={location}"))['geocodes'][0]['adcode']
        result = (await get_json(f"https://restapi.amap.com/v3/weather/weatherInfo?key={wkey}&city={addr_code}&extensions=base"))['lives'][0]
        d['temperature'], d['weather'], d['humidity'] = result['temperature'], result['weather'], result['humidity']
        return d
    
    except CommonMaicaException as ce:
        raise ce
    
    except Exception as e:
        raise MaicaInternetWarning(f'Weather API failed: {str(e)}', '406')

if __name__ == '__main__':
    from maica import init
    init()
    print(asyncio.run(weather_api_get('los angeles')))
