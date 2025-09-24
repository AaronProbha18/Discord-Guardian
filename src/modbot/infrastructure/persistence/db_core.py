"""SQLite persistence core"""
from __future__ import annotations

import os
import sqlite3

from .migrations import apply_runtime_migrations
from .action_repository import ActionRepository
from .appeals_repository import AppealsRepository

DB_PATH = os.getenv("SQLITE_PATH", "storage/mod.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS action_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER,
  guild_id TEXT,
  channel_id TEXT,
  actor_id TEXT,
  action TEXT,
  target_id TEXT,
  reason TEXT,
  evidence_json TEXT,
  status TEXT DEFAULT 'success',
  failure_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_action_target_ts ON action_log(target_id, action, ts);
CREATE TABLE IF NOT EXISTS appeals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_submitted INTEGER,
    user_id TEXT,
    action_log_id INTEGER,
    reason TEXT,
    status TEXT,
    decision TEXT,
    moderator_id TEXT,
    resolution TEXT,
    ts_decided INTEGER
);
CREATE INDEX IF NOT EXISTS idx_appeals_user_status ON appeals(user_id, status);
"""


def init_connection(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    conn.commit()
    apply_runtime_migrations(conn)
    return conn


class ActionDB:
    """Backward-compatible facade used by existing code.

    Wraps two repositories; new code should prefer using the repositories
    directly for narrower dependency surfaces.
    """
    def __init__(self, path: str = DB_PATH):
        self.conn = init_connection(path)
        self.actions = ActionRepository(self.conn)
        self.appeals = AppealsRepository(self.conn)

    # Delegate methods (action log)
    def log_action(self, *a, **kw):  # type: ignore[override]
        return self.actions.log_action(*a, **kw)

    def count_recent(self, *a, **kw):
        return self.actions.count_recent(*a, **kw)

    def count_recent_like(self, *a, **kw):
        return self.actions.count_recent_like(*a, **kw)

    def fetch_actions(self, *a, **kw):
        return self.actions.fetch_actions(*a, **kw)

    def count_actions(self, *a, **kw):
        return self.actions.count_actions(*a, **kw)

    def aggregate_counts(self, *a, **kw):
        return self.actions.aggregate_counts(*a, **kw)

    def get_last_action(self, *a, **kw):
        return self.actions.get_last_action(*a, **kw)

    # Appeals
    def get_open_appeal_for_user(self, *a, **kw):
        return self.appeals.get_open_appeal_for_user(*a, **kw)

    def create_appeal(self, *a, **kw):
        return self.appeals.create_appeal(*a, **kw)

    def list_appeals(self, *a, **kw):
        return self.appeals.list_appeals(*a, **kw)

    def get_appeal(self, *a, **kw):
        return self.appeals.get_appeal(*a, **kw)

    def decide_appeal(self, *a, **kw):
        return self.appeals.decide_appeal(*a, **kw)

    def purge_old_appeals(self, *a, **kw):
        return self.appeals.purge_old_appeals(*a, **kw)

__all__ = [
    'ActionDB', 'init_connection', 'ActionRepository', 'AppealsRepository', 'DB_PATH'
]
