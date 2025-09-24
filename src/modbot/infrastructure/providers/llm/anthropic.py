from __future__ import annotations

from .base import LLMError, LLMRateLimitError, _retry, require_env


class AnthropicProvider:
    def __init__(self, model: str, timeout: float, max_retries: int, retry_base_delay: float):
        import anthropic  # type: ignore
        require_env('ANTHROPIC_API_KEY')
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    async def _raw_complete(self, prompt: str) -> str:
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=400,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:  
            msg = str(e).lower()
            if "rate limit" in msg or "429" in msg:
                raise LLMRateLimitError(str(e)) from e
            raise
        parts = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
        return "\n".join(parts)

    async def complete(self, prompt: str) -> str:  # type: ignore[override]
        try:
            return await _retry(lambda: self._raw_complete(prompt), self.max_retries, self.retry_base_delay)
        except LLMRateLimitError:
            raise
        except Exception as e:
            raise LLMError(f"anthropic error: {e}") from e

__all__ = ['AnthropicProvider']
