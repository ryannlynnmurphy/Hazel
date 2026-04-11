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

WMO_CODES = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Severe thunderstorm",
}

WMO_ICONS = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌧️", 55: "🌧️",
    61: "🌦️", 63: "🌧️", 65: "🌧️",
    66: "🌧️", 67: "🌧️",
    71: "🌨️", 73: "❄️", 75: "❄️", 77: "❄️",
    80: "🌦️", 81: "🌧️", 82: "⛈️",
    85: "🌨️", 86: "🌨️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}

def _night_icon(code, hour_index, sunrise_h, sunset_h):
    """Swap sun icons for moon icons at night."""
    if hour_index < sunrise_h or hour_index >= sunset_h:
        return {0: "🌙", 1: "🌙", 2: "☁️"}.get(code, WMO_ICONS.get(code, "🌙"))
    return WMO_ICONS.get(code, "☀️")

def get_weather_structured():
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            f"&current_weather=true"
            f"&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,uv_index,weathercode"
            f"&daily=sunrise,sunset"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
            f"&timezone=America/New_York&forecast_days=2"
        )
        data = _session.get(url, timeout=5).json()
        cw   = data["current_weather"]
        hour = cw.get("time", "")[:13]
        try:
            hi = next(i for i, t in enumerate(data["hourly"]["time"]) if t.startswith(hour))
        except StopIteration:
            hi = 0

        code = cw.get("weathercode", 0)

        # Parse sunrise/sunset hour for day/night icon logic
        sunrise_h = int(data["daily"]["sunrise"][0].split("T")[1].split(":")[0])
        sunset_h = int(data["daily"]["sunset"][0].split("T")[1].split(":")[0])

        # Build hourly forecast (next 8 hours from now)
        hourly_times = data["hourly"]["time"]
        hourly_temps = data["hourly"]["temperature_2m"]
        hourly_codes = data["hourly"].get("weathercode", [])
        hourly = []
        for i in range(hi, min(hi + 8, len(hourly_times))):
            t = hourly_times[i]
            h = int(t.split("T")[1].split(":")[0])
            label = "Now" if i == hi else f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"
            hcode = hourly_codes[i] if i < len(hourly_codes) else 0
            hourly.append({
                "label": label,
                "temp": round(hourly_temps[i]),
                "icon": _night_icon(hcode, h, sunrise_h, sunset_h),
            })

        return {
            "temp":    round(cw["temperature"]),
            "feels":   round(data["hourly"]["apparent_temperature"][hi]),
            "wind":    round(cw["windspeed"]),
            "hum":     data["hourly"]["relative_humidity_2m"][hi],
            "uv":      round(data["hourly"].get("uv_index", [0])[hi], 1),
            "cond":    WMO_CODES.get(code, "Unknown"),
            "icon":    _night_icon(code, hi % 24, sunrise_h, sunset_h),
            "sunrise": data["daily"]["sunrise"][0],
            "sunset":  data["daily"]["sunset"][0],
            "hourly":  hourly,
        }
    except Exception as e:
        return None
