from __future__ import annotations
import discord
from ..client import ModerationBot
from ...infrastructure.logging.structured_logging import warning as log_warning, info as log_info
from discord import app_commands
from ...utils.channel_utils import find_text_channel

def setup_appeal(bot: ModerationBot):
    @bot.tree.command(name="appeal", description="Submit an appeal for your most recent moderation action")
    @app_commands.describe(reason="Why you believe the action was incorrect")
    async def appeal(interaction: discord.Interaction, reason: str):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        if not bot.policy or not getattr(bot.policy, 'appeals', None):
            await interaction.followup.send("Appeals not configured.")
            log_warning("cmd.appeal.disabled", user_id=interaction.user.id)
            return
        user = interaction.user
        if isinstance(user, discord.Member) and bot.is_moderator(user):
            await interaction.followup.send("Moderators cannot submit appeals.")
            log_warning("cmd.appeal.denied_moderator", user_id=interaction.user.id)
            return
        existing = bot.db.get_open_appeal_for_user(user.id)
        if existing:
            await interaction.followup.send(f"You already have an open appeal (id={existing['id']}).")
            log_warning("cmd.appeal.duplicate", user_id=interaction.user.id, appeal_id=existing['id'])
            return
        last_action = bot.db.get_last_action(user.id, window_minutes=7*24*60)
        action_id = last_action['id'] if last_action else None
        appeal_id = bot.db.create_appeal(user.id, reason[:500], action_id)
        guild = interaction.guild
        if guild and bot.policy.appeals and bot.policy.appeals.channel:
            ch = find_text_channel(guild, bot.policy.appeals.channel)
            if ch:
                try:
                    await ch.send(f"[Appeal #{appeal_id}] from {user.mention} referencing action {action_id or 'n/a'}: {reason[:180]}")
                except Exception:  
                    log_warning("appeal.notify_channel_failed", appeal_id=appeal_id)
        await interaction.followup.send(f"Appeal submitted (id={appeal_id}). A moderator will review it.")
        log_info("appeal.submitted", appeal_id=appeal_id, user_id=interaction.user.id, action_ref=action_id)
    return bot
