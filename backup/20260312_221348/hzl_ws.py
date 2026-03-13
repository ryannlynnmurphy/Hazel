import asyncio
import websockets
import json
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

_clients = set()
_loop = None
_last_state = {"state": "idle", "transcript": ""}
_on_message = None

def set_message_handler(fn):
    global _on_message
    _on_message = fn

def start_ws_server():
    global _loop
    threading.Thread(target=_start_http, daemon=True).start()
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_until_complete(_serve())

def _start_http():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/apikey":
                key = os.environ.get("ANTHROPIC_API_KEY", "")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"key": key}).encode())
            else:
                self.send_response(404)
                self.end_headers()
    server = HTTPServer(("localhost", 8766), Handler)
    server.socket.setsockopt(1, 2, 1)
    server.serve_forever()

async def _serve():
    async with websockets.serve(_handler, "localhost", 8765):
        print("[HZL UI] WebSocket server on ws://localhost:8765")
        print("[HZL UI] API key endpoint on http://localhost:8766/apikey")
        await asyncio.Future()

async def _handler(ws):
    _clients.add(ws)
    try:
        await ws.send(json.dumps(_last_state))
        async for msg in ws:
            try:
                data = json.loads(msg)
                if _on_message and data.get("type") in ("chat", "voice"):
                    threading.Thread(target=_on_message, args=(data,), daemon=True).start()
                elif data.get("type") == "action":
                    action = data.get("action", "")
                    def _do(a=action):
                        try:
                            import spotify as sp
                            if a == "spotify_pause":   sp.pause()
                            elif a == "spotify_skip":  sp.skip()
                            elif a == "spotify_prev":  sp.previous()
                        except Exception as e:
                            print(f"[Spotify] {e}")
                    threading.Thread(target=_do, daemon=True).start()
            except:
                pass
    finally:
        _clients.discard(ws)

def broadcast(data: dict):
    global _last_state
    _last_state = data
    if not _clients or _loop is None:
        return
    msg = json.dumps(data)
    asyncio.run_coroutine_threadsafe(_broadcast_all(msg), _loop)

async def _broadcast_all(msg):
    dead = set()
    for ws in _clients:
        try:
            await ws.send(msg)
        except:
            dead.add(ws)
    _clients.difference_update(dead)
