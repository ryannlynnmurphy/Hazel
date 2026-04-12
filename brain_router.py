"""
HZL AI · Brain Router (brain_router.py)
Routes messages through tiered model escalation chain.
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
    m = message.strip().lower().rstrip("?!.")
    if m in _GREETINGS:
        import random
        return random.choice(_GREETING_RESPONSES)
    if _TIME_PATTERNS.match(message.strip()):
        from datetime import datetime
        return datetime.now().strftime("It's %I:%M %p.")
    if _DATE_PATTERNS.match(message.strip()):
        from datetime import datetime
        return datetime.now().strftime("It's %A, %B %d, %Y.")
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
    m = message.lower()
    if _URL_RE.search(message):
        return 3
    if any(t in m for t in _ACTION_TRIGGERS):
        return 3
    if any(kw in m for kw in DEEP_KEYWORDS):
        return 2
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

LOCAL_SYSTEM = (
    "You are Hazel, a personal AI assistant created by Ryann Lynn Murphy. "
    "You run locally on this computer. No cloud, no telemetry. "
    "Answer directly in 2-3 sentences. Be warm but concise. "
    "Do not say 'certainly', 'of course', or 'great question'. "
    "If something is funny, be funny. If something is hard, be steady."
)


def _call_tier(tier: int, message: str, hint: str = None) -> str | None:
    if tier == 1:
        return ollama_chat("phi3:mini", message, LOCAL_SYSTEM, max_tokens=200, timeout=15)
    elif tier == 2:
        return ollama_chat("gpt-oss:20b", message, LOCAL_SYSTEM, max_tokens=400, timeout=30)
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
                else:
                    topic = message.split(' - ')[-1] if ' - ' in message else message
                    search_result = web_search(topic[:100])
                    augmented = f"{message}\n\n[Related info from web search]:\n{search_result}"
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
    return None


# ── Main Router ───────────────────────────────────────────────────────────

def route(message: str, hint: str = None, force_tier: int = None) -> tuple[str, str, str]:
    """
    Routes a message through the tiered model escalation chain.

    Returns (response_text, tier_name, tier_type)
    e.g. ("The weather is nice.", "phi3", "local")
    """
    t0 = time.monotonic()

    if force_tier is not None:
        tier = force_tier
    else:
        instant = _check_instant(message)
        if instant:
            log.info(f"Tier 0 (instant): {message[:40]!r} -> {len(instant)} chars")
            return instant, "instant", "local"
        tier = _classify_min_tier(message)

    if tier <= 2 and not ollama_available():
        log.warning("Ollama not available -- skipping to Tier 3 (Claude Haiku)")
        tier = 3

    max_tier = force_tier if force_tier else 5
    while tier <= max_tier:
        name, ttype = TIER_NAMES.get(tier, ("unknown", "unknown"))
        log.info(f"Trying Tier {tier} ({name}): {message[:40]!r}")
        response = _call_tier(tier, message, hint)
        if quality_gate.check(response, message, tier):
            elapsed = (time.monotonic() - t0) * 1000
            log.info(f"Tier {tier} ({name}) accepted in {elapsed:.0f}ms")
            return response, name, ttype
        log.info(f"Tier {tier} ({name}) failed quality gate -- escalating")
        tier += 1

    return "Something went wrong. Try again.", "error", "error"
