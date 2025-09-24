from __future__ import annotations
from typing import Optional, Tuple
import discord
from .registry import register
from ..interfaces import Action
from .helpers import action_warn_user


class WarnUserAction:
    def can_handle(self, action: str) -> bool:
        return action.strip().lower() == 'warn_user'
    async def execute(self, message: discord.Message, action: str, toxicity: float, ctx) -> Tuple[bool, Optional[str]]:  # noqa: ARG002
        await action_warn_user(message, f"toxicity={toxicity:.2f}", escalation_ctx=ctx)
        return True, None

register(WarnUserAction())
__all__ = ["WarnUserAction"]
