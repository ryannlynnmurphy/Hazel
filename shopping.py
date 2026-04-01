"""
shopping.py — HZL AI Shopping List
Todoist-backed (with local SQLite fallback) + full debug logging.

Setup:
    Todoist: Set TODOIST_API_TOKEN and create a project called "Shopping"
    Local fallback: No setup needed — uses ~/jarvis/shopping.db automatically
"""

import os
import sqlite3
import requests
from datetime import datetime
from hzl_logger import get_logger

log = get_logger("shopping")

_HZL_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH               = os.path.join(_HZL_DIR, "shopping.db")
TODOIST_TOKEN         = os.getenv("TODOIST_API_TOKEN")
TODOIST_BASE          = "https://api.todoist.com/api/v1"
SHOPPING_PROJECT_NAME = "Shopping"
TIMEOUT               = 10


# ── Todoist helpers ───────────────────────────────────────────────────────────

def _td_headers() -> dict:
    return {"Authorization": f"Bearer {TODOIST_TOKEN}"}


def _get_shopping_project_id() -> str | None:
    log.debug("Fetching Todoist projects to find 'Shopping'")
    resp = requests.get(f"{TODOIST_BASE}/projects", headers=_td_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    projects = data.get("results", data) if isinstance(data, dict) else data
    match = next((p for p in projects if p["name"].lower() == SHOPPING_PROJECT_NAME.lower()), None)
    if match:
        log.debug(f"Found Shopping project id={match['id']}")
    else:
        log.warning("No 'Shopping' project found in Todoist")
    return match["id"] if match else None


# ── Local SQLite backend ──────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shopping_list (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            item     TEXT    NOT NULL,
            quantity TEXT    DEFAULT '1',
            added_at TEXT,
            bought   INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def _local_add(item: str, quantity: str = "1") -> str:
    log.info(f"local add — item='{item}' qty='{quantity}'")
    conn = _db()
    conn.execute(
        "INSERT INTO shopping_list (item, quantity, added_at) VALUES (?, ?, ?)",
        (item.strip(), quantity, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return f"Added '{item}' to your shopping list."


def _local_get() -> str:
    log.info("local get_list()")
    conn = _db()
    rows = conn.execute(
        "SELECT item, quantity FROM shopping_list WHERE bought=0 ORDER BY added_at"
    ).fetchall()
    conn.close()
    if not rows:
        return "Your shopping list is empty."
    lines = [f"- {r[1]}x {r[0]}" if r[1] != "1" else f"- {r[0]}" for r in rows]
    log.info(f"Returning {len(rows)} local item(s)")
    return f"Shopping list ({len(rows)} items):\n" + "\n".join(lines)


def _local_remove(item: str) -> str:
    log.info(f"local remove — item='{item}'")
    conn = _db()
    conn.execute(
        "UPDATE shopping_list SET bought=1 WHERE lower(item) LIKE lower(?)",
        (f"%{item}%",),
    )
    conn.commit()
    changes = conn.execute("SELECT changes()").fetchone()[0]
    conn.close()
    if changes:
        log.info(f"Removed '{item}' from local list")
        return f"Removed '{item}' from your shopping list."
    log.warning(f"Item not found locally: '{item}'")
    return f"Couldn't find '{item}' on your list."


def _local_clear() -> str:
    log.info("local clear()")
    conn = _db()
    conn.execute("UPDATE shopping_list SET bought=1 WHERE bought=0")
    conn.commit()
    conn.close()
    return "Shopping list cleared."


# ── Todoist backend ───────────────────────────────────────────────────────────

def _todoist_add(item: str, quantity: str = "1") -> str:
    log.info(f"todoist add — item='{item}' qty='{quantity}'")
    project_id = _get_shopping_project_id()
    content    = f"{quantity}x {item}" if quantity != "1" else item
    payload    = {"content": content}
    if project_id:
        payload["project_id"] = project_id
    resp = requests.post(f"{TODOIST_BASE}/tasks", headers=_td_headers(), json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    log.info(f"Todoist task created: '{content}'")
    return f"Added '{content}' to Shopping list."


def _todoist_get() -> str:
    log.info("todoist get_list()")
    project_id = _get_shopping_project_id()
    if not project_id:
        return "No 'Shopping' project found in Todoist."
    resp = requests.get(
        f"{TODOIST_BASE}/tasks",
        headers=_td_headers(),
        params={"project_id": project_id},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    tasks = resp.json()
    if not tasks:
        return "Your shopping list is empty."
    lines = [f"- {t['content']}" for t in tasks]
    log.info(f"Returning {len(tasks)} Todoist shopping item(s)")
    return f"Shopping list ({len(tasks)} items):\n" + "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def _use_todoist() -> bool:
    return bool(TODOIST_TOKEN)


def add_item(item: str, quantity: str = "1") -> str:
    log.info(f"add_item() — item='{item}' qty='{quantity}' backend={'todoist' if _use_todoist() else 'local'}")
    try:
        if _use_todoist():
            return _todoist_add(item, quantity)
        return _local_add(item, quantity)
    except Exception as e:
        log.error(f"add_item() todoist failed, falling back to local — {e}", exc_info=True)
        return _local_add(item, quantity)


def get_list() -> str:
    log.info(f"get_list() — backend={'todoist' if _use_todoist() else 'local'}")
    try:
        if _use_todoist():
            return _todoist_get()
        return _local_get()
    except Exception as e:
        log.error(f"get_list() todoist failed, falling back to local — {e}", exc_info=True)
        return _local_get()


def remove_item(item: str) -> str:
    return _local_remove(item)


def clear_list() -> str:
    return _local_clear()


def add_multiple(items: list) -> str:
    log.info(f"add_multiple() — {len(items)} item(s)")
    clean  = [i.strip() for i in items if i.strip()]
    for item in clean:
        add_item(item)
    return f"Added {len(clean)} items: " + ", ".join(clean) + "."


# ── Test CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(get_list())
