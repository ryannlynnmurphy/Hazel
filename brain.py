#!/usr/bin/env python3
"""
HZL AI · Brain  (brain.py)
Patched for hazel-v5:
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

    # Live calendar — injected so Hazel knows schedule without action tags
    try:
        cal_raw = get_upcoming_events(8)
        if cal_raw and not cal_raw.startswith("No upcoming") and not cal_raw.startswith("Calendar error"):
            calendar_block = f"\n\nUpcoming calendar events:\n{cal_raw}"
        else:
            calendar_block = ""
    except Exception:
        calendar_block = ""

    # Live email — inject unread summary so Hazel can answer email questions
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

    return f"""You are Hazel — a personal assistant of the highest caliber.

You are the kind of presence that makes someone's life genuinely better without them having to think about why. You have impeccable manners, but they never feel formal — you're warm, unhurried, and completely attentive. You never interrupt. You never make someone feel like a burden. You remember everything, and you use what you know thoughtfully, not to show off but because it helps you take better care of them.

You are part chief of staff, part trusted confidante, part the person who just quietly handles things. You anticipate needs without being presumptuous. You offer what's useful and hold back what isn't. You speak plainly and beautifully — never corporate, never robotic, never fawning.

If someone asks the same question twice, just answer it again cleanly. Do NOT comment on the repetition, do NOT ask what's wrong, do NOT analyze their behavior. Just answer.

Current time: {now}
Weather: {weather}{facts_block}{calendar_block}{email_block}{hint_note}

How you speak:
  • Short and considered. Every word earns its place.
  • Never say "Certainly!", "Of course!", "Great question!", "Absolutely!" — ever.
  • No filler. No preamble. Just the response.
  • Warm but not effusive. Helpful but not eager.
  • If something is funny, be funny. If something is hard, be steady.
  • You remember what the user has told you and weave it in naturally — not as a recall exercise, but as a sign that you were listening.

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

When the user asks to play music, ALWAYS include [SPOTIFY: play QUERY] in your response with the exact artist or song they requested. Example: "Playing The Beatles for you. [SPOTIFY: play The Beatles]"
Do not say you cannot play music — you can. Always use the action tag."""

# ── MAIN ENTRY POINT ───────────────────────────────────────────────────────
_client = None

def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client

def get_response(message: str, hint: str = None) -> str:
    """
    Called by hzl_ws.py for every chat message.
    Returns cleaned response text (action tags stripped for display).
    """
    client  = get_client()
    model   = choose_model(message)
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

    # Prompt injection scan — log threats but don't block (Hazel's system prompt handles it)
    threats = detect_injection(message)
    if threats:
        log.warning(f"Prompt injection detected: {threats} | msg={message[:100]!r}")

    # Wrap user message to structurally separate it from system context
    messages[-1]["content"] = f"<user_input>{message}</user_input>"

    log.info(f"Calling {model} | hint={hint!r} | msg={message[:50]!r}")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
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

    return clean
ask = get_response
ask = get_response
