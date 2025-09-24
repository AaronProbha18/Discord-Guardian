"""Policy loader"""
from __future__ import annotations

import os
import yaml
from .models import ModerationPolicy

POLICY_FILE = os.getenv("POLICY_FILE", "policies/moderation.yaml")


def load_policy(path: str = POLICY_FILE) -> ModerationPolicy:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Policy file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    try:
        policy = ModerationPolicy(**raw)
    except Exception as e: 
        raise ValueError(f"Invalid moderation policy: {e}") from e
    return policy

__all__ = ['load_policy', 'POLICY_FILE']
