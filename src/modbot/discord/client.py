"""ModerationBot Discord client definition moved from main.py."""
from __future__ import annotations

import logging
import discord
from discord import app_commands

from ..config.settings import load_config, BotConfig
from ..domain.policy.loader import load_policy
from ..infrastructure.providers.llm.factory import create_llm_provider as get_llm_provider  # type: ignore
from ..infrastructure.providers.toxicity.factory import create_toxicity_scorer  # type: ignore
from ..infrastructure.persistence.db_core import ActionDB

from ..infrastructure.logging.structured_logging import init_logging

# Ensure logging initialized
init_logging()
logger = logging.getLogger("moderation_bot")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

CONFIG: BotConfig = load_config()
if not CONFIG.discord_token:
    logger.error("DISCORD_TOKEN missing. Check your .env file.")
    raise SystemExit(1)

class ModerationBot(discord.Client):
    """Discord client wiring policies, providers, DB, and slash commands."""
    def __init__(self):
        super().__init__(intents=INTENTS)
        self.tree = app_commands.CommandTree(self)
        self.policy = self._load_policy()
        self.config = CONFIG
        # Provider initialization can fail if optional env vars / deps missing.
        # We degrade gracefully (e.g. for --dry-run) and validate in runtime launcher.
        self.llm = None
        try:  # LLM
            self.llm = get_llm_provider(self.config)
        except Exception as e:  # pragma: no cover - env / dependency issues
            logger.warning("LLM provider initialization failed: %s (continuing; may be dry-run)", e)

        self.toxicity_scorer = None
        try:
            self.toxicity_scorer = create_toxicity_scorer(self.config)
        except Exception as e:  # pragma: no cover
            logger.warning("Toxicity scorer initialization failed: %s (continuing; may be dry-run)", e)
        self.db = ActionDB()
        self.test_guild_id = str(self.config.test_guild_id) if self.config.test_guild_id else None
        roles_env = self.config.mod_exempt_role_names or "mod,admin"
        self.moderator_role_names = {r.strip().lower() for r in roles_env.split(',') if r.strip()}

    def is_moderator(self, member: discord.Member | None) -> bool:
        if member is None:
            return False
        try:
            guild_owner_id = getattr(member.guild, 'owner_id', None)
            if guild_owner_id and member.id == guild_owner_id:
                return True
        except AttributeError:
            pass
        member_role_names = {role.name.lower() for role in getattr(member, 'roles', [])}
        if not self.moderator_role_names.isdisjoint(member_role_names):
            return True
        try:
            if member.guild_permissions.manage_guild:  # type: ignore[attr-defined]
                return True
        except Exception:  # pragma: no cover
            pass
        return False

    def _load_policy(self):
        try:
            return load_policy()
        except Exception as e:  # pragma: no cover
            logger.error("Failed to load policy: %s", e)
            return None

    async def setup_hook(self) -> None:
        if self.test_guild_id:
            try:
                gid = int(self.test_guild_id)
                test_guild = discord.Object(id=gid)
                self.tree.copy_global_to(guild=test_guild)
                await self.tree.sync(guild=test_guild)
                logger.info("Slash commands synced to test guild %s (instant)", gid)
            except ValueError:
                logger.error("Invalid TEST_GUILD_ID: %s", self.test_guild_id)
        else:
            await self.tree.sync()
            logger.info("Global slash commands sync requested (may take up to 1 hour to propagate)")

bot = ModerationBot()

__all__ = ["ModerationBot", "bot"]
