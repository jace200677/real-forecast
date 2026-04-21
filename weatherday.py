import requests
import random
from datetime import datetime, timedelta
import math
from PIL import Image, ImageDraw, ImageFont

# ---------------- CONFIG ----------------
CST_OFFSET = -5
OUTPUT_FILE = "northland_forecast.png"

# Multiple stations across Northland MN
STATIONS = [
    "KMNBABBI27",  # local
    "KMNDULUT33",  # Duluth
    "KMNHIBBI5",   # Hibbing
    "KMNGRAND4",   # Grand Rapids
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

# ---------------- FORECAST MODELS ----------------
def forecast_temp(temp, now):
    hour = now.hour + now.minute / 60
    peak_hour = 15
    curve = math.cos((hour - peak_hour) / 24 * 2 * math.pi)

    if now.month in [12, 1, 2]:
        amp = 6
    elif now.month in [6, 7, 8]:
        amp = 10
    else:
        amp = 8

    return temp + curve * amp


def forecast_wind(speed, gust, now):
    if 10 <= now.hour <= 18:
        speed *= 1.2
        gust *= 1.3
    else:
        speed *= 0.85
        gust *= 0.9

    speed += random.uniform(-1.5, 1.5)
    gust += random.uniform(-3, 3)

    return clamp(speed, 0), clamp(gust, speed)


def forecast_pressure(baro, now):
    trend = math.sin(now.hour / 24 * 2 * math.pi) * 0.05
    return clamp(baro + trend, 28.5, 31.5)


def forecast_humidity(temp, dewpt):
    temp_c = (temp - 32) * 5/9
    dew_c = (dewpt - 32) * 5/9

    es = 6.11 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
    e = 6.11 * math.exp((17.27 * dew_c) / (237.7 + dew_c))

    return clamp((e / es) * 100, 20, 100)


def forecast_dewpoint(temp, rh):
    temp_c = (temp - 32) * 5/9
    a, b = 17.27, 237.7

    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh / 100)
    dew_c = (b * alpha) / (a - alpha)

    return dew_c * 9/5 + 32


def get_wind_condition(avg_wind):
    if avg_wind >= 30:
        return "WINDY"
    elif avg_wind >= 20:
        return "BREEZY"
    else:
        return "CALM"

# ---------------- IMAGE ----------------
def render_image(data):
    img = Image.new("RGB", (600, 350), (20, 30, 45))
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("arial.ttf", 48)
        font_med = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_big = font_med = font_small = ImageFont.load_default()

    # Title
    draw.text((20, 15), "Northland MN DAY Forecast", fill="white", font=font_med)

    # Temperature
    draw.text((20, 70), f"{data['temp']:.0f}°F", fill="white", font=font_big)

    # Wind
    draw.text((20, 150), f"Avg Wind: {data['wind']:.0f} mph", fill="white", font=font_med)
    draw.text((20, 180), f"Avg Gust: {data['gust']:.0f} mph", fill="white", font=font_small)

    # Condition
    draw.text((350, 70), data["condition"], fill="orange", font=font_med)

    # Other values
    draw.text((20, 220), f"Pressure: {data['pressure']:.2f} inHg", fill="white", font=font_small)
    draw.text((20, 250), f"Humidity: {data['humidity']:.0f}%", fill="white", font=font_small)
    draw.text((20, 280), f"Dew Pt: {data['dew']:.0f}°F", fill="white", font=font_small)

    draw.text((320, 300), data["time"], fill="gray", font=font_small)

    img.save(OUTPUT_FILE)
    print("Saved:", OUTPUT_FILE)

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

    condition = get_wind_condition(f_wind)

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

if __name__ == "__main__":
    main()
