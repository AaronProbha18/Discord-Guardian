"""ActionRunner orchestrates execution & escalation recording."""
from __future__ import annotations

from typing import List, Optional
import discord

from .registry import find_handler, list_actions

try:
    from modbot.infrastructure.logging.structured_logging import info as log_info, warning as log_warning, error as log_error
except Exception:  
    def log_info(*a, **kw): pass
    def log_warning(*a, **kw): pass
    def log_error(*a, **kw): pass


class ActionRunner:
    def __init__(self):
        # side-effect: importing actions modules ensures registry population
        from . import timeout, escalate, ask_llm, delete_message, warn  # noqa: F401  # pylint: disable=unused-import

    async def run(self, message: discord.Message, actions: List[str], toxicity: float, escalation_ctx=None):
        for original in actions:
            act = original.strip()
            handler = find_handler(act)
            performed = False
            failure_reason: Optional[str] = None
            if not handler:
                log_warning('action.unknown', action=act)
                failure_reason = 'unknown_action'
            else:
                try:
                    performed, failure_reason = await handler.execute(message, act, toxicity, escalation_ctx)  # type: ignore[attr-defined]
                except Exception as e:  # noqa: BLE001
                    log_error('action.execute.error', action=act, error=str(e))
                    performed = False
                    failure_reason = 'exception'
            if escalation_ctx:
                if performed:
                    escalation_ctx.record(act, message.author.id, status='success')
                else:
                    escalation_ctx.record(act, message.author.id, status='failure', failure_reason=failure_reason or 'unspecified')

__all__ = ["ActionRunner"]

# Backwards-compatible helper matching legacy signature used in events.
_global_runner: ActionRunner | None = None

async def run_actions(message, actions, toxicity, escalation_ctx=None):
    global _global_runner  # noqa: PLW0603
    if _global_runner is None:
        _global_runner = ActionRunner()
    await _global_runner.run(message, list(actions), toxicity, escalation_ctx)

__all__.append("run_actions")
