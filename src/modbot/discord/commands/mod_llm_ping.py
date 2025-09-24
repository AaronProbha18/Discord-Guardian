from __future__ import annotations
import discord
from ..client import ModerationBot
from ...infrastructure.logging.structured_logging import error as log_error

def setup_mod_llm_ping(bot: ModerationBot):
    @bot.tree.command(name="mod_llm_ping", description="Test LLM provider connectivity")
    async def mod_llm_ping(interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            reply = await bot.llm.complete("Reply with 'pong' only.")
            await interaction.followup.send(f"LLM response: {reply[:100]}")
        except Exception as e:  
            await interaction.followup.send(f"LLM error: {e}")
            log_error("cmd.mod_llm_ping.error", user_id=interaction.user.id, error=str(e))
    return bot
