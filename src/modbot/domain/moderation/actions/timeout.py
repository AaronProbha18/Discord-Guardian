from __future__ import annotations
from typing import Optional, Tuple
import discord
from .registry import register
from ..interfaces import Action
from .helpers import action_timeout_member


class TimeoutAction:
    def can_handle(self, action: str) -> bool:
        return action.startswith('timeout_member')
    async def execute(self, message: discord.Message, action: str, toxicity: float, ctx) -> Tuple[bool, Optional[str]]:
        minutes = 30
        if action.startswith('timeout_member(') and action.endswith(')'):
            inside = action[len('timeout_member('):-1]
            if inside.isdigit():
                minutes = int(inside)
        success = await action_timeout_member(message, minutes, f"toxicity={toxicity:.2f}")
        return success, None if success else 'timeout_failed'

register(TimeoutAction())
__all__ = ["TimeoutAction"]
