# -*- coding: utf-8 -*-
"""
JARVIS Smart Home — Home Assistant API integration
"""

import requests
import os
import json

HA_URL = os.environ.get("HA_URL", "http://localhost:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")


def _headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


def _available():
    """Check if Home Assistant is running."""
    if not HA_TOKEN:
        return False
    try:
        r = requests.get(f"{HA_URL}/api/", headers=_headers(), timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def turn_on(entity_id):
    """Turn on a device."""
    try:
        r = requests.post(
            f"{HA_URL}/api/services/homeassistant/turn_on",
            headers=_headers(),
            json={"entity_id": entity_id},
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[SmartHome] turn_on error: {e}")
        return False


def turn_off(entity_id):
    """Turn off a device."""
    try:
        r = requests.post(
            f"{HA_URL}/api/services/homeassistant/turn_off",
            headers=_headers(),
            json={"entity_id": entity_id},
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[SmartHome] turn_off error: {e}")
        return False


def toggle(entity_id):
    """Toggle a device on/off."""
    try:
        r = requests.post(
            f"{HA_URL}/api/services/homeassistant/toggle",
            headers=_headers(),
            json={"entity_id": entity_id},
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[SmartHome] toggle error: {e}")
        return False


def get_state(entity_id):
    """Get the current state of a device."""
    try:
        r = requests.get(
            f"{HA_URL}/api/states/{entity_id}",
            headers=_headers(),
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("state", "unknown")
        return "unknown"
    except Exception:
        return "unavailable"


def get_all_lights():
    """Return all light entities and their states."""
    try:
        r = requests.get(f"{HA_URL}/api/states", headers=_headers(), timeout=5)
        if r.status_code == 200:
            entities = r.json()
            return [
                {"id": e["entity_id"], "state": e["state"],
                 "name": e.get("attributes", {}).get("friendly_name", e["entity_id"])}
                for e in entities
                if e["entity_id"].startswith("light.")
            ]
    except Exception:
        pass
    return []


def set_brightness(entity_id, brightness_pct):
    """Set light brightness (0-100)."""
    brightness = int(brightness_pct * 2.55)  # convert to 0-255
    try:
        r = requests.post(
            f"{HA_URL}/api/services/light/turn_on",
            headers=_headers(),
            json={"entity_id": entity_id, "brightness": brightness},
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


def execute_action(action_dict):
    """
    Execute a parsed action from JARVIS brain.
    action_dict: {"type": "home", "command": "turn_on", "entity": "light.living_room"}
    """
    if not _available():
        return f"Home Assistant isn't running or configured yet."

    command = action_dict.get("command")
    entity = action_dict.get("entity")

    if command == "turn_on":
        success = turn_on(entity)
        return f"Turned on {entity}." if success else f"Couldn't reach {entity}."
    elif command == "turn_off":
        success = turn_off(entity)
        return f"Turned off {entity}." if success else f"Couldn't reach {entity}."
    elif command == "toggle":
        success = toggle(entity)
        return f"Toggled {entity}." if success else f"Couldn't reach {entity}."
    else:
        return f"Unknown command: {command}"


def status_summary():
    """Get a plain-English summary of home status."""
    if not _available():
        return "Home Assistant is not connected."

    lights = get_all_lights()
    if not lights:
        return "No smart home devices found."

    on_lights = [l["name"] for l in lights if l["state"] == "on"]
    off_lights = [l["name"] for l in lights if l["state"] == "off"]

    parts = []
    if on_lights:
        parts.append(f"{len(on_lights)} light(s) on: {', '.join(on_lights)}")
    if off_lights:
        parts.append(f"{len(off_lights)} light(s) off")
    return ". ".join(parts) if parts else "All devices appear off."
