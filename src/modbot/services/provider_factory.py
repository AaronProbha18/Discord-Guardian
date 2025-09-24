"""Unified provider factory service for LLM and toxicity scorers."""
from __future__ import annotations

from ..config.settings import BotConfig
from ..infrastructure.providers.llm import create_llm_provider, LLMError, LLMRateLimitError, LLMTimeoutError
from ..infrastructure.providers.toxicity import create_toxicity_scorer


def build_providers(cfg: BotConfig):
    """Return (llm_provider, toxicity_scorer)."""
    llm = create_llm_provider(cfg)
    tox = create_toxicity_scorer(cfg)
    return llm, tox

__all__ = [
    'build_providers', 'LLMError', 'LLMRateLimitError', 'LLMTimeoutError'
]
