# Ship into the future

You built most of this with **Claude Code** and **Cursor Composers** — a voice OS on the Pi, a confabulatory classroom on static HTML, and a WebSocket that finally listens on the **LAN** so a Pixel is not loopback‑trapped. This file is the ritual for **after every reboot** when you want that stack back without thinking.

## One command (do this first)

```bash
ship-future
```

(if `~/bin` is on your `PATH`, a symlink was created there; otherwise:)

```bash
bash ~/projects/hazel/Hazel/scripts/ship-future.sh
```

From the repo: `make future`

What it does:

- Runs **`cursor-agent update`** so the CLI agent matches what Cursor ships (same toolchain you used to build this).
- Tells you how to **upgrade the Cursor app** on Ubuntu if you use the `cursor` apt package.
- Shows **`git status`** for this repo and prints the **LAN URL** for classroom phones.

Then **restart the Cursor app** if it was upgraded — the editor and the agent CLI are two binaries; you want both fresh.

## Bring the stack up

```bash
cd ~/projects/hazel/Hazel
bash start.sh
```

- UI (this machine): [http://localhost:8082/hazel-v5.html](http://localhost:8082/hazel-v5.html)
- UI (phone, same Wi‑Fi): `http://<output-of-hostname -I>:8082/...` — **never** `http://localhost` on the phone.
- `scatter-base.js` keeps WebSocket and “open in new tab” on **whatever host served the page**.

## What shipped in this generation

| Piece | Why it matters |
|--------|-----------------|
| `ui/scatter-base.js` | Same-origin WS + links — **Pixel problem solved** |
| `ui/classroom.html` | Single-player “Kahoot” grounded in *CONFABULATORY_PHILOSOPHY* + real praxis |
| `ui/HZL_Academy.html` | OS integration guide, not a generic OER catalog |
| `hzl_ws.py` + `start.sh` | `HZL_WS_HOST=0.0.0.0` default — classroom can connect |
| `hazel-v5.html` / `v6` | Apps + `SCATTER.wsUrl()` |

## Point Cursor at the truth in the other repo

The architecture bridge (paper → code) lives in **scatter-system**:

`scatter-system/docs/CONFABULATORY_PHILOSOPHY.md`

## GitHub when you are ready

This folder may have **no `origin`** until you add it:

```bash
git remote add origin git@github.com:ryannlynnmurphy/Hazel.git   # or your path
git push -u origin main
```

## Built with

Claude, Cursor, stubborn love for local topology, and the argument that **governance is an effect of topology** — you already wrote that; the classroom node just teaches kids to *feel* it in the same room as the box.

— *a session that didn’t just edit files — it lined up the future you with the room you own.*
