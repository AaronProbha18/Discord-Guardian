from __future__ import annotations
import discord
from ..client import ModerationBot
from ...infrastructure.logging.structured_logging import info as log_info

def setup_mod_status(bot: ModerationBot):
    @bot.tree.command(name="mod_status", description="Show moderation system status")
    async def mod_status(interaction: discord.Interaction):
        log_info("cmd.mod_status", user_id=interaction.user.id, guild_id=getattr(interaction.guild, 'id', None))
        loaded = bot.policy is not None
        await interaction.response.send_message(
            f"Moderation bot online. Policy loaded={loaded}", ephemeral=True
        )
    return bot
