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
from websockets.server import WebSocketServerProtocol

# Local modules
try:
    from brain import get_response
except ImportError:
    logging.warning("brain.py not found — responses will be echoed")
    async def get_response(message, hint=None):
        return f"[brain.py missing] You said: {message}"

try:
    import spotify
    SPOTIFY_AVAILABLE = True
except ImportError:
    logging.warning("spotify.py not found — music controls disabled")
    SPOTIFY_AVAILABLE = False

try:
    from voice import start_listening, stop_listening
    VOICE_AVAILABLE = True
except ImportError:
    logging.warning("voice.py not found — mic control disabled")
    VOICE_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [HZL-WS] %(message)s')
log = logging.getLogger(__name__)

# Track all connected clients
CLIENTS: set[WebSocketServerProtocol] = set()


async def broadcast(payload: dict):
    """Send a message to all connected UI clients."""
    if not CLIENTS:
        return
    msg = json.dumps(payload)
    await asyncio.gather(
        *[client.send(msg) for client in CLIENTS],
        return_exceptions=True
    )


async def send(ws: WebSocketServerProtocol, payload: dict):
    """Send a message to a single client."""
    try:
        await ws.send(json.dumps(payload))
    except Exception as e:
        log.error(f"Send error: {e}")


async def handle_chat(ws: WebSocketServerProtocol, message: str, hint: str = None):
    """Process a chat message through brain.py and stream response back."""
    await broadcast({"type": "thinking"})
    log.info(f"Chat → hint={hint!r} msg={message[:60]!r}")

    try:
        # brain.py handles model routing (sonnet vs haiku) and action tag parsing
        response_text = await asyncio.to_thread(get_response, message, hint)
        await broadcast({"type": "speaking"})
        await broadcast({"type": "response", "text": response_text})
        await asyncio.sleep(0.5)
        await broadcast({"type": "idle"})
    except Exception as e:
        log.error(f"Brain error: {e}")
        await broadcast({"type": "response", "text": "Something went wrong. Please try again."})
        await broadcast({"type": "idle"})


async def handle_action(ws: WebSocketServerProtocol, data: dict):
    """Route action commands to the correct integration."""
    action = data.get("action", "")
    entity_id = data.get("entity_id", "")
    log.info(f"Action: {action!r} entity={entity_id!r}")

    # ── Spotify music controls ──
    if action in ("play_pause", "next", "previous"):
        if SPOTIFY_AVAILABLE:
            try:
                if action == "play_pause":
                    result = await asyncio.to_thread(spotify.toggle_playback)
                elif action == "next":
                    result = await asyncio.to_thread(spotify.next_track)
                elif action == "previous":
                    result = await asyncio.to_thread(spotify.previous_track)

                # Push updated music state to UI
                state = await asyncio.to_thread(spotify.get_current_track)
                if state:
                    await broadcast({
                        "type":    "music_state",
                        "track":   state.get("track",  ""),
                        "artist":  state.get("artist", ""),
                        "playing": state.get("playing", False),
                        "prog":    state.get("progress_ms", 0) // 1000,
                        "dur":     state.get("duration_ms", 0) // 1000,
                    })
            except Exception as e:
                log.error(f"Spotify error: {e}")
        else:
            log.warning("Spotify action received but spotify.py unavailable")

    else:
        log.warning(f"Unknown action: {action!r}")


async def handle_connection(ws: WebSocketServerProtocol):
    """Main handler for each WebSocket connection."""
    CLIENTS.add(ws)
    remote = ws.remote_address
    log.info(f"Client connected: {remote}")

    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                log.warning(f"Invalid JSON from {remote}: {raw[:80]}")
                continue

            msg_type = data.get("type", "")

            if msg_type == "chat":
                message = data.get("message", "").strip()
                hint    = data.get("hint", None)
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

            else:
                log.warning(f"Unknown message type: {msg_type!r}")

    except websockets.exceptions.ConnectionClosedOK:
        log.info(f"Client disconnected cleanly: {remote}")
    except websockets.exceptions.ConnectionClosedError as e:
        log.warning(f"Client disconnected with error: {remote} — {e}")
    except Exception as e:
        log.error(f"Handler error for {remote}: {e}")
    finally:
        CLIENTS.discard(ws)
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
        log.info("Shutdown requested — goodbye.")
