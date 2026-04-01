"""
HZL Security — WebSocket Auth Handler (Python)
Drop into ~/jarvis/ alongside hzl_ws.py

Usage in hzl_ws.py:
  from hzl_security.ws_auth import require_ws_auth, generate_ws_token

Hazel only talks to clients that present a valid HMAC token.
Token is generated once at boot, stored locally, never sent to the internet.
"""

import asyncio  # FIX: was missing — authenticate_websocket uses asyncio.wait_for
import os
import hmac
import hashlib
import time
import json
import secrets
import logging
from typing import Optional

logger = logging.getLogger("hzl.security")

# ── Token Config ──────────────────────────────────────────────────────────────

TOKEN_EXPIRY_SECONDS = int(os.environ.get("HZL_WS_TOKEN_EXPIRY", 3600))  # 1hr default
WS_SECRET = os.environ.get("HZL_WS_SECRET")

if not WS_SECRET:
    WS_SECRET = secrets.token_hex(32)
    logger.warning(
        "HZL_WS_SECRET not set -- generated a temporary one. "
        "Tokens will not persist across restarts. "
        "Set HZL_WS_SECRET in .env for persistence."
    )


# ── Token Generation ──────────────────────────────────────────────────────────

def generate_ws_token(client_id: str = "hazel-local") -> dict:
    """
    Generate a short-lived HMAC token for WebSocket authentication.
    Call this from your Hazel launcher to get a token for the local UI.

    Returns:
        {"token": str, "expires_at": int, "client_id": str}
    """
    expires_at = int(time.time()) + TOKEN_EXPIRY_SECONDS
    payload = f"{client_id}|{expires_at}"   # FIX: pipe not colon — colons break split if client_id contains one
    
    signature = hmac.new(
        WS_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    token = f"{payload}|{signature}"   # FIX: consistent pipe delimiter
    
    return {
        "token": token,
        "expires_at": expires_at,
        "client_id": client_id
    }


# ── Token Validation ──────────────────────────────────────────────────────────

def validate_ws_token(token: str) -> tuple[bool, Optional[str]]:
    """
    Validate a WebSocket token.
    Returns (is_valid: bool, client_id: Optional[str])
    """
    if not token or not isinstance(token, str):
        return False, None
    
    try:
        # FIX: split on pipe, not colon — allows client_ids that contain colons
        # Token format: client_id|expires_at|signature
        # rsplit with maxsplit=2 makes client_id the catch-all left segment
        parts = token.rsplit("|", 2)
        if len(parts) != 3:
            logger.warning("WS auth: malformed token (wrong part count)")
            return False, None
        
        client_id, expires_at_str, provided_signature = parts
        expires_at = int(expires_at_str)
        
        # Check expiry
        if time.time() > expires_at:
            logger.warning(f"WS auth: expired token for client '{client_id}'")
            return False, None
        
        # Recompute expected signature with pipe delimiter
        payload = f"{client_id}|{expires_at_str}"   # FIX: match generation delimiter
        expected_signature = hmac.new(
            WS_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison (prevents timing attacks)
        if not hmac.compare_digest(expected_signature, provided_signature):
            logger.warning(f"WS auth: invalid signature for client '{client_id}'")
            return False, None
        
        return True, client_id
        
    except (ValueError, AttributeError) as e:
        logger.warning(f"WS auth: token parse error: {e}")
        return False, None


# ── WebSocket Rate Limiter ─────────────────────────────────────────────────────

class WSRateLimiter:
    """
    Per-client rate limiter for WebSocket messages.
    Prevents floods, prompt injection spam, and abuse.
    
    Default: 10 messages per 10 seconds per client.
    """
    
    def __init__(self, max_messages: int = 10, window_seconds: int = 10):
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = {}
    
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        
        if client_id not in self._buckets:
            self._buckets[client_id] = []
        
        # Purge old timestamps
        self._buckets[client_id] = [
            ts for ts in self._buckets[client_id] if ts > window_start
        ]
        
        if len(self._buckets[client_id]) >= self.max_messages:
            logger.warning(f"WS rate limit hit for client '{client_id}'")
            return False
        
        self._buckets[client_id].append(now)
        return True
    
    def cleanup(self):
        """Call periodically to free memory for disconnected clients."""
        now = time.time()
        window_start = now - self.window_seconds
        self._buckets = {
            cid: [ts for ts in timestamps if ts > window_start]
            for cid, timestamps in self._buckets.items()
            if any(ts > window_start for ts in timestamps)
        }


# ── Input Sanitizer ───────────────────────────────────────────────────────────

PROMPT_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard your instructions",
    "you are now",
    "act as if you",
    "forget everything",
    "new instructions:",
    "system prompt:",
    "override:",
    "jailbreak",
    "dan mode",
    "developer mode",
]

def sanitize_ws_input(message: str, max_length: int = 4000) -> tuple[bool, str]:
    """
    Validate and sanitize incoming WebSocket message content before passing to Claude.
    
    Returns (is_safe: bool, sanitized_message: str)
    """
    if not isinstance(message, str):
        return False, ""
    
    # Length cap
    if len(message) > max_length:
        logger.warning(f"WS input: message truncated ({len(message)} > {max_length})")
        message = message[:max_length]
    
    # Prompt injection detection
    lower = message.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern in lower:
            logger.warning(f"WS input: possible prompt injection detected: '{pattern}'")
            # Don't block — log and flag. Let Hazel's system prompt handle it.
            # Change to `return False, ""` if you want hard blocking.
            break
    
    return True, message.strip()


# ── Auth Middleware (for websockets library) ──────────────────────────────────

async def authenticate_websocket(websocket) -> Optional[str]:
    """
    Call at the top of your websocket handler in hzl_ws.py.
    
    Expects client to send auth message first:
      {"type": "auth", "token": "<token>"}
    
    Returns client_id if valid, None if rejected.
    
    Example usage in hzl_ws.py:
    
        async def handle_client(websocket, path):
            client_id = await authenticate_websocket(websocket)
            if not client_id:
                return  # connection already closed
            
            async for message in websocket:
                ...
    """
    try:
        raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        data = json.loads(raw)
        
        if data.get("type") != "auth":
            await websocket.send(json.dumps({"error": "auth_required"}))
            await websocket.close(1008, "Authentication required")
            return None
        
        token = data.get("token", "")
        is_valid, client_id = validate_ws_token(token)
        
        if not is_valid:
            await websocket.send(json.dumps({"error": "invalid_token"}))
            await websocket.close(1008, "Invalid or expired token")
            logger.warning(f"WS: rejected connection from {websocket.remote_address}")
            return None
        
        await websocket.send(json.dumps({"type": "auth_ok", "client_id": client_id}))
        logger.info(f"WS: authenticated client '{client_id}' from {websocket.remote_address}")
        return client_id
        
    except (json.JSONDecodeError, KeyError):
        await websocket.close(1008, "Invalid auth message")
        return None
    except Exception as e:
        logger.error(f"WS auth error: {e}")
        await websocket.close(1011, "Server error")
        return None
