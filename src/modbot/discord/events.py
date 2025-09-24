from __future__ import annotations

import discord
from typing import List

from .client import bot, ModerationBot
from ..infrastructure.logging.structured_logging import (
    info as log_info,
    warning as log_warning,
    debug as log_debug,
    error as log_error,
)
from ..services.escalation_service import evaluate_escalation_thresholds
from ..domain.moderation.actions.runner import run_actions

class EscalationContext:
    def __init__(self, bot: ModerationBot, message: discord.Message, toxicity: float):
        self.bot = bot
        self.message = message
        self.toxicity = toxicity
        self.guild_id = getattr(message.guild, 'id', None)
        self.window_minutes = bot.policy.escalation.window_minutes if bot.policy else 60
        self.pending_followups: List[str] = []

    def record(self, action: str, target_id: int, status: str = 'success', failure_reason: str | None = None):
        self.bot.db.log_action(
            self.guild_id,
            getattr(self.message.channel, 'id', None),
            getattr(self.bot.user, 'id', None),
            action,
            target_id,
            f"toxicity={self.toxicity:.2f}",
            evidence={"message_id": self.message.id, "excerpt": self.message.content[:140]},
            status=status,
            failure_reason=failure_reason,
        )
        if status != 'success':
            return
        if not self.bot.policy or not getattr(self.bot.policy, 'escalation', None):
            return
        followups = evaluate_escalation_thresholds(
            self.bot.db,
            self.bot.policy.escalation,
            target_id,
            action,
            self.window_minutes,
        )
        for f in followups:
            log_info(
                "escalation.threshold_met",
                base_action=action.split('(')[0].lower(),
                follow_action=f,
                target_id=target_id,
            )
            self.pending_followups.append(f)

@bot.event
async def on_ready():
    log_info("lifecycle.ready", bot_user=str(bot.user), bot_id=getattr(bot.user, 'id', None), guild_count=len(bot.guilds))
    for g in bot.guilds:
        log_info("lifecycle.guild", guild_name=g.name, guild_id=g.id, members=getattr(g, 'member_count', 'n/a'))

@bot.event
async def on_disconnect():
    log_warning("lifecycle.disconnected")

@bot.event
async def on_resumed():
    log_info("lifecycle.resumed")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not bot.policy:
        return
    if isinstance(message.author, discord.Member) and bot.is_moderator(message.author):
        log_debug("message.skip_exempt", user_id=message.author.id)
        return
    try:
        toxicity_score = await bot.toxicity_scorer.score(message.content)
    except Exception as e:  
        log_error("toxicity.error", error=str(e))
        toxicity_score = 0.0
    rule, actions = bot.policy.evaluate_toxicity(toxicity_score)
    if rule:
        log_info("moderation.rule_match", rule=rule.name, toxicity=round(toxicity_score, 4), actions=actions)
        escalation_ctx = EscalationContext(bot, message, toxicity_score)
        try:
            await run_actions(message, actions, toxicity_score, escalation_ctx)
            if escalation_ctx.pending_followups:
                log_info(
                    "moderation.escalation_followups",
                    count=len(escalation_ctx.pending_followups),
                    actions=escalation_ctx.pending_followups,
                )
                await run_actions(message, escalation_ctx.pending_followups, toxicity_score, escalation_ctx)
        except Exception as e:  
            log_error("moderation.action_exec_error", error=str(e))
    else:
        log_debug("moderation.no_match", toxicity=round(toxicity_score,4), excerpt=message.content[:60])
