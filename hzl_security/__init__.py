"""
HZL Security — Hazel's security infrastructure.

Usage:
    from hzl_security.ws_auth import require_ws_auth, generate_ws_token
    from hzl_security.llm import safe_claude_call
    from hzl_security.db import HZLDatabase
"""

from hzl_security.ws_auth import (
    generate_ws_token,
    validate_ws_token,
    authenticate_websocket,
    WSRateLimiter,
    sanitize_ws_input,
)
from hzl_security.llm import safe_claude_call, detect_injection
from hzl_security.db import HZLDatabase
