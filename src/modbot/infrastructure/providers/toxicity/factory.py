"""Factory for toxicity scoring provider selection."""
from __future__ import annotations

import os
from .perspective import PerspectiveScorer
from .detoxify import DetoxifyScorer
from .neutral import NeutralScorer
from ....config.settings import BotConfig


def create_toxicity_scorer(conf: BotConfig):
    api_key = conf.perspective_api_key or os.getenv("PERSPECTIVE_API_KEY")
    if api_key:
        attr_env = os.getenv("PERSPECTIVE_REQUESTED_ATTRIBUTES", "TOXICITY")
        attributes = [a.strip().upper() for a in attr_env.split(',') if a.strip()]
        try:
            timeout = int(os.getenv("PERSPECTIVE_TIMEOUT_SECONDS", "10"))
        except ValueError:
            timeout = 10
        return PerspectiveScorer(api_key, attributes=attributes, timeout=timeout)
    try:
        import importlib
        if importlib.util.find_spec("detoxify"):
            return DetoxifyScorer()
    except Exception:  
        pass
    return NeutralScorer()

__all__ = ['create_toxicity_scorer']
