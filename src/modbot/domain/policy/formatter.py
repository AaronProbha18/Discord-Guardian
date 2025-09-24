"""Policy formatting utilities."""
from __future__ import annotations

from typing import List
from .models import ModerationPolicy


def format_rules(policy: ModerationPolicy, detail: bool = False) -> str:
    lines: List[str] = []
    for r in policy.rules:
        if r.max_exclusive is None:
            rng = f"toxicity >= {r.min_inclusive:.2f}"
        else:
            rng = f"{r.min_inclusive:.2f} <= toxicity < {r.max_exclusive:.2f}"
        actions = ', '.join(r.actions)
        if detail:
            lines.append(f"- {r.name}: {rng}\n    actions: {actions}")
        else:
            lines.append(f"{r.name}: {rng} -> {actions}")
    if not detail:
        if getattr(policy, 'escalation', None) and getattr(policy.escalation, 'parsed', None):
            lines.append("")
            lines.append(f"Escalation window: {policy.escalation.window_minutes} min")
            for base, thresholds in policy.escalation.parsed.items():
                thr_parts = [f"{cnt} -> {follow}" for cnt, follow in thresholds]
                lines.append(f"{base}: " + "; ".join(thr_parts))
        return "\n".join(lines)
    if getattr(policy, 'escalation', None) and getattr(policy.escalation, 'parsed', None):
        lines.append("")
        lines.append("Escalation Thresholds:")
        lines.append(f"  window_minutes: {policy.escalation.window_minutes}")
        for base, thresholds in policy.escalation.parsed.items():
            for cnt, follow in thresholds:
                lines.append(f"  - {base} count=={cnt} => {follow}")
    return "\n".join(lines)

__all__ = ['format_rules']
