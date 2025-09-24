"""Structured logging helpers (moved from core.logging_utils)."""
from __future__ import annotations
import json as _json
import logging
import os
from datetime import datetime, timezone
from typing import Any

_LOG_JSON = os.getenv("LOG_JSON") in {"1", "true", "TRUE"}

def init_logging(level: str | int = "INFO"):
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    if logging.getLogger().handlers:
        return
    logging.basicConfig(level=level, format="%(message)s")

def _emit(level: str, event: str, **fields: Any):
    logger = logging.getLogger("moderation_bot")
    if _LOG_JSON:
        record = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "event": event}
        record.update(fields)
        logger.log(getattr(logging, level.upper(), logging.INFO), _json.dumps(record, ensure_ascii=False))
    else:
        extras = " ".join(f"{k}={v}" for k, v in fields.items())
        logger.log(getattr(logging, level.upper(), logging.INFO), f"{event} {extras}".strip())

def info(event: str, **fields: Any):
    _emit("INFO", event, **fields)

def warning(event: str, **fields: Any):
    _emit("WARNING", event, **fields)

def error(event: str, **fields: Any):
    _emit("ERROR", event, **fields)

def debug(event: str, **fields: Any):
    _emit("DEBUG", event, **fields)

__all__ = ["init_logging", "info", "warning", "error", "debug"]
