"""Application settings using Pydantic BaseSettings for validation & env loading.

Centralizes all environment parsing and adds validation rules:
 - DISCORD_TOKEN must be provided.
 - MODEL_PROVIDER normalized to lowercase and validated against allowed set.
 - Timeouts / retries coerced to positive ints.
"""
from __future__ import annotations

from typing import Optional, Literal
import os
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

_ALLOWED_MODEL_PROVIDERS = {"ollama", "openai", "anthropic", "gemini"}


class BotConfig(BaseSettings):
	# Discord
	discord_token: str = Field(..., env="DISCORD_TOKEN")
	test_guild_id: Optional[int] = Field(None, env="TEST_GUILD_ID")

	# LLM provider settings
	model_provider: str = Field("ollama", env="MODEL_PROVIDER")
	model_name: str = Field("llama3", env="MODEL_NAME")
	ollama_host: Optional[str] = Field(None, env="OLLAMA_HOST")
	llm_timeout_seconds: int = Field(25, env="LLM_TIMEOUT_SECONDS")
	llm_max_retries: int = Field(2, env="LLM_MAX_RETRIES")
	llm_retry_base_delay: float = Field(0.5, env="LLM_RETRY_BASE_DELAY")

	openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
	anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
	gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY")

	# Toxicity / external APIs
	perspective_api_key: Optional[str] = Field(None, env="PERSPECTIVE_API_KEY")
	detoxify_enabled: bool = Field(False, env="DETOXIFY_ENABLED")

	# Moderation & escalation
	mod_exempt_role_names: str = Field("mod,admin", env="MOD_EXEMPT_ROLE_NAMES")
	mod_alert_channel_name: Optional[str] = Field(None, env="MOD_ALERT_CHANNEL_NAME")
	mod_alert_role_name: Optional[str] = Field(None, env="MOD_ALERT_ROLE_NAME")

	# MCP
	mcp_server_url: Optional[str] = Field(None, env="MCP_SERVER_URL")

	# Misc
	log_json: bool = Field(False, env="LOG_JSON")

	class Config:
		case_sensitive = False
		env_file = ".env"
		env_file_encoding = "utf-8"
		protected_namespaces = ("settings_",)  # allow fields starting with model_

	@field_validator("model_provider", mode="before")
	def _normalize_provider(cls, v: str):  # noqa: D401
		return (v or "").lower()

	@field_validator("llm_timeout_seconds", "llm_max_retries", mode="before")
	def _coerce_positive(cls, v):
		try:
			iv = int(v)
		except Exception:
			iv = 0
		if iv < 0:
			iv = 0
		return iv

	@model_validator(mode="after")
	def _validate_all(self):  # noqa: D401
		if not self.discord_token:
			raise ValueError("DISCORD_TOKEN is required (empty or missing)")
		if self.model_provider not in _ALLOWED_MODEL_PROVIDERS:
			raise ValueError(
				f"MODEL_PROVIDER must be one of {_ALLOWED_MODEL_PROVIDERS}, got '{self.model_provider}'"
			)
		return self


def load_config() -> BotConfig:
	conf = BotConfig()  # type: ignore[call-arg]
	# Mirror API keys into real environment for provider libs that read os.environ directly.
	for var, value in (
		("OPENAI_API_KEY", conf.openai_api_key),
		("ANTHROPIC_API_KEY", conf.anthropic_api_key),
		("GEMINI_API_KEY", conf.gemini_api_key),
		("PERSPECTIVE_API_KEY", conf.perspective_api_key),
	):
		if value and not os.getenv(var):  # don't overwrite existing shell export
			os.environ[var] = value
	return conf


__all__ = ["BotConfig", "load_config"]
