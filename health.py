"""
health.py — HZL AI Health & Wellness Module
Handles: medications, mood, sleep, exercise
All data stored locally in SQLite — private, never leaves the Pi.
"""

import sqlite3
import json
import os
import datetime
import time

_HZL_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HZL_DIR, "memory.db")

# ── Database Init ─────────────────────────────────────────────────────────────
def _init_health_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dose TEXT,
            frequency TEXT,
            times TEXT,          -- JSON list of HH:MM strings
            notes TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS medication_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER,
            medication_name TEXT,
            taken_at TEXT,
            dose TEXT,
            notes TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS mood_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT,
            score INTEGER,       -- 1-10
            mood TEXT,           -- label: great/good/okay/low/rough
            energy INTEGER,      -- 1-10
            notes TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sleep_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,              -- date of waking up
            bedtime TEXT,                    -- HH:MM
            wake_time TEXT,                  -- HH:MM
            duration_hours REAL,
            quality INTEGER,                 -- 1-10
            notes TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS exercise_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT,           -- run, walk, gym, yoga, etc.
            duration_min INTEGER,
            intensity TEXT,      -- light/moderate/intense
            notes TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

_init_health_tables()

# ── Medications ───────────────────────────────────────────────────────────────
def add_medication(name, dose=None, frequency=None, times=None, notes=None):
    """Add a medication to track."""
    now = datetime.datetime.now().isoformat()
    times_json = json.dumps(times or [])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Dedup — don't add if already exists and active
    c.execute("SELECT id FROM medications WHERE name = ? AND active = 1", (name,))
    if c.fetchone():
        conn.close()
        print(f"[Health] Medication already exists: {name}, skipping.")
        return None
    c.execute("""
        INSERT INTO medications (name, dose, frequency, times, notes, active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (name, dose, frequency, times_json, notes, now))
    med_id = c.lastrowid
    conn.commit()
    conn.close()
    print(f"[Health] Medication added: {name} ({dose})")
    return med_id

def get_medications():
    """Get all active medications."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, dose, frequency, times, notes FROM medications WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    return [{
        "id": r[0], "name": r[1], "dose": r[2],
        "frequency": r[3], "times": json.loads(r[4] or "[]"), "notes": r[5]
    } for r in rows]

def log_medication_taken(name, dose=None, notes=None):
    """Log that a medication was taken."""
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Find medication id
    c.execute("SELECT id FROM medications WHERE name LIKE ? AND active = 1", (f"%{name}%",))
    row = c.fetchone()
    med_id = row[0] if row else None
    c.execute("""
        INSERT INTO medication_log (medication_id, medication_name, taken_at, dose, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (med_id, name, now, dose, notes))
    conn.commit()
    conn.close()
    print(f"[Health] Medication logged: {name}")

def get_medication_log_today():
    """Get medications taken today."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT medication_name, taken_at, dose
        FROM medication_log
        WHERE taken_at LIKE ?
        ORDER BY taken_at ASC
    """, (f"{today}%",))
    rows = c.fetchall()
    conn.close()
    return [{"name": r[0], "taken_at": r[1], "dose": r[2]} for r in rows]

def get_missed_medications():
    """Check which scheduled medications haven't been logged today."""
    meds = get_medications()
    taken_today = {m["name"] for m in get_medication_log_today()}
    now = datetime.datetime.now()
    missed = []
    for med in meds:
        if med["name"] not in taken_today:
            # Check if any scheduled time has passed
            for t in med["times"]:
                try:
                    scheduled = datetime.datetime.strptime(t, "%H:%M").replace(
                        year=now.year, month=now.month, day=now.day)
                    if now > scheduled:
                        missed.append({"name": med["name"], "dose": med["dose"], "scheduled": t})
                        break
                except Exception:
                    pass
    return missed

def remove_medication(name):
    """Deactivate a medication."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE medications SET active = 0 WHERE name LIKE ?", (f"%{name}%",))
    conn.commit()
    conn.close()

# ── Mood ──────────────────────────────────────────────────────────────────────
MOOD_LABELS = {
    "great": 9, "good": 7, "okay": 5, "low": 3, "rough": 1,
    "amazing": 10, "fine": 5, "bad": 2, "terrible": 1, "anxious": 4,
    "energized": 8, "tired": 3, "neutral": 5, "happy": 8, "sad": 3
}

def log_mood(mood_label=None, score=None, energy=None, notes=None):
    """Log a mood entry."""
    now = datetime.datetime.now()
    if mood_label and score is None:
        score = MOOD_LABELS.get(mood_label.lower(), 5)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO mood_log (date, time, score, mood, energy, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (now.strftime("%Y-%m-%d"), now.strftime("%H:%M"),
          score, mood_label, energy, notes, now.isoformat()))
    conn.commit()
    conn.close()
    print(f"[Health] Mood logged: {mood_label} ({score}/10)")

def get_mood_today():
    """Get mood entries from today."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT score, mood, energy, notes, time
        FROM mood_log WHERE date = ? ORDER BY time ASC
    """, (today,))
    rows = c.fetchall()
    conn.close()
    return [{"score": r[0], "mood": r[1], "energy": r[2], "notes": r[3], "time": r[4]} for r in rows]

def get_mood_trend(days=7):
    """Get average mood over past N days."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT date, AVG(score), AVG(energy)
        FROM mood_log WHERE date >= ?
        GROUP BY date ORDER BY date ASC
    """, (cutoff,))
    rows = c.fetchall()
    conn.close()
    return [{"date": r[0], "avg_score": round(r[1], 1), "avg_energy": round(r[2], 1) if r[2] else None}
            for r in rows]

# ── Sleep ─────────────────────────────────────────────────────────────────────
def log_sleep(bedtime, wake_time, quality=None, notes=None):
    """
    Log a sleep entry.
    bedtime: HH:MM string (previous night)
    wake_time: HH:MM string (this morning)
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now = datetime.datetime.now().isoformat()

    # Calculate duration
    try:
        bed = datetime.datetime.strptime(bedtime, "%H:%M")
        wake = datetime.datetime.strptime(wake_time, "%H:%M")
        if wake < bed:  # crossed midnight
            wake += datetime.timedelta(days=1)
        duration = (wake - bed).seconds / 3600
    except Exception:
        duration = None

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO sleep_log (date, bedtime, wake_time, duration_hours, quality, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (today, bedtime, wake_time, duration, quality, notes, now))
    conn.commit()
    conn.close()
    print(f"[Health] Sleep logged: {duration:.1f}h" if duration else "[Health] Sleep logged")
    return duration

def get_sleep_recent(days=7):
    """Get sleep logs for past N days."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT date, bedtime, wake_time, duration_hours, quality, notes
        FROM sleep_log WHERE date >= ? ORDER BY date DESC
    """, (cutoff,))
    rows = c.fetchall()
    conn.close()
    return [{"date": r[0], "bedtime": r[1], "wake_time": r[2],
             "duration": r[3], "quality": r[4], "notes": r[5]} for r in rows]

def get_sleep_avg(days=7):
    """Get average sleep duration and quality."""
    logs = get_sleep_recent(days)
    if not logs:
        return None
    durations = [l["duration"] for l in logs if l["duration"]]
    qualities = [l["quality"] for l in logs if l["quality"]]
    return {
        "avg_duration": round(sum(durations) / len(durations), 1) if durations else None,
        "avg_quality": round(sum(qualities) / len(qualities), 1) if qualities else None,
        "entries": len(logs)
    }

# ── Exercise ──────────────────────────────────────────────────────────────────
def log_exercise(exercise_type, duration_min=None, intensity=None, notes=None):
    """Log an exercise session."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO exercise_log (date, type, duration_min, intensity, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (today, exercise_type, duration_min, intensity, notes, now))
    conn.commit()
    conn.close()
    print(f"[Health] Exercise logged: {exercise_type} {duration_min}min")

def get_exercise_recent(days=7):
    """Get exercise logs for past N days."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT date, type, duration_min, intensity, notes
        FROM exercise_log WHERE date >= ? ORDER BY date DESC
    """, (cutoff,))
    rows = c.fetchall()
    conn.close()
    return [{"date": r[0], "type": r[1], "duration_min": r[2],
             "intensity": r[3], "notes": r[4]} for r in rows]

def get_exercise_today():
    """Get today's exercise."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT type, duration_min, intensity, notes
        FROM exercise_log WHERE date = ?
    """, (today,))
    rows = c.fetchall()
    conn.close()
    return [{"type": r[0], "duration_min": r[1], "intensity": r[2], "notes": r[3]} for r in rows]

# ── Health Context for brain.py ───────────────────────────────────────────────
def get_health_context():
    """
    Concise health context string injected into Hazel's system prompt.
    Gives Hazel awareness of Ryann's current wellbeing.
    """
    parts = []

    # Mood today
    mood_today = get_mood_today()
    if mood_today:
        latest = mood_today[-1]
        mood_str = f"Mood: {latest['mood'] or str(latest['score']) + '/10'}"
        if latest.get("energy"):
            mood_str += f", energy {latest['energy']}/10"
        parts.append(mood_str)

    # Sleep last night
    sleep = get_sleep_recent(days=1)
    if sleep:
        s = sleep[0]
        if s["duration"]:
            quality_str = f", quality {s['quality']}/10" if s["quality"] else ""
            parts.append(f"Sleep: {s['duration']:.1f}h{quality_str}")

    # Exercise today
    exercise = get_exercise_today()
    if exercise:
        ex = exercise[0]
        parts.append(f"Exercise: {ex['type']} {ex['duration_min']}min")

    # Missed medications
    missed = get_missed_medications()
    if missed:
        names = ", ".join(m["name"] for m in missed)
        parts.append(f"⚠ Missed meds: {names}")

    # Medications taken today
    taken = get_medication_log_today()
    if taken:
        names = ", ".join(m["name"] for m in taken)
        parts.append(f"Meds taken: {names}")

    return "\n".join(parts) if parts else ""

def get_health_summary():
    """Longer summary for explicit health check requests."""
    lines = ["Health summary:"]

    mood_today = get_mood_today()
    if mood_today:
        scores = [m["score"] for m in mood_today if m["score"]]
        avg = sum(scores) / len(scores) if scores else None
        latest_mood = mood_today[-1].get("mood", "")
        if avg:
            lines.append(f"• Mood today: {latest_mood} (avg {avg:.1f}/10 across {len(mood_today)} check-ins)")
    else:
        lines.append("• No mood logged today")

    sleep = get_sleep_avg(days=3)
    if sleep:
        lines.append(f"• Sleep (3-day avg): {sleep['avg_duration']}h" +
                     (f", quality {sleep['avg_quality']}/10" if sleep['avg_quality'] else ""))
    else:
        lines.append("• No recent sleep data")

    exercise = get_exercise_recent(days=3)
    if exercise:
        total_min = sum(e["duration_min"] or 0 for e in exercise)
        lines.append(f"• Exercise (3 days): {len(exercise)} session(s), {total_min} min total")
    else:
        lines.append("• No exercise logged recently")

    meds = get_medications()
    if meds:
        taken = {m["name"] for m in get_medication_log_today()}
        for med in meds:
            status = "✓ taken" if med["name"] in taken else "not yet taken"
            lines.append(f"• {med['name']} {med['dose'] or ''}: {status}")

    missed = get_missed_medications()
    if missed:
        for m in missed:
            lines.append(f"⚠ Missed: {m['name']} (scheduled {m['scheduled']})")

    return "\n".join(lines)
