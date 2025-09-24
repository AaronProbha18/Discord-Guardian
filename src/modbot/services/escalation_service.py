"""Escalation evaluation service.

Encapsulates logic previously embedded in utilities to determine which
follow-up actions should fire after recording a base moderation action.

Design goals:
 - Pure function core for easy unit testing.
 - Service wrapper that depends only on a minimal repository interface
   (`count_recent` / `count_recent_like`).
"""
from __future__ import annotations

from typing import Protocol, Iterable, List


class _ActionCountRepo(Protocol):  # minimal structural typing for DB
    def count_recent(self, target_id: int, action: str, window_minutes: int) -> int: ...
    def count_recent_like(self, target_id: int, action_prefix: str, window_minutes: int) -> int: ...


def evaluate_escalation_thresholds(repo: _ActionCountRepo, escalation_policy, target_id: int, base_action: str, window_minutes: int) -> List[str]:
    """Return list of follow-up actions whose thresholds are newly met.

    A threshold triggers if the count *after* the just-logged action equals the configured count.
    Parameterized actions (e.g. timeout_member(30)) are aggregated by their base prefix.
    """
    if not escalation_policy or not getattr(escalation_policy, 'parsed', None):
        return []
    parsed = getattr(escalation_policy, 'parsed', {}) or {}
    base_root = base_action.split('(')[0].strip().lower()
    thresholds = parsed.get(base_root, [])
    if not thresholds:
        return []
    if base_root == 'timeout_member':
        current_count = repo.count_recent_like(target_id, base_root, window_minutes)
    else:
        current_count = repo.count_recent(target_id, base_root, window_minutes)
    return [follow for cnt, follow in thresholds if cnt == current_count]


class EscalationService:
    def __init__(self, repo: _ActionCountRepo, escalation_policy):
        self._repo = repo
        self._policy = escalation_policy

    def evaluate(self, target_id: int, base_action: str, window_minutes: int) -> List[str]:
        return evaluate_escalation_thresholds(self._repo, self._policy, target_id, base_action, window_minutes)


__all__ = [
    'evaluate_escalation_thresholds', 'EscalationService'
]
