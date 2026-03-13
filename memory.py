# -*- coding: utf-8 -*-
"""
JARVIS Memory — SQLite database for conversations, facts, and outputs
"""

import sqlite3
import datetime
import os

DB_PATH = os.path.expanduser("~/jarvis/memory.db")


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create all tables if they don't exist."""
    conn = _connect()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            role      TEXT NOT NULL,
            content   TEXT NOT NULL,
            session   TEXT DEFAULT 'default'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            category  TEXT DEFAULT 'general',
            key       TEXT UNIQUE NOT NULL,
            value     TEXT NOT NULL,
            updated   TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS outputs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            type      TEXT,
            filename  TEXT,
            summary   TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            created   TEXT NOT NULL,
            remind_at TEXT NOT NULL,
            message   TEXT NOT NULL,
            fired     INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    print("[Memory] Database initialized.")


def save_message(role, content, session="default"):
    conn = _connect()
    conn.execute(
        "INSERT INTO conversations (timestamp, role, content, session) VALUES (?,?,?,?)",
        (datetime.datetime.now().isoformat(), role, content, session),
    )
    conn.commit()
    conn.close()


def get_recent(limit=20, session=None):
    conn = _connect()
    if session:
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE session=? ORDER BY id DESC LIMIT ?",
            (session, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return list(reversed(rows))


def remember_fact(key, value, category="general"):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO facts (category, key, value, updated) VALUES (?,?,?,?)",
        (category, key, value, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def recall_fact(key):
    conn = _connect()
    row = conn.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None


def forget_fact(key):
    conn = _connect()
    conn.execute("DELETE FROM facts WHERE key=?", (key,))
    conn.commit()
    conn.close()


def get_all_facts():
    conn = _connect()
    rows = conn.execute(
        "SELECT category, key, value FROM facts ORDER BY category, key"
    ).fetchall()
    conn.close()
    return rows


def search_conversations(query, limit=20):
    conn = _connect()
    rows = conn.execute(
        """SELECT timestamp, role, content FROM conversations
           WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?""",
        (f"%{query}%", limit),
    ).fetchall()
    conn.close()
    return rows


def save_reminder(remind_at, message):
    """remind_at is a datetime object or ISO string"""
    if isinstance(remind_at, datetime.datetime):
        remind_at = remind_at.isoformat()
    conn = _connect()
    conn.execute(
        "INSERT INTO reminders (created, remind_at, message) VALUES (?,?,?)",
        (datetime.datetime.now().isoformat(), remind_at, message),
    )
    conn.commit()
    conn.close()


def get_pending_reminders():
    now = datetime.datetime.now().isoformat()
    conn = _connect()
    rows = conn.execute(
        "SELECT id, message FROM reminders WHERE remind_at <= ? AND fired=0",
        (now,),
    ).fetchall()
    conn.close()
    return rows


def mark_reminder_fired(reminder_id):
    conn = _connect()
    conn.execute("UPDATE reminders SET fired=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def get_stats():
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    user_count = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE role='user'"
    ).fetchone()[0]
    facts_count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    first = conn.execute(
        "SELECT timestamp FROM conversations ORDER BY id ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return {
        "total_messages": total,
        "user_messages": user_count,
        "facts_stored": facts_count,
        "first_conversation": first[0][:10] if first else "N/A",
    }


# Initialize on import
init_db()
