"""
todoist.py — HZL AI Todoist Integration
REST API v2 with full debug logging.

Setup:
    Set env var: TODOIST_API_TOKEN
    Get it from: todoist.com → Settings → Integrations → Developer
"""

import os
import requests
from hzl_logger import get_logger

log = get_logger("todoist")

API_TOKEN = os.getenv("TODOIST_API_TOKEN")
BASE_URL  = "https://api.todoist.com/api/v1"
TIMEOUT   = 10


def _headers() -> dict:
    if not API_TOKEN:
        raise EnvironmentError("Missing TODOIST_API_TOKEN in environment.")
    return {"Authorization": f"Bearer {API_TOKEN}"}


def _get(endpoint: str, params: dict = None) -> list | dict:
    url = f"{BASE_URL}/{endpoint}"
    log.debug(f"GET {url} params={params}")
    resp = requests.get(url, headers=_headers(), params=params, timeout=TIMEOUT)
    log.debug(f"Response {resp.status_code} — {len(resp.content)} bytes")
    resp.raise_for_status()
    return resp.json()


def _post(endpoint: str, payload: dict) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    log.debug(f"POST {url} payload={payload}")
    resp = requests.post(url, headers=_headers(), json=payload, timeout=TIMEOUT)
    log.debug(f"Response {resp.status_code}")
    resp.raise_for_status()
    return resp.json() if resp.content else {}


# ── Public API ────────────────────────────────────────────────────────────────

def get_tasks(filter_str: str = "today | overdue") -> str:
    log.info(f"get_tasks() — filter='{filter_str}'")
    try:
        data = _get("tasks")
        tasks = data.get("results", data.get("items", data)) if isinstance(data, dict) else data
        if not tasks:
            log.info("No tasks found")
            return f"No tasks matching '{filter_str}'."

        priority_icons = {1: "", 2: "⚠ ", 3: "🔴 ", 4: "🚨 "}
        lines = []
        for t in tasks[:10]:
            due  = t.get("due", {})
            due_str  = f" (due {due.get('string', '')})" if due else ""
            icon = priority_icons.get(t.get("priority", 1), "")
            lines.append(f"- {icon}{t['content']}{due_str}")

        log.info(f"Returning {len(tasks)} task(s)")
        return f"Tasks ({len(tasks)} found):\n" + "\n".join(lines)

    except Exception as e:
        log.error(f"get_tasks() failed — {e}", exc_info=True)
        return f"Todoist error: {e}"


def add_task(content: str, due_string: str = None, priority: int = 1) -> str:
    log.info(f"add_task() — content='{content}' due='{due_string}' priority={priority}")
    try:
        payload = {"content": content, "priority": priority}
        if due_string:
            payload["due_string"] = due_string

        task   = _post("tasks", payload)
        due_str = f", due {task['due']['string']}" if task.get("due") else ""
        log.info(f"Task created: id={task.get('id')} '{content}'")
        return f"Task added: '{task['content']}'{due_str}."

    except Exception as e:
        log.error(f"add_task() failed — {e}", exc_info=True)
        return f"Todoist error: {e}"


def complete_task(task_name: str) -> str:
    log.info(f"complete_task() — name='{task_name}'")
    try:
        data = _get("tasks")
        tasks = data.get("results", data.get("items", data)) if isinstance(data, dict) else data
        match = next(
            (t for t in tasks if task_name.lower() in t["content"].lower()), None
        )
        if not match:
            log.warning(f"No task matching '{task_name}'")
            return f"No task found matching '{task_name}'."

        url = f"{BASE_URL}/tasks/{match['id']}/close"
        log.debug(f"POST {url}")
        resp = requests.post(url, headers=_headers(), timeout=TIMEOUT)
        resp.raise_for_status()
        log.info(f"Task completed: '{match['content']}'")
        return f"Completed: '{match['content']}'."

    except Exception as e:
        log.error(f"complete_task() failed — {e}", exc_info=True)
        return f"Todoist error: {e}"


def get_task_count() -> str:
    log.info("get_task_count() called")
    try:
        today   = _get("tasks", {"filter": "today"})
        overdue = _get("tasks", {"filter": "overdue"})
        log.info(f"Today: {len(today)}, Overdue: {len(overdue)}")
        return f"You have {len(today)} task(s) due today and {len(overdue)} overdue."
    except Exception as e:
        log.error(f"get_task_count() failed — {e}", exc_info=True)
        return f"Todoist error: {e}"


def get_projects() -> str:
    log.info("get_projects() called")
    try:
        projects = _get("projects")
        names    = [p["name"] for p in projects]
        log.info(f"Found {len(projects)} project(s): {names}")
        return "Your projects: " + ", ".join(names) + "."
    except Exception as e:
        log.error(f"get_projects() failed — {e}", exc_info=True)
        return f"Todoist error: {e}"


# ── Test CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(get_task_count())
    print(get_tasks())
