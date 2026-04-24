import requests
import random
from datetime import datetime, timedelta
import math
import os
import time
from PIL import Image, ImageDraw, ImageFont

# ---------------- CONFIG ----------------
CST_OFFSET = -5
OUTPUT_FILE = "northshore_night_forecast.png"

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
    return tuple(sum(x[i] for x in vals) / len(vals) for i in range(6))

# ---------------- FORECAST ----------------
def forecast_temp(temp, now):
    hour = now.hour + now.minute / 60
    peak_hour = 4
    curve = math.cos((hour - peak_hour) / 24 * 2 * math.pi)

    amp = 8 if now.month in [12, 1, 2] else 6
    night_drop = -2.5 if (hour >= 18 or hour <= 6) else 0

    return temp + curve * amp + night_drop


def forecast_wind(speed, gust, now):
    if now.hour >= 18 or now.hour <= 6:
        speed *= 0.75
        gust *= 0.80
    else:
        speed *= 1.05
        gust *= 1.1

    speed += random.uniform(-1.0, 1.0)
    gust += random.uniform(-2.0, 2.0)

    return clamp(speed, 0), clamp(gust, speed)


def forecast_pressure(baro, now):
    return clamp(baro + math.sin(now.hour / 24 * 2 * math.pi) * 0.04, 28.5, 31.5)


def forecast_humidity(temp, dewpt):
    temp_c = (temp - 32) * 5/9
    dew_c = (dewpt - 32) * 5/9

    es = 6.11 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
    e = 6.11 * math.exp((17.27 * dew_c) / (237.7 + dew_c))

    return clamp((e / es) * 100, 30, 100)


def forecast_dewpoint(temp, rh):
    temp_c = (temp - 32) * 5/9
    a, b = 17.27, 237.7

    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh / 100)
    dew_c = (b * alpha) / (a - alpha)

    return dew_c * 9/5 + 32


def get_condition(w):
    if w >= 30:
        return "WINDY"
    elif w >= 20:
        return "BREEZY"
    else:
        return "CALM"

# ---------------- OVERRIDES ----------------
def apply_override(data, now):
    d = now.strftime("%Y-%m-%d")

    # ---------- APRIL 24, 2026 ----------
    if d == "2026-04-24":
        data["temp"] = 41
        data["wind"] = 20
        data["gust"] = 43
        data["humidity"] = 49
        data["condition"] = "CLEAR / WINDY"

        data["alert"] = {
            "active": True,
            "level": "WATCH",
            "color": (255, 220, 0),
            "title": "EXTREME FIRE WATCH (UNTIL 6AM)",
            "desc": "Low humidity 5–15% | Winds 15–25 mph | Gusts 25–35 mph"
        }

    # ---------- APRIL 25, 2026 ----------
    elif d == "2026-04-25":
        data["temp"] = 21
        data["wind"] = 39
        data["gust"] = 79
        data["humidity"] = 100
        data["condition"] = "HEAVY THUNDERSTORMS / WINDY"

        data["alert"] = {
            "active": True,
            "level": "WARNING",
            "color": (255, 0, 0),
            "title": "EXTREME STORM WARNING (6PM–6AM)",
            "desc": "Tornado possible | Small hail | Gusts 70–100 mph"
        }

    else:
        data["alert"] = {"active": False}

    return data

# ---------------- IMAGE ----------------
def render_image(data, now):
    img = Image.new("RGB", (600, 350), (10, 15, 25))
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("arial.ttf", 48)
        font_med = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_big = font_med = font_small = ImageFont.load_default()

    alert = data.get("alert", {})
    alert_mode = alert.get("active", False)

    # ---------------- WIND STREAKS ----------------
    if alert_mode:
        for _ in range(70):
            x = random.randint(0, 600)
            y = random.randint(50, 350)
            draw.line(
                (x, y, x + random.randint(20, 80), y - random.randint(2, 10)),
                fill=(255, random.randint(120, 180), 0),
                width=2
            )

    # ---------------- ALERT BANNER ----------------
    if alert_mode:
        banner_color = alert["color"]

        if now.second % 2 == 0:
            banner_color = alert["color"]
        else:
            banner_color = (255, 255, 255)

        draw.rectangle((0, 0, 600, 60), fill=banner_color)

        import textwrap
        text = f"{alert['title']} - {alert['desc']}"
        lines = textwrap.wrap(text, width=45)

        y = 5
        for line in lines:
            w = draw.textlength(line, font=font_small)
            draw.text(((600 - w) / 2, y), line, fill="black", font=font_small)
            y += 18

        title_y = 70
    else:
        title_y = 15

    # ---------------- TEXT ----------------
    draw.text((20, title_y), "Northland MN NIGHT Forecast", fill="cyan", font=font_med)

    draw.text((20, 70), f"{data['temp']:.0f}°F", fill="white", font=font_big)

    draw.text((20, 150), f"Avg Wind: {data['wind']:.0f} mph", fill="white", font=font_med)
    draw.text((20, 180), f"Avg Gust: {data['gust']:.0f} mph", fill="white", font=font_small)

    condition_color = "#ff3b3b" if alert.get("level") == "WARNING" else "#66d9ff"
    draw.text((350, 70), data["condition"], fill=condition_color, font=font_med)

    draw.text((20, 220), f"Pressure: {data['pressure']:.2f} inHg", fill="white", font=font_small)
    draw.text((20, 250), f"Humidity: {data['humidity']:.0f}%", fill="white", font=font_small)
    draw.text((20, 280), f"Dew Pt: {data['dew']:.0f}°F", fill="white", font=font_small)

    draw.text((300, 310), data["time"], fill="gray", font=font_small)

    img.save(OUTPUT_FILE)
    print("Saved:", OUTPUT_FILE)

# ---------------- GIT ----------------
def push_to_github():
    os.system("git config user.name github-actions")
    os.system("git config user.email github-actions@github.com")
    os.system(f"git add {OUTPUT_FILE}")
    os.system('git commit -m "Update Northland NIGHT forecast" || exit 0')
    os.system("git push")

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

    data = {
        "temp": f_temp,
        "wind": f_wind,
        "gust": f_gust,
        "pressure": f_pressure,
        "humidity": f_rh,
        "dew": f_dew,
        "condition": get_condition(f_wind),
        "time": now_cst.strftime("%Y-%m-%d %H:%M CST")
    }

    data = apply_override(data, now_cst)

    render_image(data, now_cst)
    push_to_github()


if __name__ == "__main__":
    main()
