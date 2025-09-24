from __future__ import annotations

import asyncio
from .base import LLMError, LLMRateLimitError, LLMTimeoutError, _retry, require_env


class GeminiProvider:
    def __init__(self, model: str, timeout: float, max_retries: int, retry_base_delay: float):
        import google.generativeai as genai  # type: ignore
        require_env('GEMINI_API_KEY')
        genai.configure(api_key=None)  # uses env variable
        self.model = genai.GenerativeModel(model)
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    async def _raw_complete(self, prompt: str) -> str:
        loop = asyncio.get_running_loop()

        def _call():
            try:
                resp = self.model.generate_content(prompt)
                return getattr(resp, "text", "") or ""
            except Exception as e:  
                msg = str(e).lower()
                if "rate limit" in msg or "429" in msg:
                    raise LLMRateLimitError(str(e)) from e
                raise

        try:
            return await asyncio.wait_for(loop.run_in_executor(None, _call), timeout=self.timeout)
        except asyncio.TimeoutError as e:
            raise LLMTimeoutError(str(e)) from e

    async def complete(self, prompt: str) -> str:  # type: ignore[override]
        try:
            return await _retry(lambda: self._raw_complete(prompt), self.max_retries, self.retry_base_delay)
        except (LLMTimeoutError, LLMRateLimitError):
            raise
        except Exception as e:
            raise LLMError(f"gemini error: {e}") from e

__all__ = ['GeminiProvider']
