"""
creative.py — HZL AI Creative Intelligence Module
Handles: projects, focus mode, voice journal, energy tracking, Spotify signals
"""

import sqlite3
import json
import os
import time
import datetime
from pathlib import Path

DB_PATH = os.path.expanduser("~/jarvis/memory.db")

# ── Creative Disciplines ──────────────────────────────────────────────────────
DISCIPLINES = [
    "visual_design", "photography", "writing", "marketing",
    "ai_development", "theatre", "film_tv", "music", "audio"
]

# ── Focus Mode ────────────────────────────────────────────────────────────────
# How long (minutes) of deep work before Hazel considers you in flow state
FLOW_THRESHOLD_MIN = 25

_focus_state = {
    "active": False,
    "started_at": None,
    "project": None,
    "interrupted": False,
}

# ── Energy Tracking ───────────────────────────────────────────────────────────
# Maps calendar signals to energy levels
ENERGY_SIGNALS = {
    "morning jog":    "high",
    "workout":        "high",
    "get ready":      "medium",
    "barista shift":  "low",       # draining work
    "commute":        "low",
    "therapy":        "reflective",
    "winding down":   "low",
    "date":           "social",
}

# Spotify genre → work mode signals
SPOTIFY_WORK_SIGNALS = {
    "lo-fi":          "deep_work",
    "ambient":        "deep_work",
    "classical":      "deep_work",
    "jazz":           "creative_flow",
    "indie":          "creative_flow",
    "electronic":     "energized",
    "hip-hop":        "energized",
    "pop":            "light_tasks",
    "podcast":        "passive",
}

# ── Database Init ─────────────────────────────────────────────────────────────
def _init_creative_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            discipline TEXT,
            brief TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT,
            notes TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            entry TEXT NOT NULL,
            summary TEXT,
            mood TEXT,
            project_id INTEGER,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS energy_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            hour INTEGER,
            level TEXT,
            source TEXT,
            notes TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            started_at TEXT,
            ended_at TEXT,
            duration_min INTEGER,
            interrupted INTEGER DEFAULT 0
        )
    """)

    c.execute("DROP TABLE IF EXISTS creative_briefs")
    c.execute("""
        CREATE TABLE IF NOT EXISTS creative_briefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT,
            client TEXT,
            objective TEXT,
            audience TEXT,
            deliverables TEXT,
            deadline TEXT,
            tone TEXT,
            ref_links TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

_init_creative_tables()

# ── Projects ──────────────────────────────────────────────────────────────────
def create_project(name, discipline=None, brief=None, notes=None):
    """Create a new creative project."""
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO projects (name, discipline, brief, status, created_at, updated_at, notes)
        VALUES (?, ?, ?, 'active', ?, ?, ?)
    """, (name, discipline, brief, now, now, notes))
    project_id = c.lastrowid
    conn.commit()
    conn.close()
    return project_id

def get_active_projects():
    """Get all active projects."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, name, discipline, brief, updated_at, notes
        FROM projects WHERE status = 'active'
        ORDER BY updated_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "discipline": r[2],
             "brief": r[3], "updated_at": r[4], "notes": r[5]} for r in rows]

def get_project(project_id):
    """Get a specific project by ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "discipline": row[2],
            "brief": row[3], "status": row[4], "created_at": row[5],
            "updated_at": row[6], "notes": row[7]}

def update_project(project_id, **kwargs):
    """Update project fields."""
    now = datetime.datetime.now().isoformat()
    kwargs["updated_at"] = now
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [project_id]
    c.execute(f"UPDATE projects SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()

def archive_project(project_id):
    """Archive a completed project."""
    update_project(project_id, status="archived")

def get_current_project_context():
    """Returns a brief string summary of active projects for brain.py injection."""
    projects = get_active_projects()
    if not projects:
        return "No active projects."
    lines = []
    for p in projects[:5]:  # cap at 5 for context window
        line = f"• {p['name']}"
        if p["discipline"]:
            line += f" ({p['discipline']})"
        if p["brief"]:
            line += f": {p['brief'][:80]}"
        lines.append(line)
    return "Active projects:\n" + "\n".join(lines)

# ── Creative Briefs ───────────────────────────────────────────────────────────
def save_brief(project_id, title, client=None, objective=None, audience=None,
               deliverables=None, deadline=None, tone=None, references=None):
    """Save a creative brief for a project."""
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO creative_briefs
        (project_id, title, client, objective, audience, deliverables, deadline, tone, ref_links, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, title, client, objective, audience,
          deliverables, deadline, tone, references, now))
    conn.commit()
    conn.close()

def get_brief(project_id):
    """Get the most recent brief for a project."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT * FROM creative_briefs WHERE project_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, (project_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "project_id": row[1], "title": row[2],
        "client": row[3], "objective": row[4], "audience": row[5],
        "deliverables": row[6], "deadline": row[7], "tone": row[8],
        "references": row[9], "created_at": row[10]
    }

# ── Focus Mode ────────────────────────────────────────────────────────────────
def enter_focus_mode(project_name=None):
    """Activate focus mode — Hazel goes quiet."""
    _focus_state["active"] = True
    _focus_state["started_at"] = time.time()
    _focus_state["project"] = project_name
    _focus_state["interrupted"] = False
    print(f"[Focus] Mode activated — {project_name or 'general focus'}")

def exit_focus_mode():
    """Deactivate focus mode and log the session."""
    if not _focus_state["active"]:
        return
    duration = int((time.time() - _focus_state["started_at"]) / 60)
    _log_focus_session(
        project_name=_focus_state["project"],
        started_at=datetime.datetime.fromtimestamp(_focus_state["started_at"]).isoformat(),
        ended_at=datetime.datetime.now().isoformat(),
        duration_min=duration,
        interrupted=_focus_state["interrupted"]
    )
    _focus_state["active"] = False
    _focus_state["started_at"] = None
    print(f"[Focus] Session ended — {duration} min")

def is_focus_active():
    return _focus_state["active"]

def get_focus_state():
    if not _focus_state["active"]:
        return None
    elapsed = int((time.time() - _focus_state["started_at"]) / 60)
    return {
        "active": True,
        "project": _focus_state["project"],
        "elapsed_min": elapsed,
        "in_flow": elapsed >= FLOW_THRESHOLD_MIN
    }

def _log_focus_session(project_name, started_at, ended_at, duration_min, interrupted):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO focus_sessions (project_name, started_at, ended_at, duration_min, interrupted)
        VALUES (?, ?, ?, ?, ?)
    """, (project_name, started_at, ended_at, duration_min, int(interrupted)))
    conn.commit()
    conn.close()

def get_focus_stats(days=7):
    """Get focus session stats for the past N days."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*), SUM(duration_min), AVG(duration_min)
        FROM focus_sessions WHERE started_at > ?
    """, (cutoff,))
    row = c.fetchone()
    conn.close()
    return {
        "sessions": row[0] or 0,
        "total_min": row[1] or 0,
        "avg_min": round(row[2] or 0)
    }

# ── Voice Journal ─────────────────────────────────────────────────────────────
def add_journal_entry(entry, mood=None, project_id=None, summary=None):
    """Save a journal entry."""
    now = datetime.datetime.now()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO journal (date, entry, summary, mood, project_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (now.strftime("%Y-%m-%d"), entry, summary, mood, project_id, now.isoformat()))
    conn.commit()
    conn.close()

def get_today_journal():
    """Get all journal entries from today."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT entry, summary, mood, created_at FROM journal
        WHERE date = ? ORDER BY created_at ASC
    """, (today,))
    rows = c.fetchall()
    conn.close()
    return [{"entry": r[0], "summary": r[1], "mood": r[2], "created_at": r[3]} for r in rows]

def get_journal_range(days=7):
    """Get journal entries for past N days."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT date, entry, summary, mood FROM journal
        WHERE date >= ? ORDER BY date DESC, created_at DESC
    """, (cutoff,))
    rows = c.fetchall()
    conn.close()
    return [{"date": r[0], "entry": r[1], "summary": r[2], "mood": r[3]} for r in rows]

def get_journal_context():
    """Brief journal context string for brain.py injection."""
    entries = get_today_journal()
    if not entries:
        return ""
    summaries = [e["summary"] or e["entry"][:60] for e in entries if e.get("summary") or e.get("entry")]
    return "Today's journal: " + " | ".join(summaries[:3])

# ── Energy Tracking ───────────────────────────────────────────────────────────
def log_energy(level, source=None, notes=None):
    """Log current energy level."""
    now = datetime.datetime.now()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO energy_log (date, hour, level, source, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (now.strftime("%Y-%m-%d"), now.hour, level, source, notes))
    conn.commit()
    conn.close()

def infer_energy_from_calendar(events):
    """
    Given a list of recent/upcoming calendar event strings,
    infer current energy level.
    Returns: 'high' | 'medium' | 'low' | 'reflective' | 'social' | 'unknown'
    """
    now_str = datetime.datetime.now().strftime("%H:%M")
    for event in events:
        event_lower = event.lower()
        for signal, level in ENERGY_SIGNALS.items():
            if signal in event_lower:
                return level
    return "unknown"

def get_task_recommendations(energy_level):
    """
    Given an energy level, suggest what kind of work to prioritize.
    """
    recs = {
        "high": "Great time for deep creative work, complex problem solving, or writing first drafts.",
        "medium": "Good for reviews, planning, emails, and iterative work.",
        "low": "Best for admin tasks, scheduling, listening to references, or light research.",
        "reflective": "Good for journaling, reviewing past work, or planning future creative direction.",
        "social": "Lean into collaboration, client calls, or feedback sessions.",
        "unknown": "No strong signal — follow your instincts.",
    }
    return recs.get(energy_level, recs["unknown"])

# ── Spotify Work Signal ───────────────────────────────────────────────────────
def infer_work_mode_from_spotify(track_name=None, artist=None, genre=None):
    """
    Given currently playing track info, infer work mode.
    Returns a work mode string or None.
    """
    if not any([track_name, artist, genre]):
        return None
    check = " ".join(filter(None, [track_name, artist, genre])).lower()
    for keyword, mode in SPOTIFY_WORK_SIGNALS.items():
        if keyword in check:
            return mode
    return "unknown"

# ── Daily Debrief ─────────────────────────────────────────────────────────────
def build_daily_debrief():
    """
    Build a structured debrief string for end-of-day summary.
    Used by brain.py or ambient loop.
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    journal = get_today_journal()
    focus = get_focus_stats(days=1)
    projects = get_active_projects()

    lines = [f"Daily debrief for {today}:"]

    if focus["sessions"] > 0:
        lines.append(f"• Focus: {focus['sessions']} session(s), {focus['total_min']} min total")

    if journal:
        lines.append(f"• Journal: {len(journal)} entr{'y' if len(journal)==1 else 'ies'}")
        for e in journal[:2]:
            if e.get("summary"):
                lines.append(f"  — {e['summary']}")

    if projects:
        lines.append(f"• Active projects: {', '.join(p['name'] for p in projects[:3])}")

    return "\n".join(lines)

# ── Context String for brain.py ───────────────────────────────────────────────
def get_creative_context():
    """
    Full creative context string injected into Hazel's system prompt.
    Kept concise for token efficiency.
    """
    parts = []

    projects_ctx = get_current_project_context()
    if projects_ctx:
        parts.append(projects_ctx)

    journal_ctx = get_journal_context()
    if journal_ctx:
        parts.append(journal_ctx)

    focus = get_focus_state()
    if focus:
        flow = " (in flow state)" if focus["in_flow"] else ""
        parts.append(f"Focus mode active{flow}: {focus['elapsed_min']} min on {focus['project'] or 'general work'}")

    return "\n".join(parts) if parts else ""
