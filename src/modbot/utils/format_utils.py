"""Formatting helpers split from utils.py."""
from __future__ import annotations
import time

def truncate_for_discord(text: str, limit: int = 1950) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."

def format_rel_age(ts: int, now_ts: int | None = None) -> str:
    now_ts = now_ts or int(time.time())
    delta = max(0, now_ts - ts)
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    if delta < 86400:
        return f"{delta // 3600}h"
    return f"{delta // 86400}d"

__all__ = ["truncate_for_discord", "format_rel_age"]
