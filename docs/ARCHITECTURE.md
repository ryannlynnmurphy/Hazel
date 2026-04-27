# Hazel — Architecture

Hazel is a locally hosted voice AI assistant targeting Raspberry Pi 5. All processing runs on-device except for three optional cloud APIs: Claude (LLM), ElevenLabs (TTS), and Tavily (web search). Every other integration — STT, memory, Google services, Spotify, smart home — runs through direct API calls or local storage.

---

## System Overview

```
Microphone
    |
    v
[voice.py] — arecord → Whisper STT
    |
    v
[main.py] — conversation loop + reminder checker
    |
    v
[hzl_ws.py] — asyncio WebSocket server (port 8765)
    |
    v
[brain.py] — model routing → Claude API
    |
    v
[Integrations] — gmail, gcal, smarthome, spotify, search, health, ...
    |
    v
[voice.py] — ElevenLabs TTS → aplay (speaker)
    |
    v
[hzl_ws.py] — broadcasts state to UI clients

Browser UI (Scatter OS — `ui/scatter.html`, root `/`) ←→ WebSocket ws://localhost:8765
```

---

## STT Pipeline

**File:** `voice.py`

1. `arecord` captures audio from the USB mic (`JARVIS_MIC_CARD` env var, auto-detected via `arecord -l` if unset) for a configurable duration (default 6 seconds, `JARVIS_RECORD_SECONDS`).
2. Audio is written to a temporary `.wav` file.
3. OpenAI Whisper (`openai-whisper` package) transcribes the wav locally. Model size defaults to `base`, configurable via `JARVIS_WHISPER_MODEL`. The model is loaded once and cached in memory.
4. Short/noise phrases (`"ok"`, `"uh"`, `"thanks"`, etc.) are filtered and discarded.
5. Transcribed text is passed to `handle_chat_input()` in `main.py`, then on to `brain.py`.

The Whisper model runs fully on-device. No audio ever leaves the Pi during transcription.

---

## Claude API Integration

**File:** `brain.py`

### Model Routing

Two models are used, selected per-message by keyword matching:

| Model | Usage |
|---|---|
| `claude-sonnet-4-5` | Complex reasoning, writing, code, explanations, planning |
| `claude-haiku-4-5-20251001` | Fast factual queries, simple commands |

Routing is handled by `choose_model()`, which runs a regex against the user message before the API call.

### System Prompt

`build_system_prompt()` constructs a fresh system prompt on every request, injecting:

- Current date and time
- Live weather (from Open-Meteo, cached 15 min)
- Upcoming calendar events (up to 8, from Google Calendar)
- Unread email summary (up to 6, from Gmail)
- Stored user facts (from SQLite `facts` table)
- Optional hint context (e.g., `"weather"`, `"calendar"`) passed from `hzl_ws.py`

This means Claude always has live context without requiring the user to ask for it explicitly.

### Conversation History

The last 12 message turns are retrieved from SQLite and included in the `messages` array on every API call. This gives Hazel short-term conversational memory.

### Action Tags

Claude embeds structured action tags in its responses. `parse_actions()` extracts and executes them before stripping them from the spoken/displayed text:

| Tag | Effect |
|---|---|
| `[REMINDER: HH:MM message]` | Saves a timed reminder to SQLite |
| `[SPOTIFY: play QUERY]` | Triggers Spotify playback |
| `[SPOTIFY: pause/skip/previous]` | Controls Spotify |
| `[GMAIL: check/search/send]` | Reads or sends email |
| `[GCAL: check/add]` | Reads or creates calendar events |
| `[ACTION: command entity]` | Controls a Home Assistant entity |
| `[HEALTH: add_med/took/remove_med]` | Manages medication tracking |
| `[PANEL: name]` | Instructs the UI to open a named panel |

---

## TTS Pipeline

**File:** `voice.py`

### Primary: ElevenLabs

- Voice ID: `Uc7anshoV8mdBhDnEZEX` (a custom "Hazel" voice)
- Model: `eleven_turbo_v2`
- API returns streamed MP3, written to a temp file
- `ffmpeg` converts MP3 to WAV (44100 Hz, stereo)
- `aplay` plays via `JARVIS_SPEAKER_CARD` (default `plughw:2,0`)

### Fallback: Piper (fully local)

If ElevenLabs fails or no API key is present, `_speak_piper()` is called:
- Model: `en_US-lessac-medium.onnx` (included in `voices/`)
- Piper binary runs on aarch64 (Raspberry Pi), piping text to stdout
- `aplay` plays the resulting WAV

Text is cleaned before TTS: action tags, markdown, and extra whitespace are stripped by `clean_for_speech()`.

---

## Database

**File:** `memory.py`, `health.py`  
**Engine:** SQLite  
**Path:** `~/jarvis/memory.db`

### Tables

| Table | Purpose |
|---|---|
| `conversations` | Full conversation history (role, content, session, timestamp) |
| `facts` | Persistent user facts (key/value, category) — survives restarts |
| `outputs` | References to generated documents/deliverables |
| `reminders` | Timed reminders with `fired` flag |
| `medications` | Tracked medications (name, dose, frequency, schedule) |
| `medication_log` | Daily log of medications taken |

The database is initialized on import of `memory.py`. It is never uploaded anywhere — all data stays on the Pi.

---

## WebSocket Server

**File:** `hzl_ws.py`  
**Port:** 8765 (configurable via `HZL_WS_HOST` / `HZL_WS_PORT`)

The WebSocket server is the central message bus between the browser UI, `main.py`, and all integrations. It runs as an asyncio event loop in a background thread started by `main.py`.

### Inbound message types (UI to server)

| Type | Description |
|---|---|
| `chat` | User text message with optional `hint` |
| `action` | Direct control (play, pause, skip, turn_on, turn_off) |
| `start_listening` | Activate microphone |
| `stop_listening` | Deactivate microphone |
| `news_category` | Request headlines for a category |

### Outbound message types (server to UI)

| Type | Description |
|---|---|
| `response` | Hazel's text response |
| `thinking` / `speaking` / `listening` / `idle` | State machine transitions |
| `weather_state` | Live weather data |
| `calendar_state` | Upcoming events list |
| `email_state` | Unread emails list |
| `music_state` | Spotify now playing, queue, library, recent |
| `meds_state` | Medication list with taken status |
| `news_state` | News headlines |
| `contacts_state` | Contact list |
| `panel_open` | Instructs UI to open a named panel |
| `init_key` | Passes config to UI on connect |

On each new connection, `push_on_connect()` immediately pushes current state for all panels.

---

## Integrations

### Gmail (`gmail.py`)
Google Gmail API via OAuth2. Reads unread emails (up to N), fetches email body by sender, sends email. Credentials stored in `credentials.json` + `token.json`.

### Google Calendar (`gcal.py`)
Google Calendar API via OAuth2. Lists upcoming events (plain text, formatted for injection into system prompt). Adds events with title, date, and optional time.

### Spotify (`spotify.py`)
`spotipy` library with `SpotifyOAuth`. Scopes: playback state, modify playback, recently played, playlist read, library read. Supports play (by search query), pause, skip, previous, now-playing, recently played, queue, library. Cache stored at `~/.spotify_cache`.

### Home Assistant (`smarthome.py`)
REST API at `HA_URL` (default `http://localhost:8123`). Supports `turn_on`, `turn_off`, `toggle`, `get_state`, `set_brightness`, and listing all light entities. Gracefully skips if `HA_TOKEN` is not set.

### Tavily Search (`search.py`)
`TavilyClient` for real-time web search. Used by `hzl_ws.py` when a message requests a news article URL or web lookup. Returns answer + top 2 result snippets.

### Weather (`weather.py`)
Open-Meteo free API. Lat/lon hardcoded to Garden City, NY. Returns temperature, feels-like, humidity, wind speed, UV index, sunrise/sunset. Cached for 15 minutes. No API key required.

### News (`news.py`)
News API. Returns structured headlines by category (general, technology, business, etc.).

### Todoist (`todoist.py`)
Todoist API for task management.

### GitHub (`github_integration.py`)
PyGitHub. List repos, view files and recent commits, push file content.

### Health (`health.py`)
SQLite-backed medication tracker. Auto-parses medication mentions from conversation ("I take X", "I just took X") and logs them.

### Contacts (`contacts.py`)
JSON-backed local contact list (`contacts.json`). Add, find, delete, list.

---

## Launcher and UI

### Web UI
`ui/scatter.html` is the single Scatter OS shell — a full browser dashboard served at `http://localhost:8082/` (via `index.html` redirect) or `http://localhost:8082/scatter.html`. It connects to the WebSocket server and renders panels for chat, calendar, email, music, weather, news, health, and contacts. Legacy `hazel-v5.html` / `hazel-v6.html` URLs redirect into this shell; the old terminal-only UI is kept as `scatter-v6-terminal.html` for reference.

### Desktop Launcher (`launcher.py`)
Tkinter GUI providing start/stop controls, live log tail, and a link to open the web UI. Designed for use on the Pi's desktop environment.

### Shell Scripts
- `start.sh` — starts the HTTP server (port 8082) and `main.py`, logs to `~/jarvis/logs/`
- `stop.sh` — kills both processes by PID
- `install.sh` — one-shot setup for a fresh Raspberry Pi 5

---

## Process Model

```
start.sh
  ├── python3 -m http.server 8082 --directory ~/jarvis/ui  (background)
  └── python3 main.py  (background)
         ├── Thread: hzl_ws.py (asyncio event loop, port 8765)
         └── Main loop: reminder checker (every 30s)
```

`main.py` owns the reminder check loop. All conversation handling runs through `hzl_ws.py`. The two communicate via `broadcast_sync()`, which uses `asyncio.run_coroutine_threadsafe()` to bridge the threaded and async worlds.
