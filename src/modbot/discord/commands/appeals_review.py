from __future__ import annotations
import time
import discord
from ..client import ModerationBot
from ...infrastructure.logging.structured_logging import info as log_info, warning as log_warning
from ...utils.decorators import moderator_only
from ...utils.format_utils import format_rel_age, truncate_for_discord
from discord import app_commands

def setup_appeals_review(bot: ModerationBot):
    @bot.tree.command(name="appeals_review", description="List or decide appeals (moderators)")
    @moderator_only("Restricted to moderators.", "cmd.appeals_review.denied")
    @app_commands.describe(action="list or decide", appeal_id="Appeal ID (for decide)", decision="uphold|overturn|modify", resolution="Moderator resolution text", status="Filter status for list", user="Filter to user")
    async def appeals_review(
        interaction: discord.Interaction,
        action: str = 'list',
        appeal_id: int | None = None,
        decision: str | None = None,
        resolution: str | None = None,
        status: str | None = 'open',
        user: discord.User | None = None,
        limit: int = 20,
    ):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        action = action.lower()
        if action == 'list':
            rows = bot.db.list_appeals(status=status, user_id=user.id if user else None, limit=min(max(1, limit), 50))
            if not rows:
                await interaction.followup.send("No appeals found.")
                return
            now = int(time.time())
            lines: list[str] = [f"Appeals ({len(rows)})"]
            for r in rows:
                rel = format_rel_age(int(r['ts_submitted']), now_ts=now)
                linked = r.get('linked_action') or 'n/a'
                lines.append(
                    f"#{r['id']} {rel} ago user={r['user_id']} status={r['status']} linked={linked} reason={r['reason'][:50]}"
                )
            output = truncate_for_discord("\n".join(lines))
            await interaction.followup.send(output)
            log_info("appeals.list", moderator_id=interaction.user.id, count=len(rows))
        elif action == 'decide':
            if not (appeal_id and decision and resolution):
                await interaction.followup.send("Provide appeal_id, decision, and resolution for 'decide'.")
                log_warning("appeal.decide.missing_params", moderator_id=interaction.user.id)
                return
            decision = decision.lower()
            if decision not in {'uphold', 'overturn', 'modify'}:
                await interaction.followup.send("Decision must be uphold|overturn|modify.")
                log_warning("appeal.decide.invalid_decision", moderator_id=interaction.user.id, decision=decision)
                return
            ok = bot.db.decide_appeal(appeal_id, interaction.user.id, decision, resolution[:400])
            if not ok:
                await interaction.followup.send("Appeal not found or already decided.")
                log_warning("appeal.decide.not_found_or_closed", moderator_id=interaction.user.id, appeal_id=appeal_id)
                return
            if bot.policy and getattr(bot.policy, 'appeals', None):
                bot.db.purge_old_appeals(getattr(bot.policy.appeals, 'retention_days', 30))
            ap = bot.db.get_appeal(appeal_id)
            notified = ""
            if ap:
                target_user_id = ap['user_id']
                try:
                    if interaction.guild:
                        member = interaction.guild.get_member(int(target_user_id)) if str(target_user_id).isdigit() else None
                    else:
                        member = None
                    if member:
                        dm_text = (
                            f"Your appeal #{appeal_id} has been decided: {decision}.\n"
                            f"Resolution: {resolution[:380]}"
                        )
                        try:
                            await member.send(dm_text)
                            notified = " (user notified)"
                        except Exception:  
                            notified = " (DM failed)"
                except Exception:  
                    pass
            await interaction.followup.send(f"Appeal #{appeal_id} marked decided ({decision}).{notified}")
            log_info("appeal.decided", appeal_id=appeal_id, moderator_id=interaction.user.id, decision=decision, notified=notified.strip())
        else:
            await interaction.followup.send("Unknown action. Use list or decide.")
    return bot
