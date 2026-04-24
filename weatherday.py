import requests
import random
from datetime import datetime, timedelta
import math
import os
import time
from PIL import Image, ImageDraw, ImageFont

# ---------------- CONFIG ----------------
CST_OFFSET = -5
OUTPUT_FILE = "northland_forecast.png"

STATIONS = [
    "KMNBABBI27",
    "KMNDULUT33",
    "KMNHIBBI5",
    "KMNGRAND4",
]

API_KEY = "354b43fc8a5e4d7c8b43fc8a5ecd7c56"

# ---------------- HELPERS ----------------
def clamp(val, min_v=None, max_v=None):
    if min_v is not None and val < min_v:
        return min_v
    if max_v is not None and val > max_v:
        return max_v
    return val

# ---------------- OVERRIDES ----------------
def get_override(now):
    date_str = now.strftime("%Y-%m-%d")

    if date_str == "2026-04-24":
        return {
            "temp": 60,
            "wind": 15,
            "gust": 26,
            "humidity": 14,
            "condition": "WINDY",
            "alert": {
                "title": "EXTREME FIRE WATCH",
                "desc": "Low humidity 5–15% with winds 15–25 mph gusting 25–35 mph",
                "color": (255, 215, 0)
            }
        }

    elif date_str == "2026-04-25":
        return {
            "temp": 72,
            "wind": 21,
            "gust": 57,
            "humidity": 11,
            "condition": "WINDY",
            "alert": {
                "title": "EXTREME FIRE WARNING",
                "desc": "Low humidity 5–15% with winds 15–25 mph gusting 25–35 mph",
                "color": (255, 140, 0)
            }
        }

    return None

# ---------------- FETCH ----------------
def fetch_station(station_id):
    try:
        url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=e&apiKey={API_KEY}"
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
    vals = [fetch_station(s) for s in stations]
    return tuple(sum(x[i] for x in vals)/len(vals) for i in range(6))

# ---------------- FORECAST ----------------
def forecast_dewpoint(temp, rh):
    temp_c = (temp - 32) * 5/9
    a, b = 17.27, 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh / 100)
    dew_c = (b * alpha) / (a - alpha)
    return dew_c * 9/5 + 32

# ---------------- VISUAL EFFECTS ----------------
def draw_wind(draw):
    for _ in range(25):
        x = random.randint(0, 600)
        y = random.randint(60, 340)
        length = random.randint(20, 80)
        draw.line((x, y, x + length, y), fill=(180, 200, 255), width=1)

# ---------------- IMAGE ----------------
def render_image(data):
    img = Image.new("RGB", (600, 350), (15, 25, 40))
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("arial.ttf", 52)
        font_med = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_big = font_med = font_small = ImageFont.load_default()

    # Wind effect
    draw_wind(draw)

    # Flashing alert
    if data.get("alert"):
        flash = int(time.time()) % 2 == 0
        color = data["alert"]["color"] if flash else (255, 255, 255)

        draw.rectangle([(0, 0), (600, 50)], fill=color)
        draw.text((10, 8), data["alert"]["title"], fill="black", font=font_med)
        draw.text((10, 28), data["alert"]["desc"], fill="black", font=font_small)

    # Title
    draw.text((20, 60), "Northland MN Forecast", fill="white", font=font_med)

    # Temp
    draw.text((20, 100), f"{data['temp']:.0f}°F", fill="white", font=font_big)

    # Wind
    draw.text((20, 180), f"Wind: {data['wind']:.0f} mph", fill="white", font=font_med)
    draw.text((20, 210), f"Gusts: {data['gust']:.0f} mph", fill="white", font=font_small)

    # Right side
    draw.text((350, 100), data["condition"], fill="orange", font=font_med)

    # Bottom stats
    draw.text((20, 250), f"Humidity: {data['humidity']:.0f}%", fill="white", font=font_small)
    draw.text((20, 275), f"Dew Pt: {data['dew']:.0f}°F", fill="white", font=font_small)

    draw.text((320, 320), data["time"], fill="gray", font=font_small)

    img.save(OUTPUT_FILE)
    print("Saved:", OUTPUT_FILE)

# ---------------- GIT ----------------
def push_to_github():
    os.system("git config user.name github-actions")
    os.system("git config user.email github-actions@github.com")
    os.system(f"git add {OUTPUT_FILE}")
    os.system('git commit -m "Auto forecast update" || exit 0')
    os.system("git push")

# ---------------- MAIN ----------------
def main():
    now = datetime.utcnow() + timedelta(hours=CST_OFFSET)

    base = fetch_regional_data(STATIONS)
    temp, wind, gust, baro, rh, dew = base

    override = get_override(now)

    if override:
        data = {
            "temp": override["temp"],
            "wind": override["wind"],
            "gust": override["gust"],
            "humidity": override["humidity"],
            "dew": forecast_dewpoint(override["temp"], override["humidity"]),
            "condition": override["condition"],
            "time": now.strftime("%Y-%m-%d %H:%M CST"),
            "alert": override["alert"]
        }
    else:
        data = {
            "temp": temp,
            "wind": wind,
            "gust": gust,
            "humidity": rh,
            "dew": dew,
            "condition": "CALM" if wind < 15 else "WINDY",
            "time": now.strftime("%Y-%m-%d %H:%M CST"),
            "alert": None
        }

    render_image(data)
    push_to_github()

if __name__ == "__main__":
    main()
