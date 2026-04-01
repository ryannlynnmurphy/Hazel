# -*- coding: utf-8 -*-
"""
JARVIS Morning Brief — Runs daily via cron at 7:30 AM
Speaks the weather, date, and a motivating summary.
"""

import os
import sys
import requests
import datetime
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anthropic

_HZL_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_MODEL = os.path.join(_HZL_DIR, "voices", "en_US-lessac-medium.onnx")
WEATHER_KEY = os.environ.get("WEATHER_API_KEY", "")
CITY = os.environ.get("JARVIS_CITY", "New York")


def speak(text):
    if not os.path.exists(VOICE_MODEL):
        print(f"[Brief] {text}")
        return
    try:
        subprocess.run(
            ["piper", "--model", VOICE_MODEL, "--output_file", "/tmp/brief.wav"],
            input=text.encode("utf-8"),
            capture_output=True,
        )
        subprocess.run(["aplay", "-q", "/tmp/brief.wav"])
    except Exception as e:
        print(f"[Brief] Speak error: {e}")


def get_weather():
    if not WEATHER_KEY:
        return "Weather unavailable — no API key configured."
    try:
        url = (
            f"http://api.openweathermap.org/data/2.5/weather"
            f"?q={CITY}&appid={WEATHER_KEY}&units=imperial"
        )
        r = requests.get(url, timeout=5).json()
        temp = round(r["main"]["temp"])
        feels = round(r["main"]["feels_like"])
        desc = r["weather"][0]["description"]
        humidity = r["main"]["humidity"]
        return (
            f"{temp} degrees Fahrenheit, feels like {feels}, "
            f"{desc}, humidity {humidity} percent"
        )
    except Exception as e:
        return f"Weather unavailable: {e}"


def get_briefing(weather, today_str):
    try:
        client = anthropic.Anthropic()
        prompt = (
            f"Today is {today_str}. Weather in {CITY}: {weather}. "
            f"Write a 2-sentence morning briefing — positive, grounded, and useful. "
            f"No fluff. Just something genuinely helpful to hear at the start of the day."
        )
        r = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.content[0].text
    except Exception as e:
        return f"Good morning. Have a great day ahead."


def main():
    today = datetime.datetime.now().strftime("%A, %B %d")
    weather = get_weather()
    briefing = get_briefing(weather, today)

    full_message = f"Good morning. Today is {today}. {weather}. {briefing}"
    print(f"[Morning Brief] {full_message}")
    speak(full_message)


if __name__ == "__main__":
    main()
