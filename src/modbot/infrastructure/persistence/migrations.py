"""Lightweight runtime migration helpers."""
from __future__ import annotations

import sqlite3


def apply_runtime_migrations(conn: sqlite3.Connection) -> None:
    """Ensure newly added columns exist (idempotent)."""
    cur = conn.execute("PRAGMA table_info(action_log)")
    cols = {row[1] for row in cur.fetchall()}
    altered = False
    if 'status' not in cols:
        conn.execute("ALTER TABLE action_log ADD COLUMN status TEXT DEFAULT 'success'")
        altered = True
    if 'failure_reason' not in cols:
        conn.execute("ALTER TABLE action_log ADD COLUMN failure_reason TEXT")
        altered = True
    if altered:
        conn.commit()

__all__ = ["apply_runtime_migrations"]
