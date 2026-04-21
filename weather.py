import requests
import random
from datetime import datetime, timedelta
import math

# ---------------- CONFIG ----------------
STATION_ID = "KMNBABBI25"
PASSWORD = "SX8EG38H"

NEARBY_STATION_ID = "KMNBABBI27"
CST_OFFSET = -5

# ---------------- BASE VALUES ----------------
start_values = {
    "temp_f": 54.0,
    "baro_in": 31.00,
    "dewpt_f": 41.0,
    "humidity": 32.0,
    "wind_speed": 69.0,
    "wind_gust": 100.0,
    "daily_rain_in": 0.00,
    "rain_in": 0.00
}

peak_values = {
    "temp_f": 32.0,
    "baro_in": 31.11,
    "dewpt_f": 49.0,
    "humidity": 32.0,
    "wind_speed": 0.0,
    "wind_gust": 0.0,
    "daily_rain_in": 0.00,
    "rain_in": 0.00
}


# ---------------- HELPERS ----------------
def clamp(val, min_v=None, max_v=None):
    if min_v is not None and val < min_v:
        return min_v
    if max_v is not None and val > max_v:
        return max_v
    return val

def interpolate(a, b, f):
    return a + (b - a) * f

# ---------------- WEATHER FETCH ----------------
def fetch_nearby_conditions(station_id):
    url = (
        "https://api.weather.com/v2/pws/observations/current"
        f"?stationId={station_id}&format=json&units=e"
        "&apiKey=354b43fc8a5e4d7c8b43fc8a5ecd7c56"
    )
    try:
        r = requests.get(url, timeout=5)
        obs = r.json()["observations"][0]["imperial"]
        return (
            obs.get("windSpeed", 0.0),
            obs.get("windGust", 0.0),
            obs.get("temp", 35.0),
            obs.get("icon", "CLR"),
        )
    except Exception:
        return 0.0, 0.0, 35.0, "CLR"

def indoor_solar_uv(weather, curtains_open, month, hour):
    """
    Calculate indoor solar and UV deterministically.
    - daytime = 6 AM → 6 PM
    - nighttime = else
    """
    # Nighttime
    if hour < 6 or hour >= 18:
        return 0, 0

    # Daytime
    sunny_conditions = ["SUN", "CLR", "FEW"]

    if not curtains_open:
        return 50, 0.2  # curtains closed

    if weather in sunny_conditions:
        # Curtains open + sunny → seasonal brightness
        if month in [6,7,8]:  # summer
            return 12000, 7
        elif month in [3,4,5,9,10,11]:  # spring/fall
            return 9000, 5
        else:  # winter
            return 6000, 3
    else:
        # Curtains open but cloudy/rainy
        return 50, 0.2


# ---------------- HVAC BRAIN ----------------
def adjust_indoor_temp(base_temp, now_cst, month, outdoor_temp):
    temp = base_temp
    weekday = now_cst.weekday()
    is_weekday = weekday <= 4
    is_friday_night = weekday == 4 and now_cst.hour >= 18
    is_weekend = weekday >= 5
    is_winter = month in [12, 1, 2]
    is_warm_season = month in [3, 4, 5, 6, 7, 8, 9, 10, 11]

    heating_allowed = outdoor_temp < 55
    if now_cst.date() in [
        datetime(2026, 3, 9).date(),
        datetime(2026, 3, 10).date()
    ]:
        return base_temp
    # seasonal drift
    if is_winter:
        temp += 3.5
    elif month in [6, 7, 8]:
        temp += 1.0

    def ramp(sh, sm, eh, em, max_add):
        start = sh * 60 + sm
        end = eh * 60 + em
        now = now_cst.hour * 60 + now_cst.minute
        if now < start or now > end:
            return 0.0
        return max_add * ((now - start) / (end - start))

    # heating failure model
    heating_failure = False
    weak_heating = False
    if heating_allowed:
        roll = random.random()
        if roll < 0.05:
            heating_failure = True
        elif roll < 0.15:
            weak_heating = True

    strength = 0.4 if weak_heating else 1.0

    # heating logic
    if heating_allowed and not heating_failure:
        if is_weekday:
            temp += ramp(4, 30, 6, 0, 6.0 * strength)
            temp += ramp(15, 15, 16, 30, 4.5 * strength)
        if is_weekend or is_friday_night:
            if outdoor_temp < 15:
                temp += 7 * strength
            elif outdoor_temp < 28:
                temp += 5 * strength
            elif outdoor_temp < 38:
                temp += 3 * strength

    # AC logic
    if is_warm_season and temp >= 80:
        ac_roll = random.random()
        if ac_roll < 0.08:
            pass
        elif ac_roll < 0.18:
            temp -= random.uniform(0.2, 0.6)
        else:
            cool = random.uniform(0.8, 1.6)
            if temp >= 85:
                cool += 0.8
            temp -= cool

    # heating overshoot
    overshoot = 0.0
    if heating_allowed and not heating_failure and temp >= 75:
        if random.random() < 0.25:
            overshoot = random.uniform(0.3, 1.6)

    max_heat = 76.0 + overshoot

    if is_winter:
        return clamp(temp, None, max_heat)
    else:
        return clamp(temp, 70.0, 85.0)


def indoor_air_pressure(outdoor_baromin):
    """
    Deterministic indoor pressure: slight fixed offset from outdoor.
    """
    # Example: indoor slightly higher than outdoor
    return clamp(outdoor_baromin + 0.02, 28.0, 31.0)


# ---------------- DEW POINT CALC ----------------
def dew_point_f(temp_f, rh):
    """
    Calculate indoor dew point in Fahrenheit from temp and RH.
    Works for all seasons.
    """
    temp_c = (temp_f - 32) * 5 / 9
    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh / 100.0)
    dew_c = (b * alpha) / (a - alpha)
    dew_f = dew_c * 9 / 5 + 32
    return dew_f


def calculate_indoor_humidity(temp_f, month):
    """
    Estimate indoor humidity for all seasons based on temp and typical ranges.
    Returns %RH
    """
    if month in [12, 1, 2]:  # winter
        base_rh = 30
    elif month in [3, 4, 5, 9, 10, 11]:  # spring/fall
        base_rh = 45
    else:  # summer
        base_rh = 50

    # Adjust for indoor temp drift (warmer → slightly drier)
    rh = base_rh - (temp_f - 70) * 0.5  # each °F above 70 reduces RH a bit
    return clamp(rh, 20, 60)  # limit RH to 20–60%


# ---------------- BEDTIME WIND ----------------
def bedtime_wind(base_wind, now_cst):
    """
    Adjust indoor wind during bedtime windows with ramp to 10 mph.
    Disabled on Mar 9–10 2026 due to wind event.
    """

    # Disable bedtime wind during storm event
    if now_cst.date() in [
        datetime(2026, 3, 9).date(),
        datetime(2026, 3, 10).date()
    ]:
        return base_wind

    weekday = now_cst.weekday()
    hour_min = now_cst.hour * 60 + now_cst.minute
    max_wind = 10.0

    # Weekdays Mon–Thu + Friday morning 8 PM → 5:30 AM
    if weekday <= 4:
        start = 20 * 60
        end = 29 * 60 + 30

        if hour_min < start:
            return base_wind
        elif hour_min <= 24 * 60:
            factor = (hour_min - start) / (end - start)
            return base_wind + factor * (max_wind - base_wind)
        else:
            factor = (hour_min - 24 * 60) / (end - 24 * 60)
            return base_wind + factor * (max_wind - base_wind)

    # Weekends Fri night / Sat / Sun → 10 PM → 2 AM
    if weekday == 4 or weekday >= 5:
        start = 22 * 60
        end = 26 * 60

        if hour_min < start:
            return base_wind
        elif hour_min <= 24 * 60:
            factor = (hour_min - start) / (end - start)
            return base_wind + factor * (max_wind - base_wind)
        else:
            factor = (hour_min - 24 * 60) / (end - 24 * 60)
            return base_wind + factor * (max_wind - base_wind)

    return base_wind


def special_wind_event(base_wind, now_cst):
    """
    March 10, 2026 wind events
    """
    if now_cst.date() != datetime(2026, 3, 10).date():
        return base_wind

    minutes = now_cst.hour * 60 + now_cst.minute

    # ---- EVENT 1 ----
    start1 = 7 * 60 + 15
    peak1 = 8 * 60
    end1 = 12 * 60

    if start1 <= minutes <= end1:

        if minutes <= peak1:
            factor = (minutes - start1) / (peak1 - start1)
        else:
            factor = 1 - (minutes - peak1) / (end1 - peak1)

        wind = 25 + factor * (35 - 25)

        # occasional higher gusts
        if random.random() < 0.25:
            wind += random.uniform(5, 12)

        return wind

    # ---- EVENT 2 ----
    start2 = 12 * 60
    peak2 = 13 * 60
    end2 = 17 * 60

    if start2 <= minutes <= end2:

        if minutes <= peak2:
            factor = (minutes - start2) / (peak2 - start2)
        else:
            factor = 1 - (minutes - peak2) / (end2 - peak2)

        wind = 35 + factor * (55 - 35)

        # occasional higher gusts
        if random.random() < 0.35:
            wind += random.uniform(10, 20)

        return wind

    return base_wind

def special_temp_event(base_temp, now_cst):
    """
    March 10, 2026 cold air surge with temps dipping into the 30s
    """
    if now_cst.date() != datetime(2026, 3, 10).date():
        return base_temp

    minutes = now_cst.hour * 60 + now_cst.minute

    start1 = 7 * 60 + 15
    peak1 = 8 * 60
    mid = 12 * 60
    peak2 = 13 * 60
    end = 17 * 60

    # Morning drop
    if start1 <= minutes <= peak1:
        factor = (minutes - start1) / (peak1 - start1)
        return interpolate(base_temp, 38, factor)

    # Hold cold through late morning
    if peak1 < minutes <= mid:
        return random.uniform(34, 39)

    # Early afternoon dip
    if mid < minutes <= peak2:
        factor = (minutes - mid) / (peak2 - mid)
        return interpolate(38, 33, factor)

    # Gradual recovery
    if peak2 < minutes <= end:
        factor = (minutes - peak2) / (end - peak2)
        return interpolate(33, base_temp, factor)

    return base_temp

def storm_wind_event(base_wind, now_cst):
    """
    March 9 2026 wind event
    5:25 PM → Midnight
    Peak by 8 PM with 20–30 mph winds
    """
    
    event_start = datetime(2026, 3, 9, 17, 25)
    peak_time = datetime(2026, 3, 9, 20, 0)
    event_end = datetime(2026, 3, 10, 0, 0)

    if now_cst < event_start or now_cst > event_end:
        return base_wind

    # ramp up
    if now_cst <= peak_time:
        factor = (now_cst - event_start).total_seconds() / (peak_time - event_start).total_seconds()
        target = 20 + factor * 10  # ramp 20 → 30 mph

    # ramp down slowly
    else:
        factor = (now_cst - peak_time).total_seconds() / (event_end - peak_time).total_seconds()
        target = 30 - factor * 10  # ramp 30 → 20 mph

    gust = target + random.uniform(5, 15)

    return max(base_wind, target), gust
# ---------------- MAIN ----------------
def main():
    now_utc = datetime.utcnow()
    now_cst = now_utc + timedelta(hours=CST_OFFSET)

    time_start = datetime(2026, 3, 12, 8, 41)
    time_peak = datetime(2026, 3, 12, 17, 0)

    if now_cst <= time_start:
        factor = 0.0
    elif now_cst >= time_peak:
        factor = 1.0
    else:
        factor = (now_cst - time_start).total_seconds() / (
            time_peak - time_start
        ).total_seconds()

    wind_speed, wind_gust, outdoor_temp, weather = fetch_nearby_conditions(NEARBY_STATION_ID)
    # Apply bedtime wind logic
    wind_speed0 = special_wind_event(wind_speed, now_cst)
    wind_gust0 = special_wind_event(wind_gust, now_cst)
    wind_speed0 = storm_wind_event(wind_speed, now_cst)
    wind_gust0 = storm_wind_event(wind_gust, now_cst)
    baro_base = interpolate(start_values["baro_in"], peak_values["baro_in"], factor)
    base_temp = interpolate(start_values["temp_f"], peak_values["temp_f"], factor)
    humidity = interpolate(start_values["humidity"], peak_values["humidity"], factor)
    rain_in = interpolate(start_values["rain_in"], peak_values["rain_in"], factor)
    daily_rain = interpolate(start_values["daily_rain_in"], peak_values["daily_rain_in"], factor)
    indoor_dew = interpolate(start_values["dewpt_f"], peak_values["dewpt_f"], factor)
    wind_speed_base = interpolate(start_values["wind_speed"], peak_values["wind_speed"], factor)
    wind_gust_base = interpolate(start_values["wind_gust"], peak_values["wind_gust"], factor)

    wind_dir = 270
    clouds = "BKN250"
    
    software_type = "vws versionxx"
    CURTAINS_OPEN = False  # Change as needed
    solar_lux, uv_index = indoor_solar_uv(weather, CURTAINS_OPEN, now_cst.month, now_cst.hour)
    # ---------------- PUSH TO WUNDERGROUND ----------------
    URL = (
        "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
        f"?ID={STATION_ID}&PASSWORD={PASSWORD}&dateutc=now"
        f"&winddir={wind_dir}"
        f"&windspeedmph={wind_speed_base:.1f}"
        f"&windgustmph={wind_gust_base:.1f}"
        f"&tempf={base_temp:.1f}"
        f"&rainin={rain_in:.2f}"
        f"&dailyrainin={daily_rain:.2f}"
        f"&baromin={baro_base:.2f}"
        f"&dewptf={indoor_dew:.1f}"
        f"&humidity={humidity:.0f}"
        f"&weather={weather}&clouds={clouds}"
        f"&uv={uv_index}&solarradiation={solar_lux}"
        f"&softwaretype={software_type}&action=updateraw"
    )

    print("CST:", now_cst.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Outdoor: {outdoor_temp:.1f}°F | Indoor: {base_temp:.1f}°F")
    print(f"Indoor Humidity: {humidity:.0f}% | Indoor Dew Point: {indoor_dew:.1f}°F")
    print(f"Indoor Wind Speed: {wind_speed:.1f} mph")
    print("Note: Indoor dew point monitoring historically became common around 1957 CE.")
    print("Sending update...")

    try:
        r = requests.get(URL, timeout=10)
        print("Status:", r.status_code)
        print("Response:", r.text)
    except requests.exceptions.RequestException as e:
        print("Send error:", e)

if __name__ == "__main__":
    main()


















































