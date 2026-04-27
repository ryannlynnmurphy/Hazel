#!/usr/bin/env python3
"""
Scatter · Brain  (brain.py)
Patched for Scatter OS (ui/scatter.html):
  - Model strings verified and pinned
  - Hint-aware system prompt injection
  - Action tag parser covers all v5 actions
"""

import os
import re
import logging
from datetime import datetime

import anthropic

# Security
from hzl_security.llm import detect_injection

# Local modules
try:
    from memory import get_recent, get_all_facts, save_message
except ImportError:
    logging.warning("memory.py not found")
    def get_recent(n): return []
    def get_all_facts(): return {}
    def save_message(role, content): pass

try:
    from weather import get_weather
except ImportError:
    def get_weather(): return "Weather unavailable."

try:
    from gmail import get_unread_emails, search_emails, send_email, get_email_body
except ImportError:
    def get_unread_emails(): return []
    def search_emails(q): return []
    def send_email(to, subj, body): return False

try:
    from gcal import get_upcoming_events, add_event
except ImportError:
    def get_upcoming_events(n=5): return []
    def add_event(title, date, time): return False

try:
    from smarthome import execute_action, status_summary
except ImportError:
    def execute_action(a, e): return False
    def status_summary(): return "Home Assistant unavailable."

log = logging.getLogger(__name__)

# ── MODEL ROUTING ──────────────────────────────────────────────────────────
# Pinned model strings — update here if Anthropic deprecates one
MODEL_COMPLEX = "claude-sonnet-4-5"          # complex reasoning, writing, code
MODEL_FAST    = "claude-haiku-4-5-20251001"  # fast factual queries

COMPLEX_KEYWORDS = re.compile(
    r'\b(explain|analyze|debug|code|write|compare|build|create|script|'
    r'program|essay|poem|summarize|draft|plan|design|help me|how do|'
    r'what is|tell me about|research|strategy|recommend)\b',
    re.IGNORECASE
)

def choose_model(message: str) -> str:
    if COMPLEX_KEYWORDS.search(message):
        return MODEL_COMPLEX
    return MODEL_FAST

# ── ACTION TAG PARSER ──────────────────────────────────────────────────────
ACTION_RE = re.compile(r'\[([A-Z_]+):\s*([^\]]*)\]')

# Stores the most-recently parsed action list so hzl_ws.py can consume it
_last_actions: list = []


def get_last_actions() -> list:
    """Return (and clear) the actions parsed from the most recent get_response() call."""
    global _last_actions
    actions, _last_actions = _last_actions, []
    return actions


def parse_actions(text: str) -> list[dict]:
    """Extract and execute action tags from Claude's response."""
    actions = []
    for match in ACTION_RE.finditer(text):
        tag, args = match.group(1), match.group(2).strip()

        if tag == "ACTION":
            # e.g. [ACTION: turn_on light.living_room]
            parts = args.split(maxsplit=1)
            if len(parts) == 2:
                action_name, entity = parts
                execute_action(action_name, entity)
                actions.append({"tag": "ACTION", "action": action_name, "entity": entity})

        elif tag == "REMINDER":
            # e.g. [REMINDER: 15:00 Take your Metformin]
            parts = args.split(maxsplit=1)
            if len(parts) == 2:
                from memory import save_reminder
                save_reminder(parts[0], parts[1])
                actions.append({"tag": "REMINDER", "time": parts[0], "msg": parts[1]})

        elif tag == "GMAIL":
            sub = args.split(maxsplit=1)
            cmd = sub[0].lower()
            if cmd == "check":
                get_unread_emails()
            elif cmd == "read" and len(sub) > 1:
                result = get_email_body(sub[1])
                actions.append({"tag": "GMAIL", "cmd": "read", "result": result})
                continue
            elif cmd == "search" and len(sub) > 1:
                search_emails(sub[1])
            elif cmd == "send" and len(sub) > 1:
                parts = sub[1].split("|")
                if len(parts) == 3:
                    send_email(parts[0].strip(), parts[1].strip(), parts[2].strip())
            actions.append({"tag": "GMAIL", "cmd": cmd})

        elif tag == "GCAL":
            # e.g. [GCAL: check], [GCAL: add Title|2025-12-01|09:00]
            sub = args.split(maxsplit=1)
            cmd = sub[0].lower()
            if cmd == "check":
                get_upcoming_events()
            elif cmd == "add" and len(sub) > 1:
                parts = sub[1].split("|")
                if len(parts) == 3:
                    add_event(parts[0].strip(), parts[1].strip(), parts[2].strip())
            actions.append({"tag": "GCAL", "cmd": cmd})

        elif tag == "GATEWAY":
            # e.g. [GATEWAY: sync], [GATEWAY: fetch_email], [GATEWAY: lock]
            cmd = args.lower().strip()
            actions.append({"tag": "GATEWAY", "cmd": cmd})
            # Gateway commands are handled by hzl_ws.py via the orchestrator

        elif tag == "QUEUE":
            # e.g. [QUEUE: send_email to="tim" subject="hi" body="hello"]
            parts = args.split(maxsplit=1)
            cmd = parts[0].lower() if parts else ""
            params_str = parts[1] if len(parts) > 1 else ""
            # Parse key="value" pairs
            import re as _re
            params = dict(_re.findall(r'(\w+)="([^"]*)"', params_str))
            actions.append({"tag": "QUEUE", "cmd": cmd, "params": params})

    global _last_actions
    _last_actions = actions
    return actions

# ── SYSTEM PROMPT ──────────────────────────────────────────────────────────
def build_system_prompt(hint: str = None) -> str:
    now     = datetime.now().strftime("%A, %B %d, %Y · %I:%M %p")
    facts   = get_all_facts()

    # Live weather
    try:
        weather = get_weather() or "Weather unavailable."
    except Exception:
        weather = "Weather unavailable."

    # Live calendar — injected so Scatter knows schedule without action tags
    try:
        cal_raw = get_upcoming_events(8)
        if cal_raw and not cal_raw.startswith("No upcoming") and not cal_raw.startswith("Calendar error"):
            calendar_block = f"\n\nUpcoming calendar events:\n{cal_raw}"
        else:
            calendar_block = ""
    except Exception:
        calendar_block = ""

    # Live email — inject unread summary so Scatter can answer email questions
    try:
        email_raw = get_unread_emails()
        if email_raw and isinstance(email_raw, str) and not email_raw.startswith("No "):
            email_block = f"\n\nUnread emails:\n{email_raw}"
        elif email_raw and isinstance(email_raw, list):
            lines = [f"From {e.get('from','')}: {e.get('subject','')}" for e in email_raw[:6]]
            email_block = f"\n\nUnread emails:\n" + "\n".join(lines)
        else:
            email_block = ""
    except Exception:
        email_block = ""

    # Cluster status — injected so Scatter knows the system state
    try:
        from hzl_cluster.integration import get_cluster_status
        cluster_raw = get_cluster_status()
        if cluster_raw:
            cluster_block = f"\n\nCluster status:\n{cluster_raw}"
        else:
            cluster_block = ""
    except Exception:
        cluster_block = ""

    facts_block = ""
    if facts:
        facts_block = "\n\nWhat you know about the user:\n" + \
            "\n".join(f"  • {k}: {v}" for k, v in facts.items())

    hint_note = ""
    if hint:
        hint_map = {
            "weather":     "The user is asking about weather. Be specific about Garden City, NY.",
            "calendar":    "The user is checking their schedule. Be concise — list events clearly.",
            "email":       "The user wants to check email. Summarize clearly, flag anything urgent.",
            "music":       "The user is asking about music or Spotify. Use SPOTIFY action if needed.",
            "home":        "The user is asking about smart home status. Use ACTION tags if toggling.",
            "news":        "The user wants news. Summarize the top stories briefly.",
            "medications": "The user is checking medications. Be precise about timing and dosage.",
            "contacts":    "The user is looking up a contact. Be helpful and direct.",
            "memory":      "The user wants to know what you remember about them.",
        }
        note = hint_map.get(hint, "")
        if note:
            hint_note = f"\n\nContext: {note}"

    return f"""You are Scatter — a local-first assistant built for dignity, clarity, and agency.

Your frame is human rights, mutual aid, and plain language — not luxury, not status, not performance. You help the user coordinate their day, their home, and their work so they can show up for themselves and others. You never talk down. You never imply that tools or money define a person's worth. You treat access to information, health, and calm as things every person deserves.

You are steady, direct, and kind: you answer, you don't posture. You remember what matters to the user and use it to be useful, not to flex memory. If something is heavy, you stay with it in a grounded way. If something is hopeful, you let it breathe.

If someone asks the same question twice, answer it again cleanly. Do NOT comment on the repetition, do NOT therapize, do NOT analyze their behavior. Just answer.

Current time: {now}
Weather: {weather}{facts_block}{calendar_block}{email_block}{cluster_block}{hint_note}

How you speak:
  • Short and clear. No corporate cheer, no fake enthusiasm.
  • Never say "Certainly!", "Of course!", "Great question!", "Absolutely!" — ever.
  • No filler. No preamble. Just the response.
  • Grounded and respectful — helpful, not sycophantic.
  • If something is funny, be funny. If something is hard, be steady.
  • Use what you remember to be useful, not to perform having a perfect memory.

When the user asks to see their calendar, email, music, weather, or any panel — respond with a brief 1-2 sentence acknowledgment AND include [PANEL: calendar] (or email/music/weather/news) to open the panel automatically. Never reprint full data in chat — the panel handles display. Examples:
  User: "show my calendar" → "Pulled up. Looks like a full morning." [PANEL: calendar]
  User: "check my email" → "You've got a few things waiting." [PANEL: email]
  User: "what's the weather" → "Checking now." [PANEL: weather]

Action tags (include silently in responses when needed):
  [REMINDER: HH:MM message]               — Set a reminder
  [SPOTIFY: play QUERY]                   — Play a song, artist, or playlist on Spotify
  [SPOTIFY: pause]                        — Pause Spotify
  [SPOTIFY: skip]                         — Skip to next track
  [SPOTIFY: previous]                     — Go to previous track
  [GMAIL: check]                          — Check unread email
  [GMAIL: read SENDER]                    — Read email body from sender
  [GMAIL: search QUERY]                   — Search email
  [GMAIL: send TO|SUBJECT|BODY]           — Send email
  [GCAL: check]                           — Check upcoming calendar events
  [GCAL: add TITLE|YYYY-MM-DD|HH:MM]     — Add calendar event
  [HEALTH: add_med NAME|DOSE|FREQUENCY|TIME] — Add a medication to track
  [HEALTH: took NAME]                    — Log that user took a medication
  [HEALTH: remove_med NAME]              — Remove a medication from tracking
  [GATEWAY: sync]                         — Trigger an internet sync cycle
  [GATEWAY: fetch_email]                  — Queue an email fetch for next sync
  [GATEWAY: fetch_weather]                — Queue a weather update for next sync
  [GATEWAY: fetch_news]                   — Queue a news fetch for next sync
  [GATEWAY: lock]                         — Lock the air-gap (no internet until unlocked)
  [GATEWAY: unlock]                       — Unlock the air-gap
  [GATEWAY: status]                       — Report sync status
  [QUEUE: send_email to="X" subject="Y" body="Z"] — Queue an email to send on next sync

When the user asks to play music, ALWAYS include [SPOTIFY: play QUERY] in your response with the exact artist or song they requested. Example: "Playing The Beatles for you. [SPOTIFY: play The Beatles]"
Do not say you cannot play music — you can. Always use the action tag.

You have full web search and article reading capabilities through Tavily. When the user asks you to look something up, read an article, search the web, or asks about current events you don't know about — you CAN do this. The system handles web search automatically when URLs or search queries are detected. Never say you can't access links or the web — you can.

You also have these capabilities that you should never deny:
  • Playing, pausing, skipping music on Spotify
  • Checking and sending email via Gmail
  • Reading and adding calendar events via Google Calendar
  • Setting reminders
  • Smart home control
  • Web search and article reading via Tavily
  • News headlines via NewsAPI
  • Medication tracking

If something fails, say it didn't work — don't say you can't do it."""

# ── MAIN ENTRY POINT ───────────────────────────────────────────────────────
_client = None

def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client

def get_response(message: str, hint: str = None, routed_model: str = None, routed_max_tokens: int = None) -> str:
    """
    Called by hzl_ws.py for every chat message.
    Returns cleaned response text (action tags stripped for display).

    routed_model/routed_max_tokens: if provided by the orchestrator,
    override local model selection. Falls back to choose_model() if not set.
    """
    client  = get_client()
    model   = routed_model or choose_model(message)
    max_tokens = routed_max_tokens or 1024
    history = get_recent(12)
    system  = build_system_prompt(hint)

    # Build messages list from recent history
    messages = []
    for turn in history:
        role    = turn[0] if isinstance(turn, tuple) else turn.get("role", "user")
        content = turn[1] if isinstance(turn, tuple) else turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    # Prompt injection scan — log threats but don't block (Scatter's system prompt handles it)
    threats = detect_injection(message)
    if threats:
        log.warning(f"Prompt injection detected: {threats} | msg={message[:100]!r}")

    # Wrap user message to structurally separate it from system context
    messages[-1]["content"] = f"<user_input>{message}</user_input>"

    log.info(f"Calling {model} (max_tokens={max_tokens}) | hint={hint!r} | msg={message[:50]!r}")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        raw_text = response.content[0].text
    except anthropic.APIError as e:
        log.error(f"Anthropic API error: {e}")
        return "I'm having trouble connecting right now. Please try again in a moment."

    # Execute any embedded action tags
    actions = parse_actions(raw_text)
    if actions:
        log.info(f"Executed actions: {actions}")

    # Strip action tags from displayed/spoken text
    clean = ACTION_RE.sub('', raw_text).strip()

    # Save to memory
    save_message("user",      message)
    save_message("assistant", clean)

    # Return raw text so hzl_ws.py can parse Spotify/panel tags
    return raw_text
ask = get_response
