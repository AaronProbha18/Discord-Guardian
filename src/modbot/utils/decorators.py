"""Decorator utilities split from utils.py."""
from __future__ import annotations
from typing import Callable, Awaitable, Any, TypeVar, Coroutine
from functools import wraps
import discord


F = TypeVar("F", bound=Callable[..., Any])


def moderator_only(message: str, log_event: str):
    def decorator(func: Callable[[discord.Interaction, Any], Awaitable[Any]]):  # type: ignore[type-arg]
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, **kwargs):  # type: ignore
            bot = interaction.client  # type: ignore[attr-defined]
            member = interaction.user if isinstance(interaction.user, discord.Member) else None
            if not getattr(bot, 'is_moderator', lambda m: False)(member):
                from ..infrastructure.logging.structured_logging import warning  # local import to avoid circular
                await interaction.response.send_message(message, ephemeral=True)
                warning(log_event, user_id=getattr(interaction.user, 'id', None))
                return
            await interaction.response.defer(ephemeral=True)
            return await func(interaction, **kwargs)
        return wrapper
    return decorator

__all__ = ["moderator_only"]
