import requests
import random
from datetime import datetime, timedelta
import math
import os
from PIL import Image, ImageDraw, ImageFont

# ---------------- CONFIG ----------------
CST_OFFSET = -5
OUTPUT_FILE = "northshore_night_forecast.png"

# 🌊 NORTH SHORE MN / LAKE SUPERIOR COASTAL STATIONS ONLY
STATIONS = [
    "KDLH",   # Duluth (Lake Superior shore)
    "KINL",   # International Falls (northern edge influence)
    "KDYT",   # Duluth Harbor / shoreline proxy
    "KBFW",   # Silver Bay / North Shore region proxy
]

API_KEY = "354b43fc8a5e4d7c8b43fc8a5ecd7c56"

# ---------------- HELPERS ----------------
def clamp(val, min_v=None, max_v=None):
    if min_v is not None and val < min_v:
        return min_v
    if max_v is not None and val > max_v:
        return max_v
    return val

# ---------------- FETCH ----------------
def fetch_station(station_id):
    url = (
        "https://api.weather.com/v2/pws/observations/current"
        f"?stationId={station_id}&format=json&units=e&apiKey={API_KEY}"
    )
    try:
        r = requests.get(url, timeout=5)
        obs = r.json()["observations"][0]["imperial"]
        return (
            obs.get("temp", 35.0),
            obs.get("windSpeed", 5.0),
            obs.get("windGust", 8.0),
            obs.get("pressure", 30.00),
            obs.get("humidity", 50),
            obs.get("dewpt", 30.0),
        )
    except:
        return 35.0, 5.0, 8.0, 30.00, 50, 30.0


def fetch_regional_data(stations):
    temps, winds, gusts, baros, hums, dews = [], [], [], [], [], []

    for s in stations:
        t, w, g, p, h, d = fetch_station(s)
        temps.append(t)
        winds.append(w)
        gusts.append(g)
        baros.append(p)
        hums.append(h)
        dews.append(d)

    return (
        sum(temps)/len(temps),
        sum(winds)/len(winds),
        sum(gusts)/len(gusts),
        sum(baros)/len(baros),
        sum(hums)/len(hums),
        sum(dews)/len(dews),
    )

# ---------------- NIGHT FORECAST MODELS ----------------
def forecast_temp(temp, now):
    hour = now.hour + now.minute / 60

    # Lake Superior effect → cooler nights
    peak_hour = 4
    curve = math.cos((hour - peak_hour) / 24 * 2 * math.pi)

    lake_cooling = -3.0 if hour >= 18 or hour <= 6 else 0

    amp = 7 if now.month in [12, 1, 2] else 5

    return temp + curve * amp + lake_cooling


def forecast_wind(speed, gust, now):
    hour = now.hour

    # Lake Superior increases wind variability
    lake_factor = 1.1

    if hour >= 18 or hour <= 6:
        speed *= 0.70 * lake_factor
        gust *= 0.75 * lake_factor
    else:
        speed *= 1.05
        gust *= 1.10

    speed += random.uniform(-1.2, 1.2)
    gust += random.uniform(-2.5, 2.5)

    return clamp(speed, 0), clamp(gust, speed)


def forecast_pressure(baro, now):
    trend = math.sin(now.hour / 24 * 2 * math.pi) * 0.04
    return clamp(baro + trend, 28.5, 31.5)


def forecast_humidity(temp, dewpt):
    temp_c = (temp - 32) * 5/9
    dew_c = (dewpt - 32) * 5/9

    es = 6.11 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
    e = 6.11 * math.exp((17.27 * dew_c) / (237.7 + dew_c))

    return clamp((e / es) * 100, 35, 100)


def forecast_dewpoint(temp, rh):
    temp_c = (temp - 32) * 5/9
    a, b = 17.27, 237.7

    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh / 100)
    dew_c = (b * alpha) / (a - alpha)

    return dew_c * 9/5 + 32


def get_condition(avg_wind, now):
    hour = now.hour

    if hour >= 18 or hour <= 6:
        return "LAKE NIGHT"

    if avg_wind >= 30:
        return "LAKE WINDY"
    elif avg_wind >= 20:
        return "BREEZY LAKE"
    else:
        return "CALM SHORE"

# ---------------- IMAGE ----------------
def render_image(data):
    img = Image.new("RGB", (600, 350), (8, 12, 20))  # darker lake night tone
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("arial.ttf", 48)
        font_med = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_big = font_med = font_small = ImageFont.load_default()

    draw.text((20, 15), "North Shore MN NIGHT Forecast", fill="#8fd3ff", font=font_med)

    draw.text((20, 70), f"{data['temp']:.0f}°F", fill="white", font=font_big)

    draw.text((20, 150), f"Avg Wind: {data['wind']:.0f} mph", fill="white", font=font_med)
    draw.text((20, 180), f"Avg Gust: {data['gust']:.0f} mph", fill="white", font=font_small)

    draw.text((350, 70), data["condition"], fill="#66d9ff", font=font_med)

    draw.text((20, 220), f"Pressure: {data['pressure']:.2f} inHg", fill="white", font=font_small)
    draw.text((20, 250), f"Humidity: {data['humidity']:.0f}%", fill="white", font=font_small)
    draw.text((20, 280), f"Dew Pt: {data['dew']:.0f}°F", fill="white", font=font_small)

    draw.text((300, 310), data["time"], fill="gray", font=font_small)

    img.save(OUTPUT_FILE)
    print("Saved:", OUTPUT_FILE)

# ---------------- GIT PUSH ----------------
def push_to_github():
    os.system("git config user.name github-actions")
    os.system("git config user.email github-actions@github.com")

    os.system(f"git add {OUTPUT_FILE}")
    os.system('git commit -m "North Shore night forecast update" || exit 0')
    os.system("git push")

    print("Pushed to GitHub")

# ---------------- MAIN ----------------
def main():
    now_utc = datetime.utcnow()
    now_cst = now_utc + timedelta(hours=CST_OFFSET)

    temp, wind, gust, baro, rh, dew = fetch_regional_data(STATIONS)

    f_temp = forecast_temp(temp, now_cst)
    f_wind, f_gust = forecast_wind(wind, gust, now_cst)
    f_pressure = forecast_pressure(baro, now_cst)

    f_rh = forecast_humidity(f_temp, dew)
    f_dew = forecast_dewpoint(f_temp, f_rh)

    condition = get_condition(f_wind, now_cst)

    data = {
        "temp": f_temp,
        "wind": f_wind,
        "gust": f_gust,
        "pressure": f_pressure,
        "humidity": f_rh,
        "dew": f_dew,
        "condition": condition,
        "time": now_cst.strftime("%Y-%m-%d %H:%M CST")
    }

    render_image(data)
    push_to_github()

if __name__ == "__main__":
    main()
