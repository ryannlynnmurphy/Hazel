"""
HZL Security — LLM Prompt Injection Defense
For Hazel and any HZL service that proxies user input to Claude.

Prompt injection = a user crafting input that tries to override
Hazel's system prompt and make her do something else.

This module wraps your Claude API calls with:
  - Injection pattern detection
  - Input length enforcement
  - Structural message separation (user content never bleeds into system)
  - Audit logging for suspicious inputs

Usage:
  from hzl_security.llm import safe_claude_call

  response = await safe_claude_call(
      user_input=raw_input,
      system_prompt=HAZEL_SYSTEM_PROMPT,
      client=anthropic_client,
  )
"""

import re
import logging
import os
from typing import Optional

logger = logging.getLogger("hzl.llm")

# ── Injection Patterns ────────────────────────────────────────────────────────

# These are patterns that indicate someone is trying to manipulate the LLM.
# Detection doesn't always mean blocking — we log and optionally sanitize.

INJECTION_PATTERNS = [
    (re.compile(r"ignore\s+(previous|all|your)\s+instructions", re.I), "instruction_override"),
    (re.compile(r"disregard\s+(your|all|previous)\s+(instructions|training|context)", re.I), "instruction_override"),
    (re.compile(r"you\s+are\s+now\s+(a|an|the)\s+\w+", re.I), "persona_override"),
    (re.compile(r"act\s+as\s+(if\s+you\s+are|a|an)", re.I), "persona_override"),
    (re.compile(r"forget\s+everything\s+(above|before|previously)", re.I), "context_wipe"),
    (re.compile(r"new\s+(system\s+)?instructions?:", re.I), "system_injection"),
    (re.compile(r"\[SYSTEM\]|\[INST\]|<\|system\|>|<\|user\|>", re.I), "token_injection"),
    (re.compile(r"(jailbreak|dan\s+mode|developer\s+mode|god\s+mode)", re.I), "jailbreak"),
    (re.compile(r"repeat\s+(after|back)\s+me[:\s]", re.I), "echo_attack"),
    (re.compile(r"print\s+(your|the)\s+system\s+prompt", re.I), "prompt_leak"),
    (re.compile(r"reveal\s+(your|the)\s+(system\s+)?(prompt|instructions)", re.I), "prompt_leak"),
    (re.compile(r"what\s+are\s+your\s+(instructions|rules|guidelines)", re.I), "prompt_leak"),
]

MAX_INPUT_LENGTH = int(os.environ.get("HZL_MAX_INPUT_LENGTH", 4000))


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_injection(user_input: str) -> list[str]:
    """
    Scan input for prompt injection patterns.
    Returns list of detected threat types (empty = clean).
    """
    threats = []
    for pattern, threat_type in INJECTION_PATTERNS:
        if pattern.search(user_input):
            if threat_type not in threats:
                threats.append(threat_type)
    return threats


# ── Safe Claude Call Wrapper ──────────────────────────────────────────────────

async def safe_claude_call(
    user_input: str,
    system_prompt: str,
    client,  # anthropic.AsyncAnthropic
    model: str = "claude-haiku-4-5",
    max_tokens: int = 1024,
    block_on_injection: bool = False,
    db=None,  # Optional HZLDatabase instance for audit logging
    client_id: str = "unknown",
) -> dict:
    """
    Safely call Claude with user input, defending against prompt injection.

    Args:
        user_input: Raw input from the user
        system_prompt: Hazel's system prompt (kept separate from user content)
        client: anthropic.AsyncAnthropic instance
        model: Claude model to use
        max_tokens: Response token limit
        block_on_injection: If True, refuse to call Claude when injection detected
        db: Optional HZLDatabase for audit logging
        client_id: Identifier for the requesting client (for logs)

    Returns:
        {
            "response": str | None,
            "blocked": bool,
            "threats": list[str],
            "flagged": bool,
        }
    """

    # 1. Length check
    if len(user_input) > MAX_INPUT_LENGTH:
        logger.warning(f"Input truncated for client '{client_id}': {len(user_input)} chars")
        user_input = user_input[:MAX_INPUT_LENGTH]

    # 2. Injection scan
    threats = detect_injection(user_input)
    flagged = len(threats) > 0

    if flagged:
        logger.warning(
            f"Prompt injection detected for client '{client_id}': {threats}\n"
            f"Input preview: {user_input[:100]}..."
        )
        if db:
            db.audit_log(
                event_type="prompt_injection_detected",
                details=f"threats={threats} | input_preview={user_input[:200]}",
                ip=client_id,
            )

    # 3. Block if configured to do so
    if block_on_injection and flagged:
        return {
            "response": None,
            "blocked": True,
            "threats": threats,
            "flagged": True,
        }

    # 4. Build messages — user content is always structurally separated
    #    from the system prompt. Never concatenate them.
    #    Wrap user input to make injection attempts inert.
    safe_user_content = f"<user_input>{user_input}</user_input>"

    try:
        message = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,  # system always separate
            messages=[
                {"role": "user", "content": safe_user_content}
            ],
        )

        response_text = message.content[0].text if message.content else ""

        return {
            "response": response_text,
            "blocked": False,
            "threats": threats,
            "flagged": flagged,
        }

    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return {
            "response": None,
            "blocked": False,
            "threats": threats,
            "flagged": flagged,
            "error": str(e),
        }
