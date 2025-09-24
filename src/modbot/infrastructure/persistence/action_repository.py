"""Action log data access"""
from __future__ import annotations

import time
import json
import sqlite3
from typing import Optional, Dict


class ActionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def log_action(
        self,
        guild_id: Optional[int],
        channel_id: Optional[int],
        actor_id: Optional[int],
        action: str,
        target_id: Optional[int],
        reason: str,
        evidence: dict | None = None,
        status: str = 'success',
        failure_reason: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO action_log(ts,guild_id,channel_id,actor_id,action,target_id,reason,evidence_json,status,failure_reason) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                int(time.time()),
                str(guild_id) if guild_id else None,
                str(channel_id) if channel_id else None,
                str(actor_id) if actor_id else None,
                action,
                str(target_id) if target_id else None,
                reason,
                json.dumps(evidence or {}),
                status,
                failure_reason,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def count_recent(self, target_id: int, action: str, window_minutes: int) -> int:
        cutoff = int(time.time()) - window_minutes * 60
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM action_log WHERE target_id=? AND action=? AND ts>=? AND status='success'",
            (str(target_id), action, cutoff),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def count_recent_like(self, target_id: int, action_prefix: str, window_minutes: int) -> int:
        cutoff = int(time.time()) - window_minutes * 60
        pattern = f"{action_prefix}%"
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM action_log WHERE target_id=? AND action LIKE ? AND ts>=? AND status='success'",
            (str(target_id), pattern, cutoff),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def fetch_actions(
        self,
        target_id: int,
        limit: int = 20,
        window_minutes: int | None = None,
        actions: list[str] | None = None,
        like_prefixes: list[str] | None = None,
        offset: int = 0,
    ) -> list[dict]:
        clauses = ["target_id = ?"]
        params: list = [str(target_id)]
        if window_minutes is not None and window_minutes > 0:
            cutoff = int(time.time()) - window_minutes * 60
            clauses.append("ts >= ?")
            params.append(cutoff)
        action_subclauses = []
        if actions:
            for a in actions:
                action_subclauses.append("action = ?")
                params.append(a)
        if like_prefixes:
            for p in like_prefixes:
                action_subclauses.append("action LIKE ?")
                params.append(p + '%')
        if action_subclauses:
            clauses.append('(' + ' OR '.join(action_subclauses) + ')')
        where_sql = ' AND '.join(clauses)
        sql = f"SELECT id, ts, action, reason, evidence_json, status, failure_reason FROM action_log WHERE {where_sql} ORDER BY ts DESC LIMIT ? OFFSET ?"
        params.append(int(limit))
        params.append(int(max(0, offset)))
        cur = self.conn.execute(sql, params)
        rows: list[dict] = []
        for r in cur.fetchall():
            rows.append(
                {
                    'id': r[0],
                    'ts': r[1],
                    'action': r[2],
                    'reason': r[3],
                    'evidence_json': r[4],
                    'status': r[5],
                    'failure_reason': r[6],
                }
            )
        return rows

    def count_actions(self, target_id: int, window_minutes: int | None = None) -> int:
        clauses = ["target_id = ?"]
        params: list = [str(target_id)]
        if window_minutes is not None and window_minutes > 0:
            cutoff = int(time.time()) - window_minutes * 60
            clauses.append("ts >= ?")
            params.append(cutoff)
        sql = f"SELECT COUNT(*) FROM action_log WHERE {' AND '.join(clauses)}"
        cur = self.conn.execute(sql, params)
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def aggregate_counts(self, window_minutes: int = 1440) -> Dict[str, int]:
        cutoff = int(time.time()) - window_minutes * 60
        cur = self.conn.execute(
            "SELECT action, COUNT(*) FROM action_log WHERE ts >= ? AND status='success' GROUP BY action",
            (cutoff,),
        )
        return {r[0]: r[1] for r in cur.fetchall()}

    def get_last_action(self, user_id: int, window_minutes: int | None = None) -> Optional[dict]:
        params: list = [str(user_id)]
        where = "target_id=? AND status='success'"
        if window_minutes and window_minutes > 0:
            cutoff = int(time.time()) - window_minutes * 60
            where += " AND ts >= ?"
            params.append(cutoff)
        sql = f"SELECT id, ts, action, reason FROM action_log WHERE {where} ORDER BY ts DESC LIMIT 1"
        cur = self.conn.execute(sql, params)
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "ts": row[1], "action": row[2], "reason": row[3]}

__all__ = ["ActionRepository"]
