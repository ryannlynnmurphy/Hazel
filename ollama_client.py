"""
HZL AI · Ollama Client (ollama_client.py)
Talks to local Ollama instance for Tier 1/2 inference.
"""

import os
import logging
import requests

log = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_TIMEOUT_T1 = 15
OLLAMA_TIMEOUT_T2 = 30


def is_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def chat(model: str, message: str, system_prompt: str,
         max_tokens: int = 200, timeout: int = 15) -> str | None:
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
