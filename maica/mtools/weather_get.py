import json
import datetime
import asyncio

from typing import *
from pydantic import BaseModel, Field, model_validator, ValidationError
from maica.maica_utils import *
from .api_keys import TpAPIKeys

# Data structures
class GeoResults(BaseModel):
    class GeoLoc(BaseModel):
        latitude: float
        longitude: float

    results: list[GeoLoc] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def compat_gaode(cls, data: Any):
        if isinstance(data, dict):
            if isinstance(data.get("geocodes"), list):
                data["results"] = [
                    {
                        "latitude": i["location"].split(',')[1],
                        "longitude": i["location"].split(',')[0],
                    }
                    for i in data["geocodes"]
                ]
        return data

class WeatherResults(BaseModel):
    class Current(BaseModel):
        time: datetime.datetime
        interval: int
        temperature_2m: float
        relative_humidity_2m: int
        wind_speed_10m: float

    class Forecast(BaseModel):
        time: datetime.datetime
        temperature_2m_max: float
        temperature_2m_min: float
        precipitation_probability_max: int

    current: Current
    daily: List[Forecast]
    geoloc: Optional[GeoResults.GeoLoc] = None

    @model_validator(mode="before")
    @classmethod
    def reshape_daily(cls, data: Any):
        if isinstance(data, dict):
            if isinstance(data.get("daily"), dict):

                daily = data["daily"]
                keys = [
                    "time",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                ]
                rows = [
                    dict(zip(keys, values))
                    for values in zip(*(daily[k] for k in keys))
                ]

                data["daily"] = rows

        return data
    
    def to_friendly(self, target_lang: Literal['zh', 'en', 'auto'] = 'zh'):
        _Bt = BilingualText
        l1 = _Bt(
            f"当前气温{self.current.temperature_2m}度, 相对湿度{self.current.relative_humidity_2m}%, 风速{self.current.wind_speed_10m}m/s",
            f"Current temperature is {self.current.temperature_2m} Celsius, relative humidity {self.current.relative_humidity_2m}%, wind speed {self.current.wind_speed_10m}m/s",
        )

        tmax_3 = max([i.temperature_2m_max for i in self.daily])
        tmin_3 = min([i.temperature_2m_min for i in self.daily])
        pp_max = max([i.precipitation_probability_max for i in self.daily])

        l2 = _Bt(
            f"三日内最高温{tmax_3}度, 最低温{tmin_3}度, 降雨概率约{pp_max}%",
            f"Three days' highest temperature {tmax_3} Celsius, lowest temperature {tmin_3} Celsius, precipitation probability around {pp_max}%"
        )

        friendly = l1 + "; " + l2 + "."

        return friendly.to_str(target_lang)

async def _name_to_loc(name: str):
    geo = await dld_json(
        "https://geocoding-api.open-meteo.com/v1/search",
        carriage={
            "name": name,
            "count": 1,
            "language": "zh",
        },
    )
    geo_m = GeoResults.model_validate(geo)
    return geo_m

async def _name_to_loc_gaode(name: str):
    gaode_key = TpAPIKeys.GAODE_WEATHER
    assert gaode_key, "GaoDe key not configured"

    geo = await dld_json(
        "https://restapi.amap.com/v3/geocode/geo",
        carriage={
            "address": name,
            "output": "JSON",
            "key": gaode_key,
        }
    )
    geo_m = GeoResults.model_validate(geo)
    return geo_m

async def name_to_loc(name: str):
    try:
        locs = await _name_to_loc(name)
    except Exception as e1:
        try:
            locs = await _name_to_loc_gaode(name)
        except Exception as e2:
            raise MaicaConnectionWarning(f"All geolocation apis failed for {name}: {str(e1)}; {str(e2)}")
        
    return locs

async def _loc_to_weather(loc: GeoResults.GeoLoc):
    weather = await dld_json(
        "https://api.open-meteo.com/v1/forecast",
        carriage={
            "latitude": loc.latitude,
            "longitude": loc.longitude,

            # 当前天气
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
            ],

            # 简单未来预报
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
            ],

            "forecast_days": 3,
            "timezone": "auto",
        },
    )
    weather_m = WeatherResults.model_validate(weather)
    return weather_m

async def weather_api_get(location):
    try:
        locs = await name_to_loc(location)

        loc = locs.results[0]
        weather = await _loc_to_weather(loc)
        
        weather.geoloc = loc
        return weather
    
    except CommonMaicaException as ce:
        raise ce
    
    except Exception as e:
        raise MaicaInternetWarning(f'Weather API failed: {str(e)}', '406') from e

if __name__ == '__main__':
    from maica import init
    init()
    print(asyncio.run(weather_api_get('武汉')).to_friendly())
