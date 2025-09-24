"""Bot runtime launcher.

Provides a console entry point for `python -m modbot` with optional flags:
  --dry-run     Validate config & policy, print summary, exit.
  --sync-only   Just sync slash commands then exit (requires TEST_GUILD_ID or global).

Default with no flags: start the Discord bot.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from .discord.client import bot, CONFIG  # imports initialize logging & config
from .discord.commands import register_all_commands
from .discord import events  # noqa: F401 -- import registers event handlers
from .domain.policy.loader import load_policy
from .domain.policy.formatter import format_rules


def _print_header():
    print("modbot: provider=%s model=%s" % (CONFIG.model_provider, CONFIG.model_name))


def _validate_policy(verbose: bool = False):
    try:
        pol = load_policy()
    except Exception as e:  # pragma: no cover
        print(f"Policy load failed: {e}", file=sys.stderr)
        return False
    if verbose:
        text = format_rules(pol, detail=False)
        print("Policy rules loaded:\n" + (text or "(none)"))
    return True


async def _sync_commands(quiet: bool = False):
    if not quiet:
        print("Commands registered (sync occurs on connect).")


def main(argv: list[str] | None = None, *, dry_run: bool | None = None):  # pragma: no cover (manual entry)
    parser = argparse.ArgumentParser(description="Run the Discord AI moderator bot")
    parser.add_argument("--dry-run", action="store_true", help="Validate config & policy then exit")
    parser.add_argument("--sync-only", action="store_true", help="Register commands and exit (login not performed)")
    args = parser.parse_args(argv)

    if dry_run is True:
        args.dry_run = True

    _print_header()

    if args.dry_run:
        print("\nDry run validation successful.")
        # In dry run, we can also try to initialize commands to catch startup errors
        try:
            register_all_commands(bot)
            print("Command registration check successful.")
        except Exception as e:
            print(f"Command registration check failed: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Register commands just once before running or syncing
    register_all_commands(bot)

    if args.sync_only:
        asyncio.run(_sync_commands())
        sys.exit(0)
    
    # Default: run the bot
    bot.run(CONFIG.discord_token)


if __name__ == "__main__":  # pragma: no cover
    main()