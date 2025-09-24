from __future__ import annotations
import os
import discord
from ..client import ModerationBot
from ...utils.decorators import moderator_only
from discord import app_commands

def setup_mod_config(bot: ModerationBot):
    @bot.tree.command(name="mod_config", description="Show sanitized runtime configuration & policy highlights")
    @moderator_only("/mod_config restricted to moderators", "cmd.mod_config.denied")
    async def mod_config(interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        cfg = bot.config
        env_show = {
            'MODEL_PROVIDER': cfg.model_provider,
            'MODEL_NAME': cfg.model_name,
            'OLLAMA_HOST': cfg.ollama_host,
            'LLM_TIMEOUT_SECONDS': cfg.llm_timeout_seconds,
            'LLM_MAX_RETRIES': cfg.llm_max_retries,
            'PERSPECTIVE_API_KEY': 'set' if os.getenv('PERSPECTIVE_API_KEY') else 'unset',
            'MOD_EXEMPT_ROLE_NAMES': cfg.mod_exempt_role_names,
            'MOD_ALERT_CHANNEL_NAME': cfg.mod_alert_channel_name,
            'MOD_ALERT_ROLE_NAME': cfg.mod_alert_role_name,
        }
        lines = ["Config summary:"]
        for k, v in env_show.items():
            lines.append(f"  {k}={v}")
        if bot.policy and getattr(bot.policy, 'escalation', None):
            esc = bot.policy.escalation
            bases = ', '.join(f"{b}:{len(thr)}" for b, thr in esc.parsed.items())
            lines.append(f"Escalation window={esc.window_minutes} base_actions={bases}")
        await interaction.followup.send("\n".join(lines))
    return bot
