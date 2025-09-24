"""Factory for constructing LLM provider based on configuration."""
from __future__ import annotations

import os
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .base import LLMError
from ....config.settings import BotConfig


def create_llm_provider(conf: BotConfig):
    provider = (conf.model_provider or 'ollama').lower()
    model = conf.model_name
    timeout = float(conf.llm_timeout_seconds)
    max_retries = int(conf.llm_max_retries)
    retry_base_delay = float(os.getenv('LLM_RETRY_BASE_DELAY', '0.5'))
    if provider == 'openai':
        return OpenAIProvider(model, timeout, max_retries, retry_base_delay)
    if provider == 'anthropic':
        return AnthropicProvider(model, timeout, max_retries, retry_base_delay)
    if provider == 'gemini':
        try:  
            from .gemini import GeminiProvider  # type: ignore
        except Exception as e:  # import error or missing dependency
            raise RuntimeError(f"Gemini provider unavailable: {e}") from e
        return GeminiProvider(model, timeout, max_retries, retry_base_delay)
    # default ollama
    host = conf.ollama_host or os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    return OllamaProvider(model, host, timeout, max_retries, retry_base_delay)

__all__ = ['create_llm_provider', 'LLMError']
