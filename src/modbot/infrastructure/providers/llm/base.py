"""Base LLM provider abstractions and retry helpers."""
from __future__ import annotations

import asyncio
import os
import random
from typing import Callable, Awaitable
import httpx


class LLMError(Exception):
    """Base normalized LLM exception."""


class LLMRateLimitError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


def _is_retryable(exc: Exception) -> bool:
    retryable_types = (httpx.TransportError, httpx.ReadTimeout, httpx.ConnectError)
    if isinstance(exc, retryable_types):
        return True
    msg = str(exc).lower()
    if "rate limit" in msg or "429" in msg:
        return True
    return False


async def _retry(fn: Callable[[], Awaitable], max_retries: int, base_delay: float):
    attempt = 0
    delay = base_delay
    while True:
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            if attempt > max_retries or not _is_retryable(exc):
                raise
            await asyncio.sleep(delay + random.random() * 0.25)
            delay *= 2


def require_env(var: str):  # small helper
    if not os.getenv(var):
        raise RuntimeError(f"{var} required for this provider")


__all__ = [
    'LLMError', 'LLMRateLimitError', 'LLMTimeoutError', '_retry', 'require_env'
]
