import requests
import random
from datetime import datetime, timedelta
import math
import os
import time
from PIL import Image, ImageDraw, ImageFont

# ---------------- CONFIG ----------------
CST_OFFSET = -5
OUTPUT_FILE = "northshore_day_forecast.png"

STATIONS = ["KDLH", "KCKC", "KHYR", "KDYT"]

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
    d = now.strftime("%Y-%m-%d")

    if d == "2026-04-24":
        return {
            "temp": 60, "wind": 15, "gust": 26, "humidity": 19,
            "condition": "WINDY SHORE",
            "alert": {
                "title": "EXTREME FIRE WATCH",
                "desc": "Humidity 10–20% | Winds 15–30 mph gust 35–45 mph",
                "color": (255, 220, 0)
            }
        }

    if d == "2026-04-25":
        return {
            "temp": 72, "wind": 21, "gust": 57, "humidity": 14,
            "condition": "WINDY SHORE",
            "alert": {
                "title": "EXTREME FIRE WARNING",
                "desc": "Humidity 10–20% | Winds 15–30 mph gust 35–45 mph",
                "color": (255, 140, 0)
            }
        }

    return None

# ---------------- FETCH ----------------
def fetch_station(station_id):
    try:
        url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=e&apiKey={API_KEY}"
        r = requests.get(url, timeout=4)
        data = r.json()

        if "observations" not in data:
            raise ValueError("Bad station")

        obs = data["observations"][0]["imperial"]

        return (
            obs.get("temp", 40),
            obs.get("windSpeed", 8),
            obs.get("windGust", 12),
            obs.get("pressure", 30.0),
            obs.get("humidity", 60),
            obs.get("dewpt", 35),
        )
    except:
        # fallback realistic North Shore defaults
        return (
            random.uniform(45, 65),
            random.uniform(8, 18),
            random.uniform(15, 30),
            random.uniform(29.7, 30.2),
            random.uniform(40, 80),
            random.uniform(30, 50),
        )

def fetch_regional_data(stations):
    vals = [fetch_station(s) for s in stations]
    return tuple(sum(x[i] for x in vals)/len(vals) for i in range(6))

# ---------------- FORECAST ----------------
def forecast_temp(temp, now):
    hour = now.hour + now.minute / 60
    curve = math.cos((hour - 15)/24 * 2*math.pi)
    lake = -2
    return temp + curve*6 + lake

def forecast_wind(speed, gust, now):
    mult = 1.3 if 10 <= now.hour <= 18 else 0.9
    return clamp(speed*mult + random.uniform(-1,1),0), clamp(gust*mult + random.uniform(-3,3),0)

def forecast_pressure(baro, now):
    return clamp(baro + math.sin(now.hour/24*2*math.pi)*0.04, 28.5, 31.5)

def forecast_humidity(temp, dew):
    return clamp((dew/temp)*100 if temp else 50, 20, 100)

def forecast_dewpoint(temp, rh):
    return temp - ((100 - rh)/5)

def get_condition(w):
    return "WINDY SHORE" if w >= 20 else "CALM LAKE"

# ---------------- VISUALS ----------------
def draw_wind(draw):
    for _ in range(50):
        x = random.randint(0, 600)
        y = random.randint(60, 340)
        length = random.randint(20, 120)
        draw.line((x, y, x+length, y), fill=(180,220,255), width=1)

def draw_fire_meter(draw, humidity):
    # scale 0–100 → bar
    x0, y0 = 400, 200
    width = 150
    level = int((100 - humidity)/100 * width)

    draw.rectangle([x0, y0, x0+width, y0+15], outline="white")
    draw.rectangle([x0, y0, x0+level, y0+15], fill="red")

    label = "LOW"
    if humidity < 30: label = "HIGH"
    if humidity < 20: label = "VERY HIGH"
    if humidity < 15: label = "EXTREME"

    draw.text((x0, y0-20), f"FIRE: {label}", fill="orange")

# ---------------- IMAGE ----------------
def render_image(data):
    img = Image.new("RGB", (600, 350), (10,20,35))
    draw = ImageDraw.Draw(img)

    try:
        big = ImageFont.truetype("arial.ttf", 52)
        med = ImageFont.truetype("arial.ttf", 24)
        small = ImageFont.truetype("arial.ttf", 18)
    except:
        big = med = small = ImageFont.load_default()

    # wind effect
    draw_wind(draw)

    # alert banner
    if data.get("alert"):
        flash = int(time.time()) % 2 == 0
        color = data["alert"]["color"] if flash else (255,255,255)

        draw.rectangle([0,0,600,55], fill=color)
        draw.text((10,8), data["alert"]["title"], fill="black", font=med)
        draw.text((10,30), data["alert"]["desc"], fill="black", font=small)

    draw.text((20,65), "North Shore MN Forecast", fill="lightblue", font=med)

    draw.text((20,100), f"{data['temp']:.0f}°F", fill="white", font=big)

    draw.text((20,180), f"Wind {data['wind']:.0f} mph", fill="white", font=med)
    draw.text((20,210), f"Gust {data['gust']:.0f} mph", fill="white", font=small)

    draw.text((380,100), data["condition"], fill="cyan", font=med)

    draw.text((20,260), f"Humidity {data['humidity']:.0f}%", fill="white", font=small)
    draw.text((20,285), f"Dew {data['dew']:.0f}°F", fill="white", font=small)

    draw_fire_meter(draw, data["humidity"])

    draw.text((300,320), data["time"], fill="gray", font=small)

    img.save(OUTPUT_FILE)
    print("Saved:", OUTPUT_FILE)

# ---------------- GIT ----------------
def push_to_github():
    os.system("git config user.name github-actions")
    os.system("git config user.email github-actions@github.com")
    os.system(f"git add {OUTPUT_FILE}")
    os.system('git commit -m "Auto North Shore update" || exit 0')
    os.system("git push")

# ---------------- MAIN ----------------
def main():
    now = datetime.utcnow() + timedelta(hours=CST_OFFSET)

    temp, wind, gust, baro, rh, dew = fetch_regional_data(STATIONS)

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
        f_temp = forecast_temp(temp, now)
        f_wind, f_gust = forecast_wind(wind, gust, now)

        data = {
            "temp": f_temp,
            "wind": f_wind,
            "gust": f_gust,
            "humidity": rh,
            "dew": dew,
            "condition": get_condition(f_wind),
            "time": now.strftime("%Y-%m-%d %H:%M CST"),
            "alert": None
        }

    render_image(data)
    push_to_github()

if __name__ == "__main__":
    main()
