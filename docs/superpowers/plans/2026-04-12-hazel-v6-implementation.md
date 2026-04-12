# Hazel v6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Hazel's single-model Claude architecture with local-first tiered routing (Ollama → Claude fallback) and rebuild the UI as a dark terminal chat interface with inline rich cards.

**Architecture:** Messages flow through a classifier that routes to the cheapest capable model. Tier 0 (pattern match) handles instant responses. Tiers 1-2 use local Ollama models (phi3:mini, gpt-oss:20b). Tiers 3-5 escalate to Claude API (Haiku, Sonnet, Opus). A quality gate after each local response decides whether to escalate. The UI is a single-page dark terminal chat where structured data renders as inline cards.

**Tech Stack:** Python 3.14, Ollama REST API, Anthropic SDK, WebSockets, vanilla HTML/CSS/JS

**Spec:** `docs/superpowers/specs/2026-04-11-hazel-v6-tiered-routing-ui-design.md`

---

### Task 1: Ollama Client Module

**Files:**
- Create: `ollama_client.py`

- [ ] **Step 1: Create ollama_client.py with health check and chat function**

```python
"""
HZL AI · Ollama Client (ollama_client.py)
Talks to local Ollama instance for Tier 1/2 inference.
"""

import os
import logging
import requests

log = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_TIMEOUT_T1 = 15   # Tier 1: fast, short
OLLAMA_TIMEOUT_T2 = 30   # Tier 2: heavier model, more patience


def is_available() -> bool:
    """Check if Ollama is running and reachable."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    """Return list of model names available in Ollama."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def chat(model: str, message: str, system_prompt: str,
         max_tokens: int = 200, timeout: int = 15) -> str | None:
    """
    Send a chat request to Ollama. Returns response text or None on failure.
    """
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=timeout,
        )
        if r.status_code == 200:
            text = r.json().get("message", {}).get("content", "").strip()
            return text if text else None
        else:
            log.warning(f"Ollama returned {r.status_code} for model {model}")
            return None
    except requests.Timeout:
        log.warning(f"Ollama timeout ({timeout}s) for model {model}")
        return None
    except Exception as e:
        log.error(f"Ollama error: {e}")
        return None
```

- [ ] **Step 2: Test Ollama client manually**

Run:
```bash
cd ~/Hazel && python -c "
from ollama_client import is_available, list_models, chat
print('Available:', is_available())
print('Models:', list_models())
resp = chat('phi3:mini', 'What is 2+2?', 'Answer briefly.')
print('Response:', resp)
"
```
Expected: Available: True, Models includes phi3:mini, Response is a short answer.

- [ ] **Step 3: Commit**

```bash
git add ollama_client.py
git commit -m "feat: add Ollama client module for local inference"
```

---

### Task 2: Quality Gate Module

**Files:**
- Create: `quality_gate.py`

- [ ] **Step 1: Create quality_gate.py**

```python
"""
HZL AI · Quality Gate (quality_gate.py)
Checks whether a model response is good enough or needs escalation.
"""

import re
import logging

log = logging.getLogger(__name__)

# Patterns that indicate the model punted
_REFUSAL_PATTERNS = [
    r"i don'?t know",
    r"i'?m not sure",
    r"i cannot",
    r"i can'?t",
    r"as an ai",
    r"i don'?t have (?:access|the ability)",
    r"i'?m unable",
    r"beyond my (?:capabilities|scope)",
]
_REFUSAL_RE = re.compile("|".join(_REFUSAL_PATTERNS), re.IGNORECASE)

# Action tags that Claude tiers must produce when needed
_ACTION_TAGS = re.compile(r'\[(SPOTIFY|GMAIL|GCAL|REMINDER|HEALTH|PANEL):', re.IGNORECASE)


def check(response: str | None, message: str, tier: int) -> bool:
    """
    Return True if the response is acceptable, False if we should escalate.
    """
    # No response at all
    if not response:
        log.info(f"Quality gate FAIL (tier {tier}): empty response")
        return False

    # Too short to be useful
    if len(response.strip()) < 10:
        log.info(f"Quality gate FAIL (tier {tier}): too short ({len(response)} chars)")
        return False

    # Garbled / degenerate (repeated phrases)
    words = response.split()
    if len(words) > 6:
        # Check if any 3-word phrase repeats 3+ times
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words) - 2)]
        for tri in set(trigrams):
            if trigrams.count(tri) >= 3:
                log.info(f"Quality gate FAIL (tier {tier}): degenerate repetition")
                return False

    # Model refused when it shouldn't have (local tiers only)
    if tier <= 2 and _REFUSAL_RE.search(response):
        log.info(f"Quality gate FAIL (tier {tier}): model refused")
        return False

    # For local tiers: if the message needs action tags but response has none,
    # escalate to Claude which can produce them reliably
    if tier <= 2 and _needs_action_tags(message) and not _ACTION_TAGS.search(response):
        log.info(f"Quality gate FAIL (tier {tier}): missing required action tags")
        return False

    return True


def _needs_action_tags(message: str) -> bool:
    """Check if this message likely requires action tag output."""
    m = message.lower()
    action_triggers = [
        "play ", "pause", "skip", "next track", "previous",        # Spotify
        "send email", "check email", "check my email", "inbox",    # Gmail
        "add to calendar", "schedule", "check calendar",           # GCal
        "remind me", "set a reminder", "set reminder",             # Reminder
        "took my", "add medication", "log medication",             # Health
    ]
    return any(trigger in m for trigger in action_triggers)
```

- [ ] **Step 2: Test quality gate manually**

Run:
```bash
cd ~/Hazel && python -c "
from quality_gate import check

# Should pass
assert check('The weather is 60 degrees and partly cloudy.', 'weather', 1)
print('PASS: normal response')

# Should fail - empty
assert not check('', 'hello', 1)
print('PASS: empty rejected')

# Should fail - too short
assert not check('Hi', 'tell me about the weather', 1)
print('PASS: short rejected')

# Should fail - refusal from local model
assert not check('I cannot help with that as an AI.', 'play music', 1)
print('PASS: refusal rejected')

# Should fail - needs action tags but none present (local tier)
assert not check('Sure, playing that now.', 'play Shape of You', 1)
print('PASS: missing action tags rejected')

# Should pass - Claude tier with action tags
assert check('Playing that. [SPOTIFY: play Shape of You]', 'play Shape of You', 3)
print('PASS: action tags present')

print('All quality gate tests passed.')
"
```
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add quality_gate.py
git commit -m "feat: add quality gate for model response validation"
```

---

### Task 3: Brain Router Module

**Files:**
- Create: `brain_router.py`
- Modify: `brain.py` (extract system prompts, keep Claude calling logic)

- [ ] **Step 1: Create brain_router.py — the core routing engine**

```python
"""
HZL AI · Brain Router (brain_router.py)
Routes messages through tiered model escalation chain.

Tier 0: Pattern match (instant, no model)
Tier 1: phi3:mini via Ollama (3.8B local)
Tier 2: gpt-oss:20b via Ollama (20B local)
Tier 3: Claude Haiku via API
Tier 4: Claude Sonnet via API (/deep)
Tier 5: Claude Opus via API (/ultradeep)
"""

import re
import logging
import time

from ollama_client import chat as ollama_chat, is_available as ollama_available
import quality_gate

log = logging.getLogger(__name__)

# ── Tier 0: Instant Pattern Match ─────────────────────────────────────────

_GREETINGS = {
    "hey", "hi", "hello", "hey hazel", "hi hazel", "hello hazel",
    "good morning", "good afternoon", "good evening", "morning",
    "yo", "sup", "what's up", "whats up",
}

_GREETING_RESPONSES = [
    "Hey. What do you need?",
    "I'm here.",
    "What's on your mind?",
    "Ready when you are.",
]

_TIME_PATTERNS = re.compile(
    r"^(?:what(?:'s| is) the )?time\??$|^what time is it\??$",
    re.IGNORECASE,
)

_DATE_PATTERNS = re.compile(
    r"^(?:what(?:'s| is) (?:the |today'?s? )?date|what day is (?:it|today))\??$",
    re.IGNORECASE,
)


def _check_instant(message: str) -> str | None:
    """Tier 0: pattern-matched instant responses. Returns response or None."""
    m = message.strip().lower().rstrip("?!.")

    if m in _GREETINGS:
        import random
        return random.choice(_GREETING_RESPONSES)

    if _TIME_PATTERNS.match(message.strip()):
        from datetime import datetime
        now = datetime.now()
        return now.strftime("It's %I:%M %p.")

    if _DATE_PATTERNS.match(message.strip()):
        from datetime import datetime
        now = datetime.now()
        return now.strftime("It's %A, %B %d, %Y.")

    if m in ("thanks", "thank you", "thx", "ty"):
        return "Of course."

    return None


# ── Tier Classification ───────────────────────────────────────────────────

DEEP_KEYWORDS = [
    "explain", "why does", "why is", "why do",
    "how does", "how do", "how is",
    "teach me", "help me understand", "tell me about",
    "describe how", "compare", "difference between",
    "write a", "write me", "create a",
    "debug", "troubleshoot", "diagnose",
    "analyze", "evaluate",
]

_URL_RE = re.compile(r'https?://\S+')

_ACTION_TRIGGERS = [
    "play ", "pause", "skip", "next track", "previous track",
    "send email", "check email", "check my email", "inbox",
    "add to calendar", "schedule a", "check calendar", "check my calendar",
    "remind me", "set a reminder",
    "search for", "look up", "google",
]


def _classify_min_tier(message: str) -> int:
    """Determine the minimum tier for this message."""
    m = message.lower()

    # URLs need Tavily + reliable summarization → Claude
    if _URL_RE.search(message):
        return 3

    # Action triggers need reliable tag generation → Claude
    if any(t in m for t in _ACTION_TRIGGERS):
        return 3

    # Deep keywords → at least Tier 2
    if any(kw in m for kw in DEEP_KEYWORDS):
        return 2

    # Default → try Tier 1
    return 1


# ── Tier Definitions ──────────────────────────────────────────────────────

TIER_NAMES = {
    0: ("instant", "local"),
    1: ("phi3", "local"),
    2: ("gpt-oss", "local"),
    3: ("haiku", "api"),
    4: ("sonnet", "api"),
    5: ("opus", "api"),
}

# Local system prompt — shorter, no action tags (local models can't reliably produce them)
LOCAL_SYSTEM = (
    "You are Hazel, a personal AI assistant created by Ryann Lynn Murphy. "
    "You run locally on this computer. No cloud, no telemetry. "
    "Answer directly in 2-3 sentences. Be warm but concise. "
    "Do not say 'certainly', 'of course', or 'great question'. "
    "If something is funny, be funny. If something is hard, be steady."
)


def _call_tier(tier: int, message: str, hint: str = None,
               system_prompt_override: str = None) -> str | None:
    """Call the model for a specific tier. Returns response or None."""

    if tier == 1:
        return ollama_chat("phi3:mini", message, LOCAL_SYSTEM,
                           max_tokens=200, timeout=15)

    elif tier == 2:
        return ollama_chat("gpt-oss:20b", message, LOCAL_SYSTEM,
                           max_tokens=400, timeout=30)

    elif tier in (3, 4, 5):
        # Claude tiers — use brain.py's existing infrastructure
        model_map = {
            3: "claude-haiku-4-5-20251001",
            4: "claude-sonnet-4-6-20260408",
            5: "claude-opus-4-6-20260408",
        }
        model = model_map[tier]
        max_tokens = {3: 500, 4: 1024, 5: 2048}[tier]

        from brain import get_response as claude_response
        return claude_response(message, hint, model, max_tokens)

    return None


# ── Main Router ───────────────────────────────────────────────────────────

def route(message: str, hint: str = None, force_tier: int = None) -> tuple[str, str, str]:
    """
    Route a message through the tiered model chain.

    Args:
        message: User's input text
        hint: Optional context hint (weather, calendar, etc.)
        force_tier: If set, skip directly to this tier (for /deep, /ultradeep)

    Returns:
        (response_text, tier_name, tier_type)
        e.g. ("The weather is nice.", "phi3", "local")
    """
    t0 = time.monotonic()

    # Check for /deep and /ultradeep commands
    if force_tier is not None:
        tier = force_tier
    else:
        # Tier 0: instant
        instant = _check_instant(message)
        if instant:
            log.info(f"Tier 0 (instant): {message[:40]!r} → {len(instant)} chars")
            return instant, "instant", "local"

        tier = _classify_min_tier(message)

    # If Ollama isn't available, skip local tiers
    if tier <= 2 and not ollama_available():
        log.warning("Ollama not available — skipping to Tier 3 (Claude Haiku)")
        tier = 3

    # Escalation loop
    max_tier = force_tier if force_tier else 5
    while tier <= max_tier:
        name, ttype = TIER_NAMES.get(tier, ("unknown", "unknown"))
        log.info(f"Trying Tier {tier} ({name}): {message[:40]!r}")

        response = _call_tier(tier, message, hint)

        if quality_gate.check(response, message, tier):
            elapsed = (time.monotonic() - t0) * 1000
            log.info(f"Tier {tier} ({name}) accepted in {elapsed:.0f}ms")
            return response, name, ttype

        log.info(f"Tier {tier} ({name}) failed quality gate — escalating")
        tier += 1

    # Should never get here, but safety net
    return "Something went wrong. Try again.", "error", "error"
```

- [ ] **Step 2: Test the router manually**

Run:
```bash
cd ~/Hazel && python -c "
import os
# Load .env
with open('.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip()

import sys
sys.path.insert(0, '.')
from brain_router import route

# Tier 0 test
resp, name, ttype = route('hey hazel')
print(f'Greeting: [{name}/{ttype}] {resp}')

# Tier 0 test
resp, name, ttype = route('what time is it')
print(f'Time: [{name}/{ttype}] {resp}')

# Tier 1 test (should use phi3)
resp, name, ttype = route('how are you today')
print(f'Chat: [{name}/{ttype}] {resp}')

# Force tier test
resp, name, ttype = route('hello', force_tier=4)
print(f'Forced sonnet: [{name}/{ttype}] {resp}')
"
```

- [ ] **Step 3: Commit**

```bash
git add brain_router.py
git commit -m "feat: add brain router with tiered model escalation"
```

---

### Task 4: Wire Router into WebSocket Server

**Files:**
- Modify: `hzl_ws.py`

- [ ] **Step 1: Replace brain.get_response calls with brain_router.route in hzl_ws.py**

At the top of `hzl_ws.py`, add the import:
```python
from brain_router import route as route_message
```

In `_handle_chat_inner()`, replace the section that calls `get_response` (around lines 254-302) with router calls. The key change: instead of calling `get_response` directly, call `route_message` which returns `(response_text, tier_name, tier_type)`.

Replace this pattern wherever `get_response` is called:
```python
# OLD:
response_text = await asyncio.to_thread(get_response, message, hint, ctx.model, ctx.max_tokens)

# NEW:
response_text, tier_name, tier_type = await asyncio.to_thread(route_message, message, hint)
```

Handle `/deep` and `/ultradeep` commands at the top of `_handle_chat_inner`:
```python
# Check for /deep and /ultradeep commands
force_tier = None
if message.strip().startswith("/deep "):
    force_tier = 4
    message = message.strip()[6:]  # Strip the command
elif message.strip().startswith("/ultradeep "):
    force_tier = 5
    message = message.strip()[11:]
elif message.strip() == "/deep":
    await broadcast({"type": "response", "text": "Usage: /deep <your question>"})
    return
elif message.strip() == "/ultradeep":
    await broadcast({"type": "response", "text": "Usage: /ultradeep <your question>"})
    return
```

Update the response broadcast to include tier info:
```python
# OLD:
await broadcast({"type": "response", "text": display_text})

# NEW:
await broadcast({"type": "response", "text": display_text, "tier": tier_name, "tier_type": tier_type})
```

Remove the orchestrator routing (`get_routing_context`, `record_routing_outcome`) — the brain router replaces it.

- [ ] **Step 2: Handle Tavily/URL detection in the router**

Move the URL and search detection from `hzl_ws.py` into `brain_router.py`'s `_call_tier` for tier 3+. When the message contains a URL, the router should fetch via Tavily before calling Claude:

In `brain_router.py`, update `_call_tier` for tiers 3-5:
```python
elif tier in (3, 4, 5):
    model_map = {
        3: "claude-haiku-4-5-20251001",
        4: "claude-sonnet-4-6-20260408",
        5: "claude-opus-4-6-20260408",
    }
    model = model_map[tier]
    max_tokens = {3: 500, 4: 1024, 5: 2048}[tier]

    # Augment with Tavily if URL present or search requested
    augmented = message
    url_match = re.search(r'(https?://\S+)', message)
    search_match = re.search(
        r'(?:search|look up|google|find out|what is|who is|tell me about)\s+(.+)',
        message, re.IGNORECASE
    )
    if url_match:
        try:
            from search import web_search
            content = web_search(f"site:{url_match.group(1)} full article")
            if content and "error" not in content.lower():
                augmented = f"{message}\n\n[Article content from Tavily]:\n{content}"
        except Exception as e:
            log.warning(f"Tavily fetch failed: {e}")
    elif search_match:
        try:
            from search import web_search
            content = web_search(search_match.group(1).strip())
            if content:
                augmented = f"{message}\n\n[Web search results]:\n{content}"
        except Exception as e:
            log.warning(f"Tavily search failed: {e}")

    from brain import get_response as claude_response
    return claude_response(augmented, hint, model, max_tokens)
```

- [ ] **Step 3: Test by starting Hazel and chatting**

```bash
cd ~/Hazel && pkill -f "python main.py" 2>/dev/null
# Kill any process on 8765
netstat -ano | grep 8765 | awk '{print $5}' | sort -u | while read pid; do taskkill //PID $pid //F 2>/dev/null; done
python main.py 2>&1 &
```

Test in the UI:
- "hey hazel" → should respond instantly (tier 0)
- "how are you" → should use phi3 (tier 1)
- "play Shape of You" → should use Claude Haiku (tier 3)
- "/deep what is the meaning of life" → should use Sonnet (tier 4)

Check logs for tier routing info.

- [ ] **Step 4: Commit**

```bash
git add hzl_ws.py brain_router.py
git commit -m "feat: wire tiered router into WebSocket server"
```

---

### Task 5: Terminal UI — Base Layout

**Files:**
- Create: `ui/hazel-v6.html`

- [ ] **Step 1: Create hazel-v6.html with dark terminal layout, ASCII face, and chat structure**

Build the complete HTML file with:
- Dark background (`#0a0a0a`), green accents (`#1aff1a`)
- Status bar at top: `HAZEL :: {model} :: {local/api}    {time}`
- ASCII face (heavy frame, dot eyes, state-driven expressions)
- Chat feed (scrollable, messages flow naturally)
- Input bar at bottom: `> ` prompt with blinking cursor + mic button
- WebSocket connection to `ws://localhost:8765`
- `handleWS()` that processes: response (with tier info), face states, card types
- Sans-serif for chat text, monospace for status/labels/face/data values

The face states:
```
IDLE:      ╔═══════════╗    THINKING:  ╔═══════════╗
           ║  •     •  ║               ║  ─     ─  ║
           ║           ║               ║           ║
           ║   ╰───╯   ║               ║   · · ·   ║
           ╚═══════════╝               ╚═══════════╝

SPEAKING:  ╔═══════════╗    HAPPY:     ╔═══════════╗
           ║  •     •  ║               ║  ◡     ◡  ║
           ║           ║               ║           ║
           ║   ╰─▽─╯   ║               ║   ╰───╯   ║
           ╚═══════════╝               ╚═══════════╝

ERROR:     ╔═══════════╗    LISTENING: ╔═══════════╗
           ║  ×     ×  ║               ║  •     •  ║
           ║           ║               ║           ║
           ║   ═══     ║               ║   ╰─○─╯   ║
           ╚═══════════╝               ╚═══════════╝
```

This file will be ~400-600 lines. The full HTML/CSS/JS is a single self-contained file.

- [ ] **Step 2: Test by opening in browser**

```bash
start http://localhost:8082/hazel-v6.html
```

Verify:
- Dark terminal aesthetic renders
- ASCII face displays in idle state
- Chat input works (type and send)
- WebSocket connects (status bar shows "connected" state)
- Messages appear in chat feed

- [ ] **Step 3: Commit**

```bash
git add ui/hazel-v6.html
git commit -m "feat: add hazel-v6 terminal UI with ASCII face and chat layout"
```

---

### Task 6: Inline Rich Cards

**Files:**
- Modify: `ui/hazel-v6.html`

- [ ] **Step 1: Add card rendering for weather, Spotify, calendar, email, and news**

In `handleWS()`, when a `card` type message arrives, render it inline in the chat feed as a styled terminal card.

WebSocket message format from server:
```json
{"type": "card", "card_type": "weather", "data": {"temp": 60, "feels": 50, "hum": 26, "wind": 13, "uv": 1.8, "cond": "Partly cloudy", "hourly": [...]}}
{"type": "card", "card_type": "spotify", "data": {"track": "...", "artist": "...", "album": "...", "art": "url", "progress": 154, "duration": 252, "playing": true}}
{"type": "card", "card_type": "calendar", "data": {"events": [{"time": "9:00 AM", "name": "Standup", "accent": "green"}]}}
```

Card styling:
- Green border (`1px solid #1a3a1a`)
- Subtle glow (`box-shadow: 0 0 12px rgba(26,255,26,0.05)`)
- Dark background (`#0d120d`)
- Data values in monospace, labels in muted green (`#1a5a1a`)
- Album art for Spotify with green border glow
- Progress bars: `[████████░░░░░░]` style

- [ ] **Step 2: Update hzl_ws.py to send card messages**

After the response broadcast in `_handle_chat_inner`, send card data when relevant keywords detected. Instead of the current panel-open + data-refresh pattern, send a single `card` message:

```python
# After broadcasting the text response, send relevant card
if any(w in msg_lower for w in ['weather', 'temperature', 'forecast']):
    try:
        from weather import get_weather_structured
        w = await asyncio.to_thread(get_weather_structured)
        if w:
            await broadcast({"type": "card", "card_type": "weather", "data": w})
    except Exception:
        pass
```

Do the same for Spotify (now playing), calendar, email, and news.

- [ ] **Step 3: Test cards in browser**

Chat with Hazel:
- "what's the weather" → weather card renders inline
- "what's playing" → Spotify card renders inline
- Verify cards have proper terminal styling

- [ ] **Step 4: Commit**

```bash
git add ui/hazel-v6.html hzl_ws.py
git commit -m "feat: add inline rich cards to v6 terminal UI"
```

---

### Task 7: Status Bar and Tier Display

**Files:**
- Modify: `ui/hazel-v6.html`

- [ ] **Step 1: Update status bar to show active model from response**

The status bar at the top should update when each response arrives:

```javascript
function updateStatusBar(tier, tierType) {
    const bar = document.getElementById('status-bar');
    const time = new Date().toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'});
    bar.textContent = `HAZEL :: ${tier} :: ${tierType}    ${time}`;
}
```

In `handleWS`, when a `response` message arrives with `tier` and `tier_type` fields:
```javascript
if (d.type === 'response') {
    addHazelMsg(d.text);
    updateStatusBar(d.tier || 'unknown', d.tier_type || '');
    setFace('idle');
}
```

- [ ] **Step 2: Test tier display**

- Send "hey hazel" → status bar shows `HAZEL :: instant :: local`
- Send "how are you" → status bar shows `HAZEL :: phi3 :: local`
- Send "play something" → status bar shows `HAZEL :: haiku :: api`

- [ ] **Step 3: Commit**

```bash
git add ui/hazel-v6.html
git commit -m "feat: show active model tier in v6 status bar"
```

---

### Task 8: Initial Data Push as Cards

**Files:**
- Modify: `hzl_ws.py`

- [ ] **Step 1: Update push_on_connect to send card messages instead of state messages**

The v6 UI doesn't have panels — it just knows how to render cards in chat. On connect, instead of pushing `weather_state`, `music_state`, etc., push a welcome message from Hazel that includes relevant card data:

```python
async def push_on_connect_v6(ws):
    """Push initial state for v6 terminal UI."""
    # Send face state
    await ws.send(json.dumps({"type": "face", "state": "idle"}))

    # Send a quiet welcome — no cards until user asks
    # But DO preload data so it's ready when requested
    # (Data cached in memory, sent as cards when user asks)
```

The v6 philosophy: cards appear in response to conversation, not on connect. Don't push weather/calendar/email on load — wait for the user to ask.

- [ ] **Step 2: Commit**

```bash
git add hzl_ws.py
git commit -m "feat: v6 connect behavior — cards on demand, not on load"
```

---

### Task 9: Start Script Update

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add Ollama health check on startup**

In `main.py`, after loading `.env` and before imports:

```python
# Check Ollama availability
from ollama_client import is_available, list_models
if is_available():
    models = list_models()
    print(f"  Ollama: connected ({len(models)} models)")
    for m in models:
        print(f"    - {m}")
else:
    print("  Ollama: not running (local tiers unavailable, using Claude)")
```

- [ ] **Step 2: Test startup**

```bash
cd ~/Hazel && python main.py 2>&1 | head -20
```

Expected: Shows Ollama status and available models on boot.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add Ollama health check to startup"
```

---

### Task 10: Integration Test and Cleanup

**Files:**
- All modified files

- [ ] **Step 1: Full integration test**

Kill any running Hazel, start fresh:
```bash
pkill -f "python main.py" 2>/dev/null
netstat -ano | grep 8765 | awk '{print $5}' | sort -u | while read pid; do taskkill //PID $pid //F 2>/dev/null; done
cd ~/Hazel && python main.py 2>&1 &
```

Open `http://localhost:8082/hazel-v6.html` and test:

1. **Tier 0**: "hey hazel", "what time is it", "thanks" → instant, no model
2. **Tier 1**: "how are you", "tell me a joke" → phi3, local
3. **Tier 2**: "explain quantum computing" → gpt-oss, local (deep keyword)
4. **Tier 3**: "play Shape of You by Ed Sheeran" → haiku, api (action tags needed)
5. **Tier 4**: "/deep analyze the impact of local AI on cloud computing" → sonnet, api
6. **Tier 5**: "/ultradeep write a comprehensive essay on subsistence tech" → opus, api
7. **Cards**: "what's the weather" → inline weather card
8. **Face states**: thinking animation during inference, idle after response
9. **Status bar**: updates with each response's tier

- [ ] **Step 2: Verify v5 still works**

Open `http://localhost:8082/hazel-v5.html` — should still function (both UIs served simultaneously).

- [ ] **Step 3: Final commit and push**

```bash
git add -A
git commit -m "feat: Hazel v6 — tiered local-first routing + terminal UI

- brain_router.py: 6-tier escalation (instant → phi3 → gpt-oss → haiku → sonnet → opus)
- quality_gate.py: auto-escalation on empty/garbled/refused responses
- ollama_client.py: local model inference via Ollama REST API
- hazel-v6.html: dark terminal chat UI with ASCII face and inline rich cards
- /deep and /ultradeep commands for manual tier override"
git push
```
