import time
import requests

_cache = {}
_session = requests.Session()

LAT = 40.7268
LON = -73.6343

def get_weather():
    if "data" in _cache and time.time() - _cache["time"] < 900:
        return _cache["data"]
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            f"&current_weather=true"
            f"&hourly=relative_humidity_2m,apparent_temperature"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph&forecast_days=1"
        )
        data = _session.get(url, timeout=5).json()
        cw = data["current_weather"]
        temp = cw["temperature"]
        wind = cw["windspeed"]
        # Find current hour index in the hourly arrays
        hour_str = cw.get("time", "")[:13]
        try:
            hour_index = next(i for i, t in enumerate(data["hourly"]["time"]) if t.startswith(hour_str))
        except StopIteration:
            hour_index = 0
        feels = data["hourly"]["apparent_temperature"][hour_index]
        humidity = data["hourly"]["relative_humidity_2m"][hour_index]
        result = f"{temp}°F (feels like {feels}°F), humidity {humidity}%, wind {wind}mph"
        _cache["data"] = result
        _cache["time"] = time.time()
        return result
    except Exception as e:
        return None

def get_weather_structured():
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            f"&current_weather=true"
            f"&hourly=relative_humidity_2m,apparent_temperature,uv_index"
            f"&daily=sunrise,sunset"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
            f"&timezone=America/New_York&forecast_days=1"
        )
        data = _session.get(url, timeout=5).json()
        cw   = data["current_weather"]
        hour = cw.get("time", "")[:13]
        try:
            hi = next(i for i, t in enumerate(data["hourly"]["time"]) if t.startswith(hour))
        except StopIteration:
            hi = 0
        return {
            "temp":    round(cw["temperature"]),
            "feels":   round(data["hourly"]["apparent_temperature"][hi]),
            "wind":    round(cw["windspeed"]),
            "hum":     data["hourly"]["relative_humidity_2m"][hi],
            "uv":      round(data["hourly"].get("uv_index", [0])[hi], 1),
            "cond":    cw.get("weathercode", 0),
            "sunrise": data["daily"]["sunrise"][0],
            "sunset":  data["daily"]["sunset"][0],
        }
    except Exception as e:
        return None
