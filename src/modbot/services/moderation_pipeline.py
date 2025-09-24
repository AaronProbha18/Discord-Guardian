"""Moderation pipeline orchestrator.

High-level responsibilities:
 1. Score message toxicity (async) using provided scorer.
 2. Match rule from loaded policy.
 3. Run primary actions via ActionRunner.
 4. Handle follow-up escalation actions if any are discovered by the
    escalation context (delegated to the action runner via ctx.record calls).

This keeps `on_message` event handlers thin. Integration layer supplies
dependencies (policy, scorer, action runner, DB facade, logging funcs).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, Any
import discord

try:  # reuse existing logging if available
    from modbot.infrastructure.logging.structured_logging import info as log_info, debug as log_debug, error as log_error
except Exception:  
    def log_info(*a, **kw): pass
    def log_debug(*a, **kw): pass
    def log_error(*a, **kw): pass


class ToxicityScorerProto(Protocol):
    async def score(self, text: str) -> float: ...  # noqa: D401


class PolicyProto(Protocol):  # structural subset
    def evaluate_toxicity(self, toxicity: float): ...  # returns (rule, actions)


class ActionRunnerProto(Protocol):
    async def run(self, message: discord.Message, actions: List[str], toxicity: float, escalation_ctx=None): ...


class ActionDBProto(Protocol):  # facade subset for escalation context
    def log_action(self, *a, **kw): ...
    def count_recent(self, target_id: int, action: str, window_minutes: int) -> int: ...
    def count_recent_like(self, target_id: int, action_prefix: str, window_minutes: int) -> int: ...


@dataclass
class EscalationContext:
    bot: Any  # expect attributes: policy, db, user
    message: discord.Message
    toxicity: float
    window_minutes: int
    pending_followups: List[str] = field(default_factory=list)

    def record(self, action: str, target_id: int, status: str = 'success', failure_reason: str | None = None):
        self.bot.db.log_action(
            getattr(self.message.guild, 'id', None),
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
        policy = getattr(self.bot, 'policy', None)
        if not policy or not getattr(policy, 'escalation', None):
            return
        from .escalation_service import evaluate_escalation_thresholds
        followups = evaluate_escalation_thresholds(self.bot.db, policy.escalation, target_id, action, self.window_minutes)
        for f in followups:
            log_info(
                "escalation.threshold_met",
                base_action=action.split('(')[0].lower(),
                follow_action=f,
                target_id=target_id,
            )
            self.pending_followups.append(f)


class ModerationPipeline:
    def __init__(self, scorer: ToxicityScorerProto, action_runner: ActionRunnerProto, policy: PolicyProto, db: ActionDBProto):
        self.scorer = scorer
        self.action_runner = action_runner
        self.policy = policy
        self.db = db

    async def process_message(self, bot, message: discord.Message):  # noqa: ANN001
        if message.author.bot:
            return
        if not self.policy:
            return
        try:
            toxicity = await self.scorer.score(message.content)
        except Exception as e:  
            log_error("toxicity.error", error=str(e))
            toxicity = 0.0
        rule, actions = self.policy.evaluate_toxicity(toxicity)
        if not rule:
            log_debug("moderation.no_match", toxicity=round(toxicity,4), excerpt=message.content[:60])
            return
        log_info("moderation.rule_match", rule=rule.name, toxicity=round(toxicity, 4), actions=actions)
        window_minutes = getattr(getattr(self.policy, 'escalation', None), 'window_minutes', 60)
        esc_ctx = EscalationContext(bot=bot, message=message, toxicity=toxicity, window_minutes=window_minutes)
        await self.action_runner.run(message, actions, toxicity, esc_ctx)
        if esc_ctx.pending_followups:
            log_info("moderation.escalation_followups", count=len(esc_ctx.pending_followups), actions=esc_ctx.pending_followups)
            await self.action_runner.run(message, esc_ctx.pending_followups, toxicity, esc_ctx)

__all__ = [
    'ModerationPipeline', 'EscalationContext'
]
