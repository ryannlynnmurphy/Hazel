"""
HZL AI · Quality Gate (quality_gate.py)
Checks whether a model response is good enough or needs escalation.
"""

import re
import logging

log = logging.getLogger(__name__)

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

_ACTION_TAGS = re.compile(r'\[(SPOTIFY|GMAIL|GCAL|REMINDER|HEALTH|PANEL):', re.IGNORECASE)


def check(response: str | None, message: str, tier: int) -> bool:
    if not response:
        log.info(f"Quality gate FAIL (tier {tier}): empty response")
        return False

    if len(response.strip()) < 10:
        log.info(f"Quality gate FAIL (tier {tier}): too short ({len(response)} chars)")
        return False

    words = response.split()
    if len(words) > 6:
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words) - 2)]
        for tri in set(trigrams):
            if trigrams.count(tri) >= 3:
                log.info(f"Quality gate FAIL (tier {tier}): degenerate repetition")
                return False

    if tier <= 2 and _REFUSAL_RE.search(response):
        log.info(f"Quality gate FAIL (tier {tier}): model refused")
        return False

    if tier <= 2 and _needs_action_tags(message) and not _ACTION_TAGS.search(response):
        log.info(f"Quality gate FAIL (tier {tier}): missing required action tags")
        return False

    return True


def _needs_action_tags(message: str) -> bool:
    m = message.lower()
    action_triggers = [
        "play ", "pause", "skip", "next track", "previous",
        "send email", "check email", "check my email", "inbox",
        "add to calendar", "schedule", "check calendar",
        "remind me", "set a reminder", "set reminder",
        "took my", "add medication", "log medication",
    ]
    return any(trigger in m for trigger in action_triggers)
