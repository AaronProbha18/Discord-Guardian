"""Action registry & lookup utilities."""
from __future__ import annotations

from typing import List, Optional
from ..interfaces import Action

_REGISTRY: List[Action] = []


def register(action: Action):  # simple append (idempotent safety)
    if action not in _REGISTRY:
        _REGISTRY.append(action)


def list_actions() -> List[Action]:
    return list(_REGISTRY)


def find_handler(action_str: str) -> Optional[Action]:
    act = action_str.strip()
    for handler in _REGISTRY:
        try:
            if handler.can_handle(act):  # type: ignore[attr-defined]
                return handler
        except Exception:  
            continue
    return None

__all__ = ["register", "list_actions", "find_handler"]

