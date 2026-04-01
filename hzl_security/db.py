"""
HZL Security — Safe SQLite Wrapper (Python)
For use in Hazel and any HZL Python service using SQLite.

NEVER use f-strings or string formatting to build SQL queries.
This module enforces parameterized queries. Always.

Usage:
  from hzl_security.db import HZLDatabase

  db = HZLDatabase("~/jarvis/hazel.db")
  db.execute("INSERT INTO logs (message, ts) VALUES (?, ?)", [msg, ts])
  rows = db.query("SELECT * FROM logs WHERE user = ?", [user_id])
"""

import sqlite3
import os
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("hzl.db")


class HZLDatabase:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10,
        )
        conn.row_factory = sqlite3.Row  # access columns by name
        # Enable WAL mode for better concurrent read performance
        conn.execute("PRAGMA journal_mode=WAL")
        # Foreign key enforcement
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def _cursor(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"DB error: {e}")
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Create baseline tables if they don't exist."""
        with self._cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hzl_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """)

    def execute(self, sql: str, params: list = None) -> int:
        """
        Execute a write query (INSERT, UPDATE, DELETE).
        Returns: lastrowid

        ✅ Always use ? placeholders, never f-strings.
        Example:
          db.execute("INSERT INTO logs (msg) VALUES (?)", [message])
        """
        self._validate_params(sql, params)
        with self._cursor() as cur:
            cur.execute(sql, params or [])
            return cur.lastrowid

    def query(self, sql: str, params: list = None) -> list[dict]:
        """
        Execute a read query (SELECT).
        Returns: list of row dicts

        Example:
          rows = db.query("SELECT * FROM users WHERE id = ?", [user_id])
        """
        self._validate_params(sql, params)
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            rows = cur.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"DB query error: {e}")
            raise
        finally:
            conn.close()

    def query_one(self, sql: str, params: list = None) -> Optional[dict]:
        """Returns first matching row or None."""
        results = self.query(sql, params)
        return results[0] if results else None

    def audit_log(self, event_type: str, details: str = None, ip: str = None):
        """
        Write a security event to the audit log.
        Call this for: auth attempts, rate limit hits, unexpected input, etc.
        """
        self.execute(
            "INSERT INTO hzl_audit_log (event_type, details, ip_address) VALUES (?, ?, ?)",
            [event_type, details, ip]
        )

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        return self.query(
            "SELECT * FROM hzl_audit_log ORDER BY created_at DESC LIMIT ?",
            [limit]
        )

    @staticmethod
    def _validate_params(sql: str, params: Optional[list]):
        """
        Safety check: if a query has ? placeholders, params must be provided.
        Catches the case where someone forgets to pass params and leaves raw values.
        """
        placeholder_count = sql.count("?")
        param_count = len(params) if params else 0

        if placeholder_count != param_count:
            raise ValueError(
                f"SQL parameter mismatch: query has {placeholder_count} "
                f"placeholder(s) but {param_count} param(s) provided.\n"
                f"Query: {sql}"
            )

        # Warn if query looks like it might have f-string interpolation artifacts
        suspicious = ["{", "}", "%s", "' +", "\" +"]
        for s in suspicious:
            if s in sql:
                logger.warning(
                    f"Suspicious SQL pattern detected: '{s}' in query. "
                    "Use ? parameterization, not string formatting."
                )
