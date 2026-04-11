# Hazel v6 — Tiered Model Routing + Terminal UI Overhaul

**Date:** 2026-04-11
**Author:** Ryann Lynn Murphy + Claude
**Status:** Design approved, pending implementation

---

## Summary

Hazel v6 replaces the current single-model (Claude Haiku) architecture with a local-first tiered routing system that escalates through increasingly powerful models only when needed. The UI shifts from the cream/gold panel-based dashboard (v5) to a dark terminal-hacker chat-forward interface where rich data cards render inline in conversation.

---

## Motivation

- Every "hey hazel" currently burns Claude API credits
- Most interactions (greetings, weather checks, simple questions) don't need Claude at all
- The v5 UI is panel-heavy — too many things on screen at once
- Hazel should feel like you've hacked into something powerful, not like a luxury dashboard

---

## Architecture: Tiered Model Routing

### Escalation Chain

```
User message
    |
Tier 0: Pattern Match (instant, no model)
    |  "what time is it" -> direct answer
    |  "hey hazel" -> canned greeting
    |  greetings, date, simple commands
    | (no match)
    v
Tier 1: Phi-3 mini via Ollama (3.8B, local)
    |  Normal chat, light questions, acknowledgments
    |  Humanizing raw data into natural language
    | (quality gate fails)
    v
Tier 2: gpt-oss:20b via Ollama (20B, local)
    |  Harder reasoning, writing, deeper questions
    | (quality gate fails)
    v
Tier 3: Claude Haiku via API
    |  Action tags (Spotify, Gmail, Calendar)
    |  Integrations, multi-step tasks
    | (needs more)
    v
Tier 4: Claude Sonnet via API
    |  Deep analysis, complex writing
    |  Triggered by /deep command
    v
Tier 5: Claude Opus via API
    Last resort, maximum capability
    Triggered by /ultradeep command
```

### Quality Gate

After each local model response, a fast check determines whether to escalate:

- **Empty/too short**: Response < 10 characters
- **Garbled/repetitive**: Model degeneration detected (repeated phrases, broken tokens)
- **Refusal**: Model says "I don't know" / "I can't" when the query clearly has an answer
- **Missing action tags**: Query requires Spotify/Gmail/Calendar actions but model didn't produce valid tags
- **Timeout**: Model didn't respond within budget (Tier 1: 15s, Tier 2: 30s)

If any trigger fires, escalate to next tier. No retry at same tier.

### Auto-Escalation Rules

These messages skip local models entirely and go straight to Tier 3 (Claude Haiku):

- Messages containing URLs (Tavily web fetch needed)
- Explicit integration requests: "send email", "play [song]", "add to calendar"
- Messages requiring action tag generation (reliability matters)

### Deep Keywords (auto-bump to Tier 2 minimum)

```python
DEEP_KEYWORDS = [
    "explain", "why does", "why is", "why do",
    "how does", "how do", "how is",
    "teach me", "help me understand", "tell me about",
    "describe how", "compare", "difference between",
    "write a", "write me", "create a",
    "debug", "troubleshoot", "diagnose",
    "analyze", "evaluate",
]
```

### Manual Overrides

- `/deep` — jump to Tier 4 (Claude Sonnet)
- `/ultradeep` — jump to Tier 5 (Claude Opus)

### Infrastructure

- **Ollama** (already running on laptop): Serves phi3:mini and gpt-oss:20b via OpenAI-compatible REST API at `localhost:11434`
- **Claude API** (Anthropic SDK): For Tiers 3-5
- **Model availability check on startup**: If Ollama is down, log warning and default to Tier 3 for everything

### Status Bar

The UI shows which model tier handled each response:

```
HAZEL :: phi3 :: local          (Tier 1)
HAZEL :: gpt-oss :: local       (Tier 2)
HAZEL :: haiku :: api           (Tier 3)
HAZEL :: sonnet :: api          (Tier 4)
HAZEL :: opus :: api            (Tier 5)
```

---

## Architecture: New Brain (brain.py rewrite)

### Current State

- `brain.py` sends everything to Claude Haiku
- `build_system_prompt()` constructs a single system prompt
- `get_response()` calls Anthropic API, returns text
- Action tags parsed from response

### New State

`brain.py` becomes the router:

```python
# Simplified flow
def get_response(message, hint=None):
    # Tier 0: instant pattern match
    instant = check_instant(message)
    if instant:
        return instant, "instant"

    # Determine minimum tier
    min_tier = 2 if is_deep_query(message) else 1
    if needs_api(message):
        min_tier = 3

    # Escalation loop
    for tier in range(min_tier, 6):
        response = call_tier(tier, message, hint)
        if quality_check(response, message, tier):
            return response, tier_name(tier)

    # Should never reach here, but fallback
    return "Something went wrong.", "error"
```

### Ollama Integration

```python
def call_ollama(model, message, system_prompt, max_tokens, timeout):
    response = requests.post("http://localhost:11434/api/chat", json={
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "stream": False,
        "options": {"num_predict": max_tokens}
    }, timeout=timeout)
    return response.json()["message"]["content"]
```

### System Prompts Per Tier

- **Tier 1-2 (local)**: Shorter, focused system prompt. No action tag instructions (local models can't reliably produce them). Personality-light — just answer the question.
- **Tier 3-5 (Claude)**: Full Hazel personality prompt with action tag instructions, capability awareness, integration context.

---

## UI Design: Terminal Chat (hazel-v6.html)

### Aesthetic

- **Dark background**: `#0a0a0a` base
- **Green accents**: `#1aff1a` primary, `#1a5a1a` muted, `#33ff33` bright
- **Typography**: Sans-serif (system-ui) for chat text readability. Monospace (Courier New) for status bar, labels, face, input prompt, and data values.
- **No separate panels**: Everything lives in the chat stream

### Layout

Single column, full viewport:

```
┌──────────────────────────────────┐
│ HAZEL :: phi3 :: local    18:42  │  <- Status bar (monospace, muted green)
├──────────────────────────────────┤
│                                  │
│  ╔═══════════╗                   │
│  ║  •     •  ║                   │  <- ASCII face (heavy frame, dot eyes)
│  ║           ║                   │
│  ║   ╰───╯   ║                   │
│  ╚═══════════╝                   │
│  Evening. What do you need?      │
│                                  │
│  YOU                             │
│  what's the weather              │
│                                  │
│  HAZEL                           │
│  Here's what it looks like.      │
│  ┌─────────────────────────┐     │
│  │ 60°F    Partly cloudy   │     │  <- Inline rich card
│  │ FEELS 50° | HUM 26%     │     │
│  │ Now 58° · 1pm 61° · ... │     │
│  └─────────────────────────┘     │
│                                  │
│  > _                             │  <- Input with cursor + mic button
└──────────────────────────────────┘
```

### ASCII Face — States

Heavy double-line frame, rounded expressions, dot eyes:

```
IDLE                THINKING            SPEAKING
╔═══════════╗      ╔═══════════╗      ╔═══════════╗
║  •     •  ║      ║  ─     ─  ║      ║  •     •  ║
║           ║      ║           ║      ║           ║
║   ╰───╯   ║      ║   · · ·   ║      ║   ╰─▽─╯   ║
╚═══════════╝      ╚═══════════╝      ╚═══════════╝

HAPPY               ERROR               LISTENING
╔═══════════╗      ╔═══════════╗      ╔═══════════╗
║  ◡     ◡  ║      ║  ×     ×  ║      ║  •     •  ║
║           ║      ║           ║      ║           ║
║   ╰───╯   ║      ║   ═══     ║      ║   ╰─○─╯   ║
╚═══════════╝      ╚═══════════╝      ╚═══════════╝
```

The face appears at the top of the chat on load and after periods of inactivity. During active conversation it scrolls up naturally with the chat history.

### Inline Rich Cards

Cards appear inside the chat flow when Hazel responds with structured data. Styled with terminal DNA:

**Weather Card:**
```
┌─────────────────────────────────┐
│  60°F           Partly cloudy   │
│                                 │
│  FEELS 50°  HUM 26%  WIND 13   │
│                                 │
│  Now 58° · 1pm 61° · 2pm 63°   │
│  3pm 62° · 4pm 60° · 5pm 57°   │
└─────────────────────────────────┘
```

**Spotify Card:**
```
┌─────────────────────────────────┐
│  [album art]  Title             │
│               Artist            │
│               Album             │
│                                 │
│  [████████░░░░░░]  2:34 / 4:12  │
│  ⏮  ⏸  ⏭                      │
└─────────────────────────────────┘
```

- Green border (`#1a3a1a`), subtle glow (`box-shadow: 0 0 12px rgba(26,255,26,0.05)`)
- Data values in monospace, labels in muted green
- Album art for Spotify rendered as actual image with green border glow
- Progress bars: `[████████░░░░░░]` style

### Input

Terminal-style input at bottom of viewport (fixed):

```
> _                                    [mic]
```

- `>` prompt in green monospace
- Blinking cursor
- Mic button on the right, minimal — just an icon
- Dark background (`#050805`), green border

### No Navigation

No sidebar, no tab bar, no panel switcher. The only navigation is:
- Scroll up through chat history
- Type or speak to Hazel

---

## File Structure Changes

### New Files
- `ui/hazel-v6.html` — New terminal UI (single file, self-contained)
- `brain_router.py` — New routing logic, quality gate, tier management

### Modified Files
- `brain.py` — Refactored to work with router (system prompts per tier, Ollama calls)
- `hzl_ws.py` — Updated to pass tier info to UI, simplified (no panel push logic needed)
- `main.py` — Ollama health check on startup
- `weather.py` — Already updated, returns structured data for inline cards

### Unchanged
- `spotify.py`, `gmail.py`, `gcal.py`, `voice.py`, `memory.py` — Integration modules stay the same
- `hzl_security/` — Security layer stays the same
- `.env` — Same env vars, add `OLLAMA_URL=http://localhost:11434` default

---

## WebSocket Protocol Changes

### Current
```json
{"type": "response", "text": "..."}
{"type": "weather_state", "temp": 60, ...}
{"type": "panel_open", "panel": "weather"}
```

### New
```json
{"type": "response", "text": "...", "tier": "phi3", "tier_type": "local"}
{"type": "card", "card_type": "weather", "data": {"temp": 60, "feels": 50, ...}}
{"type": "card", "card_type": "spotify", "data": {"track": "...", "artist": "...", ...}}
{"type": "face", "state": "thinking"}
{"type": "face", "state": "idle"}
```

Cards are embedded in the chat flow by the UI, not pushed as separate panel updates. The `tier` field lets the status bar show which model answered.

---

## Migration Path

1. Build `hazel-v6.html` alongside existing `hazel-v5.html` — both work simultaneously
2. Build `brain_router.py` as a new module — existing `brain.py` stays functional
3. Wire new router into `hzl_ws.py` behind a config flag
4. Test locally, switch over when stable
5. Remove v5 UI and old brain path once v6 is validated

---

## Out of Scope (for now)

- Local voice/STT overhaul (future session)
- Smart home via WiFi (future session)
- Google OAuth re-authentication (waiting on credentials)
- RAG pipeline with Claude (future iteration after routing is stable)
- Mobile/responsive layout (desktop-first)
