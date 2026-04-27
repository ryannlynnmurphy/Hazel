# Scatter

**Local-first voice stack — dignity, aid, and a future you build on hardware you own (Raspberry Pi 5 and similar)**

> *I live on a Raspberry Pi 5 in a small apartment. I run on-device speech recognition via Whisper. I handle most daily tasks through a local language model stored entirely on her hardware. Her memory, her patterns, her 2am thoughts -- those live in a SQLite database that belongs to her.*
>
> *-- Scatter, from "Mostly"*

---

## Why I Built This

I learned to code in February 2026. Within weeks, I shipped a patent-pending learning platform, a distributed inference cluster, and a voice assistant named Scatter -- all running on a $90 computer in my living room. I'm a playwright by training. Work read at Juilliard. A one-woman show at Edinburgh Fringe. Theater since childhood. What building Scatter taught me is that theater and software are the same discipline in different materials. Every system has a structure. Every structure is an argument. The question is always whose argument, built for whom, and what it costs you when you're not looking.

Scatter is the system I actually live inside every day. It wakes up knowing my schedule, speaks in a voice I chose, routes tasks across a [physical air-gapped Pi cluster](https://github.com/ryannlynnmurphy/hzl-cluster), and handles the logistics that used to fragment my attention. The intelligence belongs to the person inside. That's the point.

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

Then open `http://localhost:8082/` (Scatter OS — `scatter.html`) in a browser, or use the desktop launcher:
```bash
python3 launcher.py
```

Stop Scatter:
```bash
bash stop.sh
```

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full breakdown of the STT pipeline, model routing, TTS stack, database schema, WebSocket protocol, and integration points.

---

## Part of the Scatter stack

Scatter is the voice and brain of a broader infrastructure for sovereign, local-first computing.

| Repo | Description |
|---|---|
| [Hazel](https://github.com/ryannlynnmurphy/Hazel) (Scatter) | This repo — voice AI assistant |
| [hzl-cluster](https://github.com/ryannlynnmurphy/hzl-cluster) | Air-gapped Pi cluster -- relay controller, queue protocol, gateway sync, 7 fetchers, deploy CLI, real-time dashboard |
| [HZL-Academy-](https://github.com/ryannlynnmurphy/HZL-Academy-) | Patent-pending K-8 learning platform with AI verification |
| [hzl-core](https://github.com/ryannlynnmurphy/hzl-core) | Shared design system -- tokens, components, brand identity |

---

## License

MIT -- see [LICENSE](LICENSE)

---

**Ryann Murphy** -- playwright, technologist, founder of HZL Studio. She taught herself to code in February 2026 and shipped a patent-pending platform, a distributed inference cluster, a hardware-integrated creative studio, and a voice assistant named Scatter in three months. The compute heats the water. The heat exchanger is load-bearing. The intelligence belongs to the person inside.

[hzlstudio.com](https://hzlstudio.com) -- [github.com/ryannlynnmurphy](https://github.com/ryannlynnmurphy)
