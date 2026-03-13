"""
notify.py — HZL AI Phone Notifications via ntfy
Push notifications with full debug logging.

Setup:
    1. Install ntfy app on your phone (iOS/Android — free)
    2. Subscribe to a topic in the app (e.g. hazel-ryann-alerts)
    3. Set env vars: NTFY_TOPIC, NTFY_SERVER (optional, default: https://ntfy.sh)
"""

import os
import requests
from hzl_logger import get_logger

log = get_logger("notify")

NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")
NTFY_TOPIC  = os.getenv("NTFY_TOPIC", "hazel-alerts")
NTFY_TOKEN  = os.getenv("NTFY_TOKEN")  # Optional: for self-hosted ntfy with auth
TIMEOUT     = 10

PRIORITY_MAP = {
    "low":     "low",
    "default": "default",
    "normal":  "default",
    "high":    "high",
    "urgent":  "urgent",
    "max":     "urgent",
}


# ── Core sender ───────────────────────────────────────────────────────────────

def notify(
    message:    str,
    title:      str  = "HZL AI",
    priority:   str  = "default",
    tags:       list = None,
    topic:      str  = None,
    action_url: str  = None,
) -> str:
    resolved_topic    = topic or NTFY_TOPIC
    resolved_priority = PRIORITY_MAP.get(priority.lower(), "default")

    log.info(
        f"notify() — topic='{resolved_topic}' priority='{resolved_priority}' "
        f"title='{title}' message='{message[:60]}{'...' if len(message) > 60 else ''}'"
    )

    if not resolved_topic:
        log.error("NTFY_TOPIC not set — cannot send notification")
        return "Notify error: NTFY_TOPIC is not configured."

    url     = f"{NTFY_SERVER}/{resolved_topic}"
    headers = {
        "Title":        title,
        "Priority":     resolved_priority,
        "Content-Type": "text/plain",
    }
    if tags:
        headers["Tags"] = ",".join(tags)
        log.debug(f"Tags: {tags}")
    if action_url:
        headers["Click"] = action_url
        log.debug(f"Action URL: {action_url}")
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"

    try:
        log.debug(f"POST {url}")
        resp = requests.post(
            url,
            data=message.encode("utf-8"),
            headers=headers,
            timeout=TIMEOUT,
        )
        log.debug(f"Response {resp.status_code}")
        resp.raise_for_status()
        log.info(f"Notification sent successfully to topic '{resolved_topic}'")
        return f"Notification sent: '{message}'"

    except requests.exceptions.ConnectionError:
        log.error(f"Connection failed to ntfy server: {NTFY_SERVER}", exc_info=True)
        return "Notify error: Could not reach ntfy server."
    except Exception as e:
        log.error(f"notify() failed — {e}", exc_info=True)
        return f"Notify error: {e}"


# ── Convenience wrappers ──────────────────────────────────────────────────────

def notify_reminder(message: str) -> str:
    log.info(f"notify_reminder() — '{message}'")
    return notify(message, title="HZL Reminder", priority="high", tags=["bell"])


def notify_alert(message: str) -> str:
    log.info(f"notify_alert() — '{message}'")
    return notify(message, title="HZL Alert", priority="urgent", tags=["warning"])


def notify_info(message: str) -> str:
    log.info(f"notify_info() — '{message}'")
    return notify(message, title="HZL AI", priority="low", tags=["information_source"])


def notify_morning_brief_done() -> str:
    log.info("notify_morning_brief_done() called")
    return notify(
        "Your morning brief is ready. Good morning!",
        title="HZL AI — Morning Brief",
        priority="default",
        tags=["sunrise"],
    )


# ── Test CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "HZL AI test notification"
    print(notify(msg))
