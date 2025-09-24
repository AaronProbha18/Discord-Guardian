from __future__ import annotations

from .base import LLMError, LLMRateLimitError, _retry, require_env


class OpenAIProvider:
    def __init__(self, model: str, timeout: float, max_retries: int, retry_base_delay: float):
        from openai import AsyncOpenAI  # type: ignore
        require_env('OPENAI_API_KEY')
        self.client = AsyncOpenAI()
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    async def _raw_complete(self, prompt: str) -> str:
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=400,
                timeout=self.timeout,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:  
            msg = str(e).lower()
            if "rate limit" in msg or "429" in msg:
                raise LLMRateLimitError(str(e)) from e
            raise

    async def complete(self, prompt: str) -> str:  # type: ignore[override]
        try:
            return await _retry(lambda: self._raw_complete(prompt), self.max_retries, self.retry_base_delay)
        except LLMRateLimitError:
            raise
        except Exception as e:
            raise LLMError(f"openai error: {e}") from e

__all__ = ['OpenAIProvider']
