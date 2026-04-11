#!/usr/bin/env python3
"""
HZL AI · WebSocket Server  (hzl_ws.py)
Patched for hazel-v5.html

Message contract (UI → server):
  { type: 'chat',            message: str, hint: str }
  { type: 'action',          action: 'play_pause'|'next'|'previous' }
  { type: 'action',          action: 'turn_on'|'turn_off', entity_id: str }
  { type: 'start_listening' }
  { type: 'stop_listening'  }

Message contract (server → UI):
  { type: 'response',        text: str }
  { type: 'speaking'  }
  { type: 'listening' }
  { type: 'thinking'  }
  { type: 'idle'      }
  { type: 'music_state', track: str, artist: str, playing: bool, prog: int, dur: int }
  { type: 'weather_state',   temp, feels, hum, wind, uv, cond }
  { type: 'calendar_state',  events: [ {time, name, sub, accent} ] }
  { type: 'email_state',     emails: [ {av, from, subj, prev, time, unread} ] }
  { type: 'home_state',      devices: [ {id, name, icon, on, val?} ] }
"""

import asyncio
import json
import logging
import os
import websockets
from websockets.asyncio.server import ServerConnection

# Security
from hzl_security.ws_auth import WSRateLimiter, sanitize_ws_input

# Cluster routing
from hzl_cluster.integration import get_routing_context, record_routing_outcome, shutdown_integration

_rate_limiter = WSRateLimiter(max_messages=10, window_seconds=10)

# Local modules
try:
    from brain import get_response, get_last_actions
except ImportError:
    logging.warning("brain.py not found — responses will be echoed")
    async def get_response(message, hint=None):
        return f"[brain.py missing] You said: {message}"
    def get_last_actions():
        return []

try:
    import spotify
    from spotify import now_playing_structured, recently_played, get_queue, get_library, play, pause, skip, previous
    SPOTIFY_AVAILABLE = True
except ImportError:
    logging.warning("spotify.py not found — music controls disabled")
    SPOTIFY_AVAILABLE = False
try:
    from voice import speak as _speak
    VOICE_AVAILABLE = True
except Exception:
    VOICE_AVAILABLE = False
    def _speak(text): pass

try:
    from voice import start_listening, stop_listening
    VOICE_AVAILABLE = True
except ImportError:
    logging.warning("voice.py not found — mic control disabled")
    VOICE_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [HZL-WS] %(message)s')
log = logging.getLogger(__name__)

# Track all connected clients
CLIENTS: set[ServerConnection] = set()
_chat_lock = asyncio.Lock()  # Prevent concurrent chat processing


async def broadcast(payload: dict):
    """Send a message to all connected UI clients."""
    if not CLIENTS:
        return
    msg = json.dumps(payload)
    await asyncio.gather(
        *[client.send(msg) for client in CLIENTS],
        return_exceptions=True
    )


async def send(ws: ServerConnection, payload: dict):
    """Send a message to a single client."""
    try:
        await ws.send(json.dumps(payload))
    except Exception as e:
        log.error(f"Send error: {e}")



async def refresh_panels():
    """Push updated calendar and email state to all clients."""
    # Calendar
    try:
        from gcal import get_upcoming_events
        raw = await asyncio.to_thread(get_upcoming_events, 30)
        events = []
        if isinstance(raw, str) and raw and not raw.startswith("No upcoming") and not raw.startswith("Calendar error"):
            for line in raw.strip().splitlines():
                if ": " in line:
                    time_part, name_part = line.split(": ", 1)
                    events.append({"time": time_part.strip(), "name": name_part.strip(), "sub": "", "accent": "gold"})
        if events:
            await broadcast({"type": "calendar_state", "events": events})
            log.info(f"Calendar panel refreshed: {len(events)} events")
    except Exception as e:
        log.warning(f"Calendar refresh failed: {e}")

    # Email
    try:
        from gmail import get_unread_emails
        raw = await asyncio.to_thread(get_unread_emails, 5, True)
        emails = []
        if isinstance(raw, list):
            for item in raw:
                emails.append({"from": item.get("from",""), "subj": item.get("subject",""), "snippet": item.get("snippet",""), "id": item.get("id","")})
        if emails:
            await broadcast({"type": "email_state", "emails": emails})
    except Exception as e:
        log.warning(f"Email refresh failed: {e}")


async def handle_gateway_action(cmd: str) -> None:
    """Send gateway commands to the orchestrator."""
    from hzl_cluster.queue_hub import HazelMessage
    import aiohttp

    ORCHESTRATOR_URL = os.environ.get("HZL_ORCHESTRATOR_URL", "http://localhost:9000")
    GATEWAY_URL = os.environ.get("HZL_GATEWAY_URL", "http://localhost:9010")

    try:
        if cmd == "sync":
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{GATEWAY_URL}/sync") as resp:
                    result = await resp.json()
                    log.info(f"[Gateway] Sync result: {result}")

        elif cmd in ("fetch_email", "fetch_weather", "fetch_news"):
            action_map = {
                "fetch_email": "fetch.email",
                "fetch_weather": "fetch.weather",
                "fetch_news": "fetch.news",
            }
            msg = HazelMessage.create(
                source="hazel-core",
                destination="gateway",
                msg_type="fetch",
                action=action_map[cmd],
                payload={},
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{ORCHESTRATOR_URL}/ingest",
                    json={"messages": [msg.to_dict()]},
                ) as resp:
                    result = await resp.json()
                    log.info(f"[Gateway] Queued {cmd}: {result}")

        elif cmd == "lock":
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{GATEWAY_URL}/lock") as resp:
                    log.info(f"[Gateway] Locked: {await resp.json()}")

        elif cmd == "unlock":
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{GATEWAY_URL}/unlock") as resp:
                    log.info(f"[Gateway] Unlocked: {await resp.json()}")

        elif cmd == "emergency":
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{GATEWAY_URL}/emergency") as resp:
                    log.info(f"[Gateway] Emergency: {await resp.json()}")

        elif cmd == "status":
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{GATEWAY_URL}/state") as resp:
                    result = await resp.json()
                    log.info(f"[Gateway] Status: {result}")

    except Exception as e:
        log.error(f"[Gateway] Action {cmd} failed: {e}")


async def handle_queue_action(cmd: str, params: dict) -> None:
    """Queue outbound messages for next sync cycle."""
    from hzl_cluster.queue_hub import HazelMessage
    import aiohttp

    ORCHESTRATOR_URL = os.environ.get("HZL_ORCHESTRATOR_URL", "http://localhost:9000")

    try:
        if cmd == "send_email":
            msg = HazelMessage.create(
                source="hazel-core",
                destination="gateway",
                msg_type="send",
                action="send.email",
                payload={
                    "to": params.get("to", ""),
                    "subject": params.get("subject", ""),
                    "body": params.get("body", ""),
                },
            )
        elif cmd == "send_message":
            msg = HazelMessage.create(
                source="hazel-core",
                destination="gateway",
                msg_type="send",
                action="send.message",
                payload={
                    "to": params.get("to", ""),
                    "body": params.get("body", ""),
                    "via": params.get("via", "signal"),
                },
            )
        else:
            log.warning(f"[Queue] Unknown cmd: {cmd}")
            return

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ORCHESTRATOR_URL}/ingest",
                json={"messages": [msg.to_dict()]},
            ) as resp:
                result = await resp.json()
                log.info(f"[Queue] Queued {cmd}: {result}")

    except Exception as e:
        log.error(f"[Queue] Action {cmd} failed: {e}")


async def handle_chat(ws: ServerConnection, message: str, hint: str = None):
    """Process a chat message through brain.py and stream response back."""
    if _chat_lock.locked():
        log.info("Hazel busy -- dropping message")
        return
    async with _chat_lock:
        await _handle_chat_inner(ws, message, hint)


async def _handle_chat_inner(ws: ServerConnection, message: str, hint: str = None):
    await broadcast({"type": "thinking"})
    log.info(f"Chat -> hint={hint!r} msg={message[:60]!r}")

    try:
        # Get routing decision from orchestrator (model + max_tokens)
        import time as _time
        ctx = await get_routing_context(message)
        log.info(f"Routed -> task={ctx.task_type} model={ctx.model} tokens={ctx.max_tokens} node={ctx.node_hostname or 'local'}")
        t0 = _time.monotonic()

        # Check if message contains a URL -- fetch via Tavily
        import re as _re2
        url_match = _re2.search(r'(https?://[^\s]+)', message)
        # Check if message is a web search request
        search_match = _re2.search(r'(?:search|look up|google|find out|what is|who is|tell me about)\s+(.+)', message, _re2.IGNORECASE)
        if url_match:
            url = url_match.group(1)
            log.info(f"Fetching article via Tavily: {url}")
            try:
                from search import web_search
                article_content = await asyncio.to_thread(web_search, f"site:{url} full article")
                if article_content and "error" not in article_content.lower():
                    augmented = f"{message}\n\n[Article content from Tavily]:\n{article_content}"
                    response_text = await asyncio.to_thread(get_response, augmented, hint, ctx.model, ctx.max_tokens)
                else:
                    topic = message.split(' - ')[-1] if ' - ' in message else message
                    search_result = await asyncio.to_thread(web_search, topic[:100])
                    augmented = f"{message}\n\n[Related info from web search]:\n{search_result}"
                    response_text = await asyncio.to_thread(get_response, augmented, hint, ctx.model, ctx.max_tokens)
            except Exception as e:
                log.warning(f"Tavily fetch failed: {e}")
                response_text = await asyncio.to_thread(get_response, message, hint, ctx.model, ctx.max_tokens)
        elif search_match:
            query = search_match.group(1).strip()
            log.info(f"Web search via Tavily: {query}")
            try:
                from search import web_search
                search_result = await asyncio.to_thread(web_search, query)
                augmented = f"{message}\n\n[Web search results from Tavily]:\n{search_result}"
                response_text = await asyncio.to_thread(get_response, augmented, hint, ctx.model, ctx.max_tokens)
            except Exception as e:
                log.warning(f"Tavily search failed: {e}")
                response_text = await asyncio.to_thread(get_response, message, hint, ctx.model, ctx.max_tokens)
        elif _re2.search(r'(?:read|summarize|open).*?email.*?from\s+(.+?)(?:\s+about|$)', message, _re2.IGNORECASE):
            email_read = _re2.search(r'(?:read|summarize|open).*?email.*?from\s+(.+?)(?:\s+about|$)', message, _re2.IGNORECASE)
            from gmail import get_email_body
            sender = email_read.group(1).strip()
            email_body = await asyncio.to_thread(get_email_body, sender)
            augmented = f"{message}\n\n[Email content fetched]:\n{email_body}"
            response_text = await asyncio.to_thread(get_response, augmented, hint, ctx.model, ctx.max_tokens)
        else:
            response_text = await asyncio.to_thread(get_response, message, hint, ctx.model, ctx.max_tokens)

        # Record success outcome for circuit breaker
        elapsed_ms = (_time.monotonic() - t0) * 1000
        record_routing_outcome(ctx, success=True, latency_ms=elapsed_ms)
        await broadcast({"type": "speaking"})
        # Strip action tags for display, keep raw for Spotify/panel parsing below
        import re as _re_clean
        display_text = _re_clean.sub(r'\[[A-Z_]+:[^\]]*\]', '', response_text).strip()
        await broadcast({"type": "response", "text": display_text})
        
        # Refresh meds UI if medication-related conversation
        med_keywords = ['medication', 'medicine', 'pill', 'take', 'took', 'taking', 'prescription', 'dose', 'vitamin', 'supplement', 'penicillin', 'antibiotic', 'probiotic', 'melatonin']
        if any(kw in message.lower() for kw in med_keywords):
            # Try to extract and add medication from user message
            try:
                import re
                from health import add_medication, log_medication_taken, get_medications, get_medication_log_today
                msg_lower = message.lower()
                
                # Pattern: "i take X" or "i'm taking X"
                add_match = re.search(r"i(?:'m)?\s+(?:take|taking)\s+(.+?)(?:\s+(?:twice|once|three times|every|at|in the|daily|weekly)|\s*$)", msg_lower)
                if add_match:
                    med_name = add_match.group(1).strip().title()
                    # Extract frequency
                    freq = "daily"
                    times = ["09:00"]
                    if "twice" in msg_lower:
                        freq = "twice daily"
                        times = ["09:00", "21:00"]
                    elif "night" in msg_lower or "evening" in msg_lower or "bedtime" in msg_lower:
                        times = ["21:00"]
                    elif "morning" in msg_lower:
                        times = ["09:00"]
                    
                    # Check if already exists
                    existing = [m["name"].lower() for m in get_medications()]
                    if med_name.lower() not in existing:
                        add_medication(med_name, None, freq, times)
                        log.info(f"Auto-added medication: {med_name}")
                
                # Pattern: "i took X" or "just took X"
                took_match = re.search(r"(?:i\s+)?(?:just\s+)?took\s+(?:my\s+)?(.+?)(?:\s|$)", msg_lower)
                if took_match:
                    med_name = took_match.group(1).strip()
                    log_medication_taken(med_name)
                    log.info(f"Logged medication taken: {med_name}")
            except Exception as e:
                log.warning(f"Med auto-parse failed: {e}")
            
            try:
                meds = get_medications()
                taken_today = {m["name"] for m in get_medication_log_today()}
                med_icons = {"vitamin": "💊", "omega": "🐟", "iron": "🩸", "probiotic": "🦠", "default": "💊"}
                med_list = []
                for m in meds:
                    icon = "💊"
                    for k, v in med_icons.items():
                        if k in m["name"].lower():
                            icon = v
                            break
                    med_list.append({
                        "name": m["name"],
                        "dose": m["dose"] or "",
                        "time": m["times"][0] if m["times"] else "",
                        "taken": m["name"] in taken_today,
                        "icon": icon,
                        "refill": False
                    })
                await broadcast({"type": "meds_state", "medications": med_list})
                log.info("Medications UI refreshed after health action")
            except Exception as e:
                log.warning(f"Meds refresh failed: {e}")
        if VOICE_AVAILABLE:
            import re as _re2
            clean = _re2.sub(r'\[.*?\]', '', response_text).strip()
            asyncio.create_task(asyncio.to_thread(_speak, clean))
        # Parse Spotify action tags from Claude response
        import re as _re3
        sp_play = _re3.search(r'\[SPOTIFY:\s*play\s+(.+?)\]', response_text, _re3.IGNORECASE)
        sp_pause = _re3.search(r'\[SPOTIFY:\s*pause\]', response_text, _re3.IGNORECASE)
        sp_skip = _re3.search(r'\[SPOTIFY:\s*skip\]', response_text, _re3.IGNORECASE)
        sp_prev = _re3.search(r'\[SPOTIFY:\s*previous\]', response_text, _re3.IGNORECASE)
        if SPOTIFY_AVAILABLE:
            if sp_play:
                query = sp_play.group(1).strip()
                result = await asyncio.to_thread(play, query)
                music_data = await asyncio.to_thread(now_playing_structured)
                recent = await asyncio.to_thread(recently_played, 5)
                await broadcast({"type": "music_state", **music_data, "recent": recent})
            elif sp_pause:
                await asyncio.to_thread(pause)
            elif sp_skip:
                await asyncio.to_thread(skip)
                music_data = await asyncio.to_thread(now_playing_structured)
                recent = await asyncio.to_thread(recently_played, 5)
                await broadcast({"type": "music_state", **music_data, "recent": recent})
            elif sp_prev:
                await asyncio.to_thread(previous)
                music_data = await asyncio.to_thread(now_playing_structured)
                recent = await asyncio.to_thread(recently_played, 5)
                await broadcast({"type": "music_state", **music_data, "recent": recent})
        # Also handle plain play/pause/skip from message keywords
        if SPOTIFY_AVAILABLE and not any([sp_play, sp_pause, sp_skip, sp_prev]):
            msg_l = message.lower()
            if any(w in msg_l for w in ['pause music','pause spotify','stop music']):
                await asyncio.to_thread(pause)
            elif any(w in msg_l for w in ['skip','next track','next song']):
                await asyncio.to_thread(skip)
                music_data = await asyncio.to_thread(now_playing_structured)
                recent = await asyncio.to_thread(recently_played, 5)
                await broadcast({"type": "music_state", **music_data, "recent": recent})
            elif any(w in msg_l for w in ['previous track','previous song','go back']):
                await asyncio.to_thread(previous)
        # Auto-open panel and refresh data based on message keywords
        import re as _re
        msg_lower = message.lower()
        panel_match = _re.search(r'\[PANEL:\s*(\w+)\]', response_text)
        if panel_match:
            await broadcast({"type": "panel_open", "panel": panel_match.group(1).lower()})
        elif any(w in msg_lower for w in ['calendar','schedule','week','meeting','event']):
            await broadcast({"type": "panel_open", "panel": "calendar"})
            try:
                from gcal import get_upcoming_events as _gcal_get
                raw = await asyncio.to_thread(_gcal_get, 30)
                events = []
                if isinstance(raw, str) and raw and not raw.startswith("No upcoming") and not raw.startswith("Calendar error"):
                    for line in raw.strip().splitlines():
                        if ": " in line:
                            time_part, name_part = line.split(": ", 1)
                            events.append({"time": time_part.strip(), "name": name_part.strip(), "sub": "", "accent": "gold"})
                if events:
                    await broadcast({"type": "calendar_state", "events": events})
            except Exception:
                pass
        elif any(w in msg_lower for w in ['email','inbox','mail','message']):
            await broadcast({"type": "panel_open", "panel": "email"})
            try:
                from gmail import get_unread_emails as _gmail_get
                raw = await asyncio.to_thread(_gmail_get, 5, True)
                if isinstance(raw, list):
                    emails = [{"from": item.get("from",""), "subj": item.get("subject",""), "snippet": item.get("snippet",""), "id": item.get("id","")} for item in raw]
                    if emails:
                        await broadcast({"type": "email_state", "emails": emails})
            except Exception:
                pass
        elif any(w in msg_lower for w in ['weather','temperature','forecast','rain','wind']):
            await broadcast({"type": "panel_open", "panel": "weather"})
            try:
                from weather import get_weather_structured as _weather_get
                w = await asyncio.to_thread(_weather_get)
                if w:
                    await broadcast({"type": "weather_state", **w})
            except Exception:
                pass
        elif any(w in msg_lower for w in ['music','spotify','song','playing','track']):
            await broadcast({"type": "panel_open", "panel": "music"})
            if SPOTIFY_AVAILABLE:
                try:
                    music_data = await asyncio.to_thread(now_playing_structured)
                    recent = await asyncio.to_thread(recently_played, 5)
                    queue_data = await asyncio.to_thread(get_queue, 5)
                    library_data = await asyncio.to_thread(get_library, 20)
                    await broadcast({"type": "music_state", **music_data, "recent": recent, "queue": queue_data, "library": library_data})
                except Exception:
                    pass
        elif any(w in msg_lower for w in ['news','headline','story']):
            await broadcast({"type": "panel_open", "panel": "news"})
            try:
                from news import get_headlines_structured as _news_get
                news = await asyncio.to_thread(_news_get, "general", 5)
                if news:
                    await broadcast({"type": "news_state", "news": news})
            except Exception:
                pass

        # Dispatch GATEWAY and QUEUE actions parsed by brain.py
        for action in get_last_actions():
            if action.get("tag") == "GATEWAY":
                cmd = action.get("cmd", "")
                await handle_gateway_action(cmd)
            elif action.get("tag") == "QUEUE":
                cmd = action.get("cmd", "")
                params = action.get("params", {})
                await handle_queue_action(cmd, params)

    except Exception as e:
        log.error(f"Brain error: {e}")
        await broadcast({"type": "response", "text": "Something went wrong. Please try again."})
        # Record failure outcome for circuit breaker
        try:
            record_routing_outcome(ctx, success=False)
        except Exception:
            pass
    finally:
        await broadcast({"type": "idle"})


async def handle_action(ws: ServerConnection, data: dict):
    """Route action commands to the correct integration."""
    action = data.get("action", "")
    entity_id = data.get("entity_id", "")
    log.info(f"Action: {action!r} entity={entity_id!r}")

    # ── Spotify music controls ──
    if action in ("play", "pause", "skip", "previous"):
        if SPOTIFY_AVAILABLE:
            try:
                if action == "play":
                    result = await asyncio.to_thread(play)
                elif action == "pause":
                    result = await asyncio.to_thread(pause)
                elif action == "skip":
                    result = await asyncio.to_thread(skip)
                elif action == "previous":
                    result = await asyncio.to_thread(previous)
                await asyncio.sleep(0.6)
                music_data = await asyncio.to_thread(now_playing_structured)
                recent = await asyncio.to_thread(recently_played, 5)
                queue = await asyncio.to_thread(get_queue, 5)
                library = await asyncio.to_thread(get_library, 20)
                await broadcast({"type": "music_state", **music_data, "recent": recent, "queue": queue, "library": library})
            except Exception as e:
                log.error(f"Spotify action error: {e}")
        else:
            log.warning("Spotify action received but spotify.py unavailable")

    else:
        log.warning(f"Unknown action: {action!r}")







async def push_on_connect(ws):
    """Push real data to a newly connected UI client."""
    # NOTE: API key is no longer sent to clients — keys stay server-side only

    # ── Weather (returns a plain string) ──
    try:
        from weather import get_weather_structured
        w = await asyncio.to_thread(get_weather_structured)
        if w:
            await ws.send(json.dumps({"type": "weather_state", **w}))
            log.info(f"Weather pushed: {w['temp']}°F feels {w['feels']}°F")
    except Exception as e:
        log.warning(f"Weather push failed: {e}")

    # ── Calendar (returns newline-joined string "Day Month DD at HH:MM AM: Title") ──
    try:
        from gcal import get_upcoming_events
        raw = await asyncio.to_thread(get_upcoming_events, 30)
        events = []
        if isinstance(raw, str) and raw and not raw.startswith("No upcoming") and not raw.startswith("Calendar error"):
            for line in raw.strip().splitlines():
                if ": " in line:
                    time_part, name_part = line.split(": ", 1)
                    events.append({"time": time_part.strip(), "name": name_part.strip(), "sub": "", "accent": "gold"})
        if events:
            await ws.send(json.dumps({"type": "calendar_state", "events": events}))
    except Exception as e:
        log.warning(f"Calendar push failed: {e}")

    # ── Email ──
    try:
        from gmail import get_unread_emails
        raw = await asyncio.to_thread(get_unread_emails, 5, True)
        emails = []
        if isinstance(raw, list):
            for item in raw:
                emails.append({"from": item.get("from",""), "subj": item.get("subject",""), "snippet": item.get("snippet",""), "id": item.get("id","")})
        if emails:
            await ws.send(json.dumps({"type": "email_state", "emails": emails}))
    except Exception as e:
        log.warning(f"Email push failed: {e}")

    # ── Contacts ──
    try:
        from contacts import get_all as get_contacts
        contacts = await asyncio.to_thread(get_contacts)
        if contacts:
            contact_list = [{"name": c.get("name",""), "email": c.get("email",""), "phone": c.get("phone",""), "note": c.get("note","")} for c in contacts]
            await ws.send(json.dumps({"type": "contacts_state", "contacts": contact_list}))
            log.info(f"Contacts pushed: {len(contact_list)}")
    except Exception as e:
        log.warning(f"Contacts push failed: {e}")

    # ── Medications ──
    try:
        from health import get_medications, get_medication_log_today
        meds = get_medications()
        taken_today = {m["name"] for m in get_medication_log_today()}
        med_icons = {"vitamin": "💊", "omega": "🐟", "iron": "🩸", "probiotic": "🦠", "default": "💊"}
        med_list = []
        for m in meds:
            icon = "💊"
            for k, v in med_icons.items():
                if k in m["name"].lower():
                    icon = v
                    break
            med_list.append({
                "name": m["name"],
                "dose": m["dose"] or "",
                "time": m["times"][0] if m["times"] else "",
                "taken": m["name"] in taken_today,
                "icon": icon,
                "refill": False
            })
        await ws.send(json.dumps({"type": "meds_state", "medications": med_list}))
        log.info(f"Medications pushed: {len(med_list)}")
    except Exception as e:
        log.warning(f"Medications push failed: {e}")

    # ── News ──
    try:
        from news import get_headlines_structured
        news = await asyncio.to_thread(get_headlines_structured, "general", 5)
        if news:
            await ws.send(json.dumps({"type": "news_state", "news": news}))
            log.info(f"News pushed: {len(news)} articles")
    except Exception as e:
        log.warning(f"News push failed: {e}")

    # ── Spotify ──
    if SPOTIFY_AVAILABLE:
        try:
            music_data = await asyncio.to_thread(now_playing_structured)
            recent = await asyncio.to_thread(recently_played, 5)
            queue_data = await asyncio.to_thread(get_queue, 5)
            library_data = await asyncio.to_thread(get_library, 20)
            await ws.send(json.dumps({"type": "music_state", **music_data, "recent": recent, "queue": queue_data, "library": library_data}))
        except Exception as e:
            log.warning(f"Spotify push failed: {e}")


async def handle_connection(ws: ServerConnection):
    """Main handler for each WebSocket connection."""
    CLIENTS.add(ws)
    remote = ws.remote_address
    log.info(f"Client connected: {remote}")

    try:
        # Push real data to UI on connect
        asyncio.create_task(push_on_connect(ws))
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                log.warning(f"Invalid JSON from {remote}: {raw[:80]}")
                continue

            msg_type = data.get("type", "")

            if msg_type == "chat":
                # Rate limit per-client
                client_key = str(ws.remote_address)
                if not _rate_limiter.is_allowed(client_key):
                    await send(ws, {"type": "response", "text": "Slow down — too many messages. Try again in a moment."})
                    continue
                # Sanitize input
                raw_msg = data.get("message", "")
                is_safe, message = sanitize_ws_input(raw_msg)
                hint = data.get("hint", None)
                if message:
                    asyncio.create_task(handle_chat(ws, message, hint))

            elif msg_type == "action":
                asyncio.create_task(handle_action(ws, data))

            elif msg_type == "start_listening":
                log.info("Mic: start listening")
                await broadcast({"type": "listening"})
                if VOICE_AVAILABLE:
                    asyncio.create_task(asyncio.to_thread(start_listening))

            elif msg_type == "stop_listening":
                log.info("Mic: stop listening")
                await broadcast({"type": "idle"})
                if VOICE_AVAILABLE:
                    asyncio.create_task(asyncio.to_thread(stop_listening))

            elif msg_type == "news_category":
                category = data.get("category", "general")
                log.info(f"News category request: {category}")
                try:
                    from news import get_headlines_structured
                    news = await asyncio.to_thread(get_headlines_structured, category, 5)
                    if news:
                        await broadcast({"type": "news_state", "news": news})
                except Exception as e:
                    log.warning(f"News category fetch failed: {e}")

            else:
                log.warning(f"Unknown message type: {msg_type!r}")

    except websockets.exceptions.ConnectionClosedOK:
        log.info(f"Client disconnected cleanly: {remote}")
    except websockets.exceptions.ConnectionClosedError as e:
        log.warning(f"Client disconnected with error: {remote} -- {e}")
    except Exception as e:
        log.error(f"Handler error for {remote}: {e}")
    finally:
        CLIENTS.discard(ws)
        _rate_limiter.cleanup()
        log.info(f"Client removed: {remote} | Active clients: {len(CLIENTS)}")


async def main():
    host = os.getenv("HZL_WS_HOST", "localhost")
    port = int(os.getenv("HZL_WS_PORT", "8765"))

    log.info(f"HZL WebSocket server starting on ws://{host}:{port}")
    async with websockets.serve(handle_connection, host, port):
        log.info("Ready. Waiting for connections...")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(shutdown_integration())
        log.info("Shutdown requested -- goodbye.")

# ── Compatibility aliases for main.py ──
_LOOP = None

def broadcast_sync(payload: dict):
    """Thread-safe broadcast — works from any thread in Python 3.13."""
    global _LOOP
    if _LOOP is None or not _LOOP.is_running():
        log.warning("broadcast_sync: loop not ready, dropping: %s", payload.get("type"))
        return
    asyncio.run_coroutine_threadsafe(broadcast(payload), _LOOP)

def set_message_handler(fn):
    pass  # kept for main.py import compatibility

def start_ws_server():
    """Called by main.py in a thread."""
    global _LOOP
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _LOOP = loop
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
