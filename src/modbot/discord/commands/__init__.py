"""Aggregate slash command registrations by importing individual command modules."""
from .mod_status import setup_mod_status
from .mod_rules import setup_mod_rules
from .mod_llm_ping import setup_mod_llm_ping
from .mod_history import setup_mod_history
from .mod_metrics import setup_mod_metrics
from .mod_config import setup_mod_config
from .appeal import setup_appeal
from .appeals_review import setup_appeals_review

ALL_SETUP_FUNCS = [
    setup_mod_status,
    setup_mod_rules,
    setup_mod_llm_ping,
    setup_mod_history,
    setup_mod_metrics,
    setup_mod_config,
    setup_appeal,
    setup_appeals_review,
]

def register_all_commands(bot):
    for f in ALL_SETUP_FUNCS:
        f(bot)
    return bot

__all__ = ["register_all_commands"]
