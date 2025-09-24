from __future__ import annotations
import discord
from ..client import ModerationBot
from ...infrastructure.logging.structured_logging import info as log_info
from ...utils.decorators import moderator_only
from discord import app_commands

def setup_mod_metrics(bot: ModerationBot):
    @bot.tree.command(name="mod_metrics", description="Show moderation action counts in the last 24h or custom window")
    @moderator_only("/mod_metrics restricted to moderators", "cmd.mod_metrics.denied")
    @app_commands.describe(window_minutes="Window size in minutes (default 1440 = 24h)")
    async def mod_metrics(interaction: discord.Interaction, window_minutes: int = 1440):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        window_minutes = max(1, min(window_minutes, 7*24*60))
        counts = bot.db.aggregate_counts(window_minutes)
        warn_total = counts.get('warn_user', 0)
        timeout_total = sum(v for k, v in counts.items() if k.startswith('timeout_member'))
        escalations = sum(v for k, v in counts.items() if k.startswith('escalate('))
        lines = [f"Metrics window={window_minutes}m (~{window_minutes/60:.1f}h)"]
        lines.append(f"warns={warn_total} timeouts={timeout_total} escalations={escalations}")
        top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:8]
        for action, ct in top:
            lines.append(f"  {action}: {ct}")
        await interaction.followup.send("\n".join(lines))
        log_info("cmd.mod_metrics", user_id=interaction.user.id)
    return bot
