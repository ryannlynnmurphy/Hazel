# Hazel

**Local-first voice AI assistant running on Raspberry Pi 5**

---

## Why I Built This

I learned to code in March 2026. Within weeks, I built a voice assistant that manages my calendar, reads my email, searches the web, and controls my smart home — all running locally on a Raspberry Pi 5. Hazel is proof that AI tools should serve creators, not replace them.

I'm a playwright by training — Fordham MFA, Edinburgh Fringe, Juilliard readings. I came to code not through a CS degree but through necessity and curiosity, building the tools I wanted to exist for artists and independent producers. Hazel is the system I actually live inside every day: she wakes up knowing my schedule, speaks in a voice I chose, and handles the logistics that used to fragment my attention. The fact that she runs entirely on a $90 computer in my living room is the point.

---

## Features

- **Voice interaction** — Speak naturally; Whisper transcribes on-device, no cloud STT required
- **Natural language responses** — Powered by Claude (Anthropic), with smart model routing: Haiku for quick queries, Sonnet for writing, code, and complex reasoning
- **Calendar management** — View, add, and query Google Calendar events by voice
- **Email** — Read, search, and send Gmail by voice with confirmation before sending
- **Web search** — Tavily-powered real-time search injected into conversation context
- **Smart home control** — Turn lights and devices on/off via Home Assistant
- **Spotify integration** — Play, pause, skip, and queue music by artist, song, or mood
- **Health tracking** — Medication reminders and daily logs stored privately in SQLite
- **Persistent memory** — Conversation history and user facts stored locally in SQLite
- **News briefings** — Live headlines delivered on demand
- **Weather** — Current conditions via Open-Meteo (no API key required)
- **Code execution** — Run and save Python snippets via voice command
- **GitHub integration** — List repos, view commits, push files by voice
- **Contacts** — Add, find, and manage a local contact list
- **Reminders** — Time-based reminders that fire as spoken alerts
- **Web UI** — Full-featured browser interface served locally at `localhost:8082`
- **Piper TTS fallback** — Fully local speech synthesis if ElevenLabs is unavailable
- **Desktop launcher** — Tkinter GUI for start/stop and live log monitoring

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| AI / LLM | Anthropic Claude (claude-sonnet-4-5, claude-haiku-4-5) |
| STT | OpenAI Whisper (local, via `openai-whisper`) |
| TTS (primary) | ElevenLabs API (`eleven_turbo_v2`) |
| TTS (fallback) | Piper (`en_US-lessac-medium`) |
| Web search | Tavily |
| Weather | Open-Meteo (free, no key) |
| Calendar | Google Calendar API (OAuth2) |
| Email | Gmail API (OAuth2) |
| Music | Spotify Web API via `spotipy` |
| Smart home | Home Assistant REST API |
| Task management | Todoist API |
| GitHub | PyGitHub |
| Database | SQLite (conversations, facts, reminders, health) |
| WebSocket server | `websockets` (asyncio, port 8765) |
| UI | HTML/CSS/JS served by `http.server` (port 8082) |
| Launcher | Tkinter |
| Audio | ALSA (`arecord`, `aplay`), ffmpeg |
| Hardware target | Raspberry Pi 5 (aarch64) |

---

## Quick Start

### Prerequisites

- Raspberry Pi 5 running Raspberry Pi OS (64-bit)
- Python 3.11+
- USB microphone (Blue Yeti recommended)
- Speaker connected via audio jack or USB

### Install

```bash
git clone https://github.com/ryannlynnmurphy/Hazel.git ~/jarvis
cd ~/jarvis
bash install.sh
```

The install script handles system packages (`ffmpeg`, `alsa-utils`, `sqlite3`), Python dependencies, Piper TTS, and a desktop launcher.

### Configure

```bash
cp .env.example .env
nano .env  # Fill in your API keys
```

Required keys: `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`

Optional (enable features): `TAVILY_API_KEY`, `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`, `GITHUB_TOKEN`, `TODOIST_API_TOKEN`, `NEWS_API_KEY`

Smart home: `HA_URL`, `HA_TOKEN` (Home Assistant)

Google services (Calendar + Gmail): place `credentials.json` in `~/jarvis/`, then run:
```bash
python3 gcal.py   # authorizes Calendar
python3 gmail.py  # authorizes Gmail
```

### Run

```bash
bash start.sh
```

Then open `http://localhost:8082/hazel-v5.html` in a browser, or use the desktop launcher:
```bash
python3 launcher.py
```

Stop Hazel:
```bash
bash stop.sh
```

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full breakdown of the STT pipeline, model routing, TTS stack, database schema, WebSocket protocol, and integration points.

---

## Part of the HZL Ecosystem

Hazel is the personal operating layer of a broader creative infrastructure being built at HZL AI LLC.

| Repo | Description |
|---|---|
| [hzl-core](https://github.com/ryannlynnmurphy/hzl-core) | Shared design system — tokens, components, brand identity |
| [hzl-studio-os](https://github.com/ryannlynnmurphy/hzl-studio-os) | Studio operating system for creative production |
| [Hazel](https://github.com/ryannlynnmurphy/Hazel) | This repo — personal AI assistant |

---

## License

MIT — see [LICENSE](LICENSE)

---

**Ryann Murphy** — Playwright-Technologist | Founder, HZL AI LLC | [ryannlynnmurphy.com](https://ryannlynnmurphy.com)
