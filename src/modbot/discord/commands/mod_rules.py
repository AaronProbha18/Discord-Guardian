from __future__ import annotations
import discord
from discord import app_commands
from ..client import ModerationBot
from ...domain.policy.formatter import format_rules

def setup_mod_rules(bot: ModerationBot):
    @bot.tree.command(name="mod_rules", description="Show loaded moderation rules")
    @app_commands.describe(detail="Show detailed rule + escalation breakdown")
    async def mod_rules(interaction: discord.Interaction, detail: bool = False):
        if not bot.policy:
            await interaction.response.send_message("No policy loaded", ephemeral=True)
            return
        text = format_rules(bot.policy, detail=detail)
        await interaction.response.send_message(text or "(no rules)", ephemeral=True)
    return bot
