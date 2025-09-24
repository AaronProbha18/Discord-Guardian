"""Appeals data access repository."""
from __future__ import annotations

import time
import sqlite3
from typing import Optional, List, Dict


class AppealsRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_open_appeal_for_user(self, user_id: int) -> Optional[dict]:
        cur = self.conn.execute(
            "SELECT id, ts_submitted, action_log_id, reason FROM appeals WHERE user_id=? AND status='open' ORDER BY ts_submitted DESC LIMIT 1",
            (str(user_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "ts_submitted": row[1], "action_log_id": row[2], "reason": row[3]}

    def create_appeal(self, user_id: int, reason: str, action_log_id: Optional[int]) -> int:
        cur = self.conn.execute(
            "INSERT INTO appeals(ts_submitted,user_id,action_log_id,reason,status) VALUES(?,?,?,?,?)",
            (int(time.time()), str(user_id), action_log_id, reason, 'open'),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_appeals(self, status: str | None = 'open', user_id: Optional[int] = None, limit: int = 20) -> list[dict]:
        clauses = []
        params: list = []
        if status and status != 'all':
            clauses.append("a.status=?")
            params.append(status)
        if user_id:
            clauses.append("a.user_id=?")
            params.append(str(user_id))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT a.id,a.ts_submitted,a.user_id,a.action_log_id,a.reason,a.status,a.decision,a.moderator_id,a.resolution,a.ts_decided,"\
            " al.action AS linked_action, al.reason AS linked_action_reason, al.ts AS linked_action_ts"\
            f" FROM appeals a LEFT JOIN action_log al ON al.id = a.action_log_id {where}"\
            " ORDER BY a.ts_submitted DESC LIMIT ?"
        )
        params.append(int(limit))
        cur = self.conn.execute(sql, params)
        rows = []
        for r in cur.fetchall():
            rows.append(
                {
                    'id': r[0], 'ts_submitted': r[1], 'user_id': r[2], 'action_log_id': r[3], 'reason': r[4], 'status': r[5],
                    'decision': r[6], 'moderator_id': r[7], 'resolution': r[8], 'ts_decided': r[9],
                    'linked_action': r[10], 'linked_action_reason': r[11], 'linked_action_ts': r[12]
                }
            )
        return rows

    def get_appeal(self, appeal_id: int) -> Optional[dict]:
        cur = self.conn.execute(
            "SELECT a.id,a.ts_submitted,a.user_id,a.action_log_id,a.reason,a.status,a.decision,a.moderator_id,a.resolution,a.ts_decided,"\
            " al.action, al.reason, al.ts FROM appeals a LEFT JOIN action_log al ON al.id=a.action_log_id WHERE a.id=?",
            (appeal_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            'id': r[0], 'ts_submitted': r[1], 'user_id': r[2], 'action_log_id': r[3], 'reason': r[4], 'status': r[5],
            'decision': r[6], 'moderator_id': r[7], 'resolution': r[8], 'ts_decided': r[9],
            'linked_action': r[10], 'linked_action_reason': r[11], 'linked_action_ts': r[12]
        }

    def decide_appeal(self, appeal_id: int, moderator_id: int, decision: str, resolution: str) -> bool:
        cur = self.conn.execute(
            "UPDATE appeals SET status='decided', decision=?, moderator_id=?, resolution=?, ts_decided=? WHERE id=? AND status='open'",
            (decision, str(moderator_id), resolution, int(time.time()), appeal_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def purge_old_appeals(self, retention_days: int):
        if retention_days <= 0:
            return
        cutoff = int(time.time()) - retention_days * 86400
        self.conn.execute(
            "DELETE FROM appeals WHERE status='decided' AND ts_decided IS NOT NULL AND ts_decided < ?",
            (cutoff,),
        )
        self.conn.commit()

__all__ = ["AppealsRepository"]
