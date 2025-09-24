"""Public behavioral contracts for moderation extension points.

Moved from legacy `contracts.py`.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable, Any, Tuple


@runtime_checkable
class Action(Protocol):
    def can_handle(self, action: str) -> bool: ...  # noqa: D401,E701
    async def execute(self, message, action: str, toxicity: float, ctx) -> Tuple[bool, str | None]: ...


@runtime_checkable
class ToxicityScorer(Protocol):
    async def score(self, text: str) -> float: ...


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(self, prompt: str) -> str: ...


__all__ = ["Action", "ToxicityScorer", "LLMProvider"]
