# hazel_ambient.py — optimized, cost-aware, robust

import threading
import time
import datetime
import os
import json
import hashlib
import anthropic
from pathlib import Path

client = anthropic.Anthropic()

# ── COST CONTROLS ──
INTERVAL_ACTIVE  = 120   # 2min  — daytime, awake hours
INTERVAL_IDLE    = 600   # 10min — evening wind-down
INTERVAL_NIGHT   = 1800  # 30min — late night/early morning
MIN_INTERVAL     = 45    # never fire faster than this regardless of triggers

# Token budgets
DECIDE_MAX_TOKENS   = 200
CONTEXT_MAX_CHARS   = 1200

# Panel persistence — survive restarts
PANEL_DIR = Path(os.path.expanduser("~/jarvis/ui/panels"))
PANEL_DIR.mkdir(parents=True, exist_ok=True)

# ── STATE ──
_last_context_hash = ""
_last_trigger_time = 0.0
_broadcast_fn      = None
_lock              = threading.Lock()
_last_panel        = ""

# Cache expensive data fetches
_cache = {}
CACHE_TTL = {
    "calendar": 300,
    "weather":  600,
    "facts":    3600,
    "creative": 300,
    "spotify":  60,
}

def start_ambient(broadcast_fn):  # disabled
    return  # ambient disabled  # disabled
    return  # ambient disabled
    global _broadcast_fn
    _broadcast_fn = broadcast_fn
    threading.Thread(target=_loop, daemon=True).start()
    print("[Ambient] Started.")

def _get_interval():  # patched — longer intervals

    h = datetime.datetime.now().hour
    if 0 <= h < 6:   return INTERVAL_NIGHT
    if 22 <= h < 24: return INTERVAL_IDLE
    if 18 <= h < 22: return INTERVAL_IDLE
    return INTERVAL_ACTIVE

def _loop():
    time.sleep(300)  # wait 5 min before first ambient fire
    while True:
        try:
            if not _interacting:
                _tick()
        except Exception as e:
            print(f"[Ambient] Loop error: {e}")
        time.sleep(_get_interval())

def _tick(forced=False):
    global _last_context_hash, _last_trigger_time

    now = time.time()
    if not forced and (now - _last_trigger_time) < MIN_INTERVAL:
        return
    _last_trigger_time = now

    with _lock:
        ctx = _build_context()
        ctx_hash = hashlib.md5(ctx.encode()).hexdigest()

        if ctx_hash == _last_context_hash and not forced:
            return
        _last_context_hash = ctx_hash

        decision = _decide(ctx)
        if decision:
            _execute(decision, ctx)

def _cached_fetch(key, fn, ttl=None):
    ttl = ttl or CACHE_TTL.get(key, 300)
    entry = _cache.get(key)
    if entry and (time.time() - entry["t"]) < ttl:
        return entry["v"]
    try:
        val = fn()
        _cache[key] = {"v": val, "t": time.time()}
        return val
    except Exception as e:
        print(f"[Ambient] Cache fetch '{key}' failed: {e}")
        return entry["v"] if entry else None

def _build_context():
    now = datetime.datetime.now()
    h = now.hour
    if 5  <= h < 9:  period = "early morning"
    elif 9  <= h < 12: period = "morning"
    elif 12 <= h < 14: period = "midday"
    elif 14 <= h < 17: period = "afternoon"
    elif 17 <= h < 20: period = "evening"
    elif 20 <= h < 23: period = "night"
    else:              period = "late night"

    lines = [
        f"Time: {now.strftime('%A %b %d, %I:%M %p')}",
        f"Period: {period}",
    ]

    cal = _cached_fetch("calendar", lambda: _fetch_calendar())
    if cal:
        lines.append(f"Calendar:\n{cal[:600]}")

    weather = _cached_fetch("weather", lambda: _fetch_weather())
    if weather:
        lines.append(f"Weather: {weather[:200]}")

    try:
        from memory import get_pending_reminders
        rem = get_pending_reminders()
        if rem:
            lines.append("Reminders: " + ", ".join([m for _, m in rem[:3]]))
    except: pass

    facts = _cached_fetch("facts", lambda: _fetch_facts(), ttl=3600)
    if facts:
        lines.append(f"Facts: {facts[:200]}")

    # Creative context — projects, journal, focus state
    creative = _cached_fetch("creative", lambda: _fetch_creative())
    if creative:
        lines.append(f"Creative: {creative[:300]}")

    # Spotify — what's playing
    spotify = _cached_fetch("spotify", lambda: _fetch_spotify(), ttl=60)
    if spotify:
        lines.append(f"Spotify: {spotify[:100]}")

    ctx = "\n".join(lines)
    return ctx[:CONTEXT_MAX_CHARS]

def _fetch_calendar():
    from gcal import get_upcoming_events
    return get_upcoming_events(max_results=8)

def _fetch_weather():
    from weather import get_weather
    return get_weather()

def _fetch_facts():
    from memory import get_all_facts
    facts = get_all_facts()
    if not facts: return ""
    return ", ".join([f"{k}: {v}" for _, k, v in facts[:5]])

def _fetch_creative():
    try:
        from creative import get_creative_context
        return get_creative_context()
    except Exception:
        return ""

def _fetch_spotify():
    try:
        from spotify import get_current_track
        track = get_current_track()
        if track:
            return f"{track.get('name','?')} — {track.get('artist','?')}"
        return ""
    except Exception:
        return ""

# ── Panel Persistence ─────────────────────────────────────────────────────────
def save_panel(label, html):
    """Persist generated panel HTML to disk."""
    safe = label.replace(" ", "_").replace("/", "_").lower()[:40]
    path = PANEL_DIR / f"{safe}.html"
    try:
        path.write_text(html, encoding="utf-8")
    except Exception as e:
        print(f"[Ambient] Panel save failed: {e}")

def load_panel(label):
    """Load previously generated panel HTML from disk."""
    safe = label.replace(" ", "_").replace("/", "_").lower()[:40]
    path = PANEL_DIR / f"{safe}.html"
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None

def _decide(ctx):
    global _last_panel
    system = (
        "You are Hazel's ambient display controller for a luxury creative AI assistant. "
        "The user is a multi-hyphenate creative: visual designer, photographer, writer, "
        "marketer, AI developer, theatre maker, film/TV producer, musician. "
        f"Last shown: {_last_panel or 'nothing'}. Don't repeat unless critical. "
        "Pick what single panel to show based on context. "
        "Panel options: calendar, weather, tasks, news, reminder, projects, journal, focus, energy, spotify, custom. "
        "Reply ONLY with compact JSON: "
        '{"panel":"<type>","label":"short label","prompt":"UI instructions","data":"key data to show"}'
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=DECIDE_MAX_TOKENS,
            system=system,
            messages=[{"role":"user","content":ctx}]
        )
        text = resp.content[0].text.strip().replace("```json","").replace("```","")
        decision = json.loads(text)
        _last_panel = decision.get("panel","")
        print(f"[Ambient] → {decision.get('panel')} ({decision.get('label','')})")
        return decision
    except Exception as e:
        print(f"[Ambient] Decide error: {e}")
        return None

def _execute(decision, ctx):
    label = decision.get("label", "hazel")
    # Include previously saved panel as base for evolution
    prev_html = load_panel(label)
    msg = {
        "type":    "generate_ui",
        "label":   label,
        "prompt":  decision.get("prompt", ""),
        "data":    decision.get("data", ctx[:400]),
        "ambient": True,
    }
    if prev_html:
        msg["prev"] = prev_html[:1800]
    if _broadcast_fn:
        _broadcast_fn(msg)

_interacting = False

def set_interacting(val: bool):
    global _interacting
    _interacting = val

def trigger_now(reason=""):
    if _interacting:
        return  # Don't fire ambient during active voice/chat interactions
    if reason:
        print(f"[Ambient] Trigger: {reason}")
    threading.Thread(target=lambda: _tick(forced=False), daemon=True).start()

def invalidate_cache(key=None):
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
