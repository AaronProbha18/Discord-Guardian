from __future__ import annotations
from typing import Optional, Tuple
import discord
from .registry import register
from ..interfaces import Action
from .helpers import action_escalate


class EscalateAction:
    def can_handle(self, action: str) -> bool:
        return action.startswith('escalate(') and action.endswith(')')
    async def execute(self, message: discord.Message, action: str, toxicity: float, ctx) -> Tuple[bool, Optional[str]]:
        label = 'human_mods'
        if action.startswith('escalate(') and action.endswith(')'):
            label = action[len('escalate('):-1] or label
        success = await action_escalate(message, label, f"toxicity={toxicity:.2f}", ctx)
        return success, None if success else 'escalation_send_failed'

register(EscalateAction())
__all__ = ["EscalateAction"]
