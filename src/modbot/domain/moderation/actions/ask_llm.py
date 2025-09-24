from __future__ import annotations
from typing import Optional, Tuple
import discord
from .registry import register
from ..interfaces import Action
from .helpers import action_ask_llm


class AskLLMAction:
    def can_handle(self, action: str) -> bool:
        return action.strip().lower() == 'ask_llm'
    async def execute(self, message: discord.Message, action: str, toxicity: float, ctx) -> Tuple[bool, Optional[str]]:
        success = await action_ask_llm(message, toxicity, ctx)
        return success, None if success else 'ask_llm_failed'

register(AskLLMAction())
__all__ = ["AskLLMAction"]
