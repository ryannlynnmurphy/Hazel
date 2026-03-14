"""
integrations.py — HZL AI Unified Integration Layer
Single file to import in brain.py. Handles all new action tag parsing,
routing, system prompt injection, and error recovery.

Usage in brain.py:
    from integrations import parse_and_route, INTEGRATION_PROMPT

    # In build_system_prompt(), append:
    return existing_prompt + INTEGRATION_PROMPT

    # In your response handling loop, after existing parse_actions():
    integration_results = parse_and_route(response_text)
    # integration_results is a list of (tag, result) tuples for logging
"""

import re
from hzl_ws import broadcast as _broadcast
import os
from hzl_logger import get_logger

log = get_logger("integrations")

# ── Lazy imports with availability flags ──────────────────────────────────────
# Each integration is imported independently so one broken module
# doesn't take down the others.

def _try_import(module_name: str):
    try:
        mod = __import__(module_name)
        log.debug(f"Module loaded: {module_name}")
        return mod
    except ImportError as e:
        log.warning(f"Module '{module_name}' not available — {e}")
        return None
    except Exception as e:
        log.error(f"Module '{module_name}' failed to import — {e}", exc_info=True)
        return None

_spotify  = _try_import("spotify")
_todoist  = _try_import("todoist")
_news     = _try_import("news")
_notify   = _try_import("notify")
_shopping = _try_import("shopping")
_weather  = _try_import("weather")

# Report availability on startup
_status = {
    "spotify":  _spotify  is not None,
    "todoist":  _todoist  is not None,
    "news":     _news     is not None,
    "notify":   _notify   is not None,
    "shopping": _shopping is not None,
}
log.info(f"Integration status: { {k: '✓' if v else '✗' for k, v in _status.items()} }")


# ── System prompt block ───────────────────────────────────────────────────────

INTEGRATION_PROMPT = """
## HZL AI — Extended Integrations

### 🎵 Spotify
[SPOTIFY: play QUERY]        — Play a song, artist, or playlist by name
[SPOTIFY: pause]             — Pause playback
[SPOTIFY: skip]              — Skip to next track
[SPOTIFY: previous]          — Go back one track
[SPOTIFY: volume LEVEL]      — Set volume 0–100
[SPOTIFY: now_playing]       — What's currently playing
[SPOTIFY: queue QUERY]       — Add a track to the queue

### ✅ Todoist
[TASK: check]                — Read today's + overdue tasks
[TASK: add CONTENT | DUE]    — Add a task (DUE is optional, e.g. "tomorrow 3pm")
[TASK: done TASK_NAME]       — Mark a task complete by name

### 📰 News
[NEWS: headlines CATEGORY]   — Top headlines (general/technology/business/science/health/sports)
[NEWS: search QUERY]         — Search news by keyword

### 🔔 Phone Notifications (ntfy)
[NOTIFY: MESSAGE]            — Default push notification to phone
[NOTIFY: urgent MESSAGE]     — Urgent alert
[NOTIFY: reminder MESSAGE]   — Reminder notification with bell

### 🛒 Shopping List
[WEATHER: check]             — Show weather panel in the UI
[SHOP: check]                — Read the shopping list
[SHOP: add ITEM | QUANTITY]  — Add an item (quantity optional, default 1)
[SHOP: add_many ITEM1, ITEM2, ITEM3] — Add multiple items at once
[SHOP: remove ITEM]          — Remove / check off an item
[SHOP: clear]                — Clear the entire list

Rules:
- Strip all action tags from spoken responses — never read them aloud
- Only use [NOTIFY:] when the user explicitly asks to be notified, or for reminders
- Use [TASK: check] when asked about tasks, to-dos, or what's on the agenda
- Combine tags freely in one response, e.g. [TASK: add Buy milk | today] then [SHOP: add milk]
"""


# ── Action tag parser ─────────────────────────────────────────────────────────

def _parse_actions(text: str) -> list[tuple[str, any]]:
    """
    Extract all HZL action tags from a Claude response string.
    Returns list of (action_type, args) tuples.
    """
    actions = []

    # ── Spotify ──────────────────────────────────────────────────────────────
    for m in re.finditer(r'\[SPOTIFY:\s*(.+?)\]', text, re.IGNORECASE):
        raw = m.group(1).strip()
        cmd = raw.lower()
        if cmd.startswith("play "):
            actions.append(("spotify_play",       raw[5:].strip()))
        elif cmd == "pause":
            actions.append(("spotify_pause",       None))
        elif cmd == "skip":
            actions.append(("spotify_skip",        None))
        elif cmd == "previous":
            actions.append(("spotify_previous",    None))
        elif cmd.startswith("volume "):
            actions.append(("spotify_volume",      raw[7:].strip()))
        elif cmd == "now_playing":
            actions.append(("spotify_now_playing", None))
        elif cmd.startswith("queue "):
            actions.append(("spotify_queue",       raw[6:].strip()))
        else:
            log.warning(f"Unknown SPOTIFY tag: '{raw}'")

    # ── Todoist ───────────────────────────────────────────────────────────────
    for m in re.finditer(r'\[TASK:\s*(.+?)\]', text, re.IGNORECASE):
        raw = m.group(1).strip()
        cmd = raw.lower()
        if cmd == "check":
            actions.append(("task_check", None))
        if re.search(r"\[WEATHER[\s:]", response, re.I):
            actions.append(("weather_check", None))
        elif cmd.startswith("add "):
            parts   = raw[4:].strip().split("|", 1)
            content = parts[0].strip()
            due     = parts[1].strip() if len(parts) > 1 else None
            actions.append(("task_add", (content, due)))
        elif cmd.startswith("done "):
            actions.append(("task_done", raw[5:].strip()))
        else:
            log.warning(f"Unknown TASK tag: '{raw}'")

    # ── News ──────────────────────────────────────────────────────────────────
    for m in re.finditer(r'\[NEWS:\s*(.+?)\]', text, re.IGNORECASE):
        raw  = m.group(1).strip()
        cmd  = raw.lower()
        parts = raw.split(None, 1)
        if cmd.startswith("headlines"):
            cat = parts[1].strip() if len(parts) > 1 else "general"
            actions.append(("news_headlines", cat))
        elif cmd.startswith("search "):
            actions.append(("news_search", raw[7:].strip()))
        else:
            log.warning(f"Unknown NEWS tag: '{raw}'")

    # ── Weather ───────────────────────────────────────────────────────────────
    # ── Notify ────────────────────────────────────────────────────────────────
    for m in re.finditer(r'\[NOTIFY:\s*(.+?)\]', text, re.IGNORECASE):
        raw = m.group(1).strip()
        cmd = raw.lower()
        if cmd.startswith("urgent "):
            actions.append(("notify_urgent",    raw[7:].strip()))
        elif cmd.startswith("reminder "):
            actions.append(("notify_reminder",  raw[9:].strip()))
        else:
            actions.append(("notify_info",      raw))

    # ── Shopping ──────────────────────────────────────────────────────────────
    for m in re.finditer(r'\[SHOP:\s*(.+?)\]', text, re.IGNORECASE):
        raw = m.group(1).strip()
        cmd = raw.lower()
        if cmd == "check":
            actions.append(("shop_check", None))
        elif cmd.startswith("add_many "):
            items = raw[9:].strip().split(",")
            actions.append(("shop_add_many", items))
        elif cmd.startswith("add "):
            parts = raw[4:].strip().split("|", 1)
            item  = parts[0].strip()
            qty   = parts[1].strip() if len(parts) > 1 else "1"
            actions.append(("shop_add", (item, qty)))
        elif cmd.startswith("remove "):
            actions.append(("shop_remove", raw[7:].strip()))
        elif cmd == "clear":
            actions.append(("shop_clear", None))
        else:
            log.warning(f"Unknown SHOP tag: '{raw}'")

    if actions:
        log.debug(f"Parsed {len(actions)} action(s): {[a[0] for a in actions]}")

    return actions


# ── Action router ─────────────────────────────────────────────────────────────

def _route(action_type: str, args) -> str:
    """Route a single parsed action to the correct integration function."""

    log.info(f"Routing: {action_type}({repr(args)[:60]})")

    # ── Spotify ──────────────────────────────────────────────────────────────
    if not _spotify and action_type.startswith("spotify_"):
        return "Spotify integration is not available."

    if action_type == "spotify_play":
        result = _spotify.play(args)
        # parse "Playing 'TRACK' by ARTIST" from result string
        import re as _re
        m = _re.search(r"Playing .(.+?). by (.+?)[.(]", result)
        if m:
            _broadcast({"type": "spotify", "track": m.group(1), "artist": m.group(2).strip(), "progress": 15})
        else:
            _broadcast({"type": "spotify", "track": args, "artist": "", "progress": 15})
        return result
    if action_type == "spotify_pause":       return _spotify.pause()
    if action_type == "spotify_skip":        return _spotify.skip()
    if action_type == "spotify_previous":    return _spotify.previous()
    if action_type == "spotify_now_playing": return _spotify.now_playing()
    if action_type == "spotify_volume":
        try:
            return _spotify.set_volume(int(args))
        except ValueError:
            log.warning(f"Invalid volume value: '{args}'")
            return f"Invalid volume: '{args}'"
    if action_type == "spotify_queue":       return _spotify.queue_track(args)

    # ── Todoist ───────────────────────────────────────────────────────────────
    if not _todoist and action_type.startswith("task_"):
        return "Todoist integration is not available."

    if action_type == "task_check":
        result = _todoist.get_tasks()
        _broadcast({"type": "tasks", "text": result})
        return result
    if action_type == "task_done":  return _todoist.complete_task(args)
    if action_type == "task_add":
        content, due = args
        result = _todoist.add_task(content, due_string=due)
        _broadcast({"type": "notify", "message": f"Task added: {content}"})
        return result

    # ── News ──────────────────────────────────────────────────────────────────
    if not _news and action_type.startswith("news_"):
        return "News integration is not available."

    if action_type == "news_headlines":
        result = _news.get_top_headlines(category=args)
        _broadcast({"type": "news", "text": result})
        return result
    if action_type == "news_search":
        result = _news.search_news(query=args)
        _broadcast({"type": "news", "text": result})
        return result

    # ── Weather ───────────────────────────────────────────────────────────────
    # ── Notify ────────────────────────────────────────────────────────────────
    # ── Weather ───────────────────────────────────────────────────────────────

    # ── Weather ───────────────────────────────────────────────────────────────
    if action_type == "weather_check":
        try:
            result = _weather.get_weather() if _weather else "Weather unavailable."
            _broadcast({"type": "weather", "text": result})
            return result
        except Exception as e:
            return f"Weather error: {e}"

    if not _notify and action_type.startswith("notify_"):
        return "Notify integration is not available."

    if action_type == "notify_urgent":   return _notify.notify_alert(args)
    if action_type == "notify_reminder": return _notify.notify_reminder(args)
    if action_type == "notify_info":     return _notify.notify_info(args)

    # ── Shopping ──────────────────────────────────────────────────────────────
    if not _shopping and action_type.startswith("shop_"):
        return "Shopping integration is not available."

    if action_type == "shop_check":
        result = _shopping.get_list()
        _broadcast({"type": "shopping", "text": result})
        return result
    if action_type == "shop_clear":    return _shopping.clear_list()
    if action_type == "shop_remove":   return _shopping.remove_item(args)
    if action_type == "shop_add_many":
        result = _shopping.add_multiple(args)
        _broadcast({"type": "notify", "message": f"Added to shopping list"})
        return result
    if action_type == "shop_add":
        item, qty = args
        result = _shopping.add_item(item, qty)
        _broadcast({"type": "notify", "message": f"Added {item} to shopping list"})
        return result

    log.warning(f"Unrecognised action type: '{action_type}'")
    return f"Unknown action: {action_type}"


# ── Public entry point ────────────────────────────────────────────────────────

def parse_and_route(response_text: str) -> list[tuple[str, str]]:
    """
    Parse all HZL action tags from a Claude response and execute them.

    Args:
        response_text: Raw Claude response string

    Returns:
        List of (action_type, result_string) tuples.
        Empty list if no tags found.
    """
    actions = _parse_actions(response_text)
    if not actions:
        return []

    results = []
    for action_type, args in actions:
        try:
            result = _route(action_type, args)
            log.info(f"  ↳ {action_type} → {result[:80]}{'...' if len(result) > 80 else ''}")
            results.append((action_type, result))
        except Exception as e:
            log.error(f"  ↳ {action_type} raised unhandled exception — {e}", exc_info=True)
            results.append((action_type, f"Error: {e}"))

    return results


def get_status() -> str:
    """Return a human-readable integration status string."""
    lines = ["HZL AI Integration Status:"]
    for name, available in _status.items():
        icon = "✓" if available else "✗"
        lines.append(f"  {icon}  {name}")
    return "\n".join(lines)


# ── Test CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(get_status())
    print()

    # Test parsing
    test_response = """
    Sure! [SPOTIFY: play lo-fi beats] [TASK: check] [NEWS: headlines technology]
    I'll also send you a reminder. [NOTIFY: reminder Your coffee is ready]
    And I added milk to your list. [SHOP: add milk]
    """
    print("Testing parse_and_route() with sample response...")
    results = parse_and_route(test_response)
    for action, result in results:
        print(f"  {action}: {result}")
