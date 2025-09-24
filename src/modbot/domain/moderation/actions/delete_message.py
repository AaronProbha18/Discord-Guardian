from __future__ import annotations
from typing import Optional, Tuple
import discord
from .registry import register
from ..interfaces import Action
from .helpers import action_delete_message


class DeleteMessageAction:
    def can_handle(self, action: str) -> bool:
        return action.strip().lower() == 'delete_message'
    async def execute(self, message: discord.Message, action: str, toxicity: float, ctx) -> Tuple[bool, Optional[str]]:  # noqa: ARG002
        await action_delete_message(message, f"toxicity={toxicity:.2f}")
        return True, None

register(DeleteMessageAction())
__all__ = ["DeleteMessageAction"]
