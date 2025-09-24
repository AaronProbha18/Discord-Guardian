from __future__ import annotations

import httpx
from .base import LLMError, LLMTimeoutError, _retry


class OllamaProvider:
    def __init__(self, model: str, host: str, timeout: float, max_retries: int, retry_base_delay: float):
        self.model = model
        self.base_url = host.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    async def _raw_complete(self, prompt: str) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.post(f"{self.base_url}/api/generate", json=payload)
            except httpx.TimeoutException as e:  
                raise LLMTimeoutError(str(e)) from e
            r.raise_for_status()
            data = r.json()
            return data.get("response") or data.get("output", "")

    async def complete(self, prompt: str) -> str:  # type: ignore[override]
        try:
            return await _retry(lambda: self._raw_complete(prompt), self.max_retries, self.retry_base_delay)
        except Exception as e:
            raise LLMError(f"ollama error: {e}") from e

__all__ = ['OllamaProvider']
