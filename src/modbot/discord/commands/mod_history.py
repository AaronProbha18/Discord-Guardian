from __future__ import annotations
import json
import time
import discord
from discord import app_commands
from ..client import ModerationBot
from ...infrastructure.logging.structured_logging import info as log_info, warning as log_warning
from ...utils.decorators import moderator_only
from ...utils.format_utils import format_rel_age, truncate_for_discord

def setup_mod_history(bot: ModerationBot):
    @bot.tree.command(name="mod_history", description="Show recent moderation actions for a user")
    @moderator_only("/mod_history restricted to moderators (configure MOD_EXEMPT_ROLE_NAMES)", "cmd.mod_history.denied")
    @app_commands.describe(
        user="Target user",
        limit="Page size (default 20)",
        window_minutes="Only actions within the past N minutes",
        include_evidence="Include evidence excerpts",
        actions="Filter actions (comma separated)",
        page="Page number (starting at 1)"
    )
    async def mod_history(
        interaction: discord.Interaction,
        user: discord.User,
        limit: int = 20,
        window_minutes: int | None = None,
        include_evidence: bool = False,
        actions: str | None = None,
        page: int = 1,
    ):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        limit = max(1, min(limit, 100))
        action_list: list[str] | None = None
        like_prefixes: list[str] = []
        if actions:
            parsed = [a.strip() for a in actions.split(',') if a.strip()]
            action_list = []
            for a in parsed:
                if a.startswith('timeout_member') and '(' not in a:
                    like_prefixes.append('timeout_member')
                elif a == 'timeout_member':
                    like_prefixes.append('timeout_member')
                else:
                    action_list.append(a)
            if not action_list:
                action_list = None
            if not like_prefixes:
                like_prefixes = []
        page = max(1, page)
        offset = (page - 1) * limit
        rows = bot.db.fetch_actions(
            target_id=user.id,
            limit=limit,
            window_minutes=window_minutes,
            actions=action_list,
            like_prefixes=like_prefixes,
            offset=offset,
        )
        if not rows:
            await interaction.followup.send("No recent moderation actions for that user.")
            return
        now = int(time.time())
        lines: list[str] = []
        total_count = bot.db.count_actions(user.id, window_minutes)
        lines.append(f"History page {page} (page_size={limit}) total_actions={total_count}")
        for r in rows:
            rel = format_rel_age(int(r['ts']), now_ts=now)
            action = r['action']
            reason = r['reason'] or ''
            line = f"{rel} ago • {action} • {reason}"
            if include_evidence and r['evidence_json']:
                try:
                    ev = json.loads(r['evidence_json'])
                    excerpt = ev.get('excerpt')
                    if excerpt:
                        line += f" • \"{excerpt[:80]}\""
                except Exception:
                    pass
            lines.append(line)
        output = truncate_for_discord("\n".join(lines))
        await interaction.followup.send(output)
        log_info("cmd.mod_history", user_id=interaction.user.id)
    return bot
