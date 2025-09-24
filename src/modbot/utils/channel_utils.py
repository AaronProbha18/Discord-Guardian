"""Channel / guild related helpers split from utils.py."""
from __future__ import annotations
from typing import Optional
import discord

from .format_utils import truncate_for_discord  # noqa: F401 (re-export convenience if desired)

def find_text_channel(guild: discord.Guild, name: str | None) -> Optional[discord.TextChannel]:
    if not name:
        return None
    name_l = name.lower()
    for ch in getattr(guild, 'channels', []):
        if isinstance(ch, discord.TextChannel) and ch.name.lower() == name_l:
            return ch
    return None

def resolve_escalation_target(guild: discord.Guild, config=None, fallback_channel: str | None = None):
    ch_name = getattr(config, 'mod_alert_channel_name', None) or fallback_channel
    role_name = getattr(config, 'mod_alert_role_name', None)
    channel = find_text_channel(guild, ch_name) if ch_name else None
    role_mention = ""
    if role_name and channel:
        for role in getattr(guild, 'roles', []):
            if role.name.lower() == role_name.lower():
                role_mention = role.mention + " "
                break
    return channel, role_mention

__all__ = ["find_text_channel", "resolve_escalation_target"]
