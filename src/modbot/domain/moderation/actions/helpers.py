"""Shared helper functions for moderation actions.

Copied (with minimal modification) from the legacy monolithic actions module.
Further refactors will relocate cross-cutting concerns (logging, utils).
"""
from __future__ import annotations

import json
import time
import re
from datetime import timedelta
from typing import Optional
import discord

try:  # legacy logging utils location (will be refactored later)
    from modbot.infrastructure.logging.structured_logging import info as log_info, warning as log_warning, error as log_error, debug as log_debug
except Exception:  
    def log_info(*a, **kw): pass
    def log_warning(*a, **kw): pass
    def log_error(*a, **kw): pass
    def log_debug(*a, **kw): pass

try:
    from modbot.utils.channel_utils import resolve_escalation_target, find_text_channel
except Exception:  
    def resolve_escalation_target(*a, **kw): return (None, "")
    def find_text_channel(*a, **kw): return None

_RE_DECISION = re.compile(r"\b(warn|ignore|escalate|delete)\b", re.I)


async def action_delete_message(message: discord.Message, reason: str):
    try:
        await message.delete()
        log_info("action.delete_message", message_id=message.id, reason=reason)
    except discord.NotFound:
        log_warning("action.delete_message.already_deleted", message_id=message.id)
    except discord.Forbidden:
        log_error("action.delete_message.forbidden", message_id=message.id)
    except Exception as e:  # noqa: BLE001
        log_error("action.delete_message.error", message_id=message.id, error=str(e))


async def action_warn_user(message: discord.Message, reason: str, escalation_ctx=None):
    user = message.author
    guild = message.guild
    excerpt = message.content[:240]
    warn_number = None
    next_threshold_text = ""
    appeals_text = ""
    window_mins = None
    if escalation_ctx and getattr(escalation_ctx.bot.policy, 'escalation', None):
        window_mins = escalation_ctx.window_minutes
        try:
            pre = escalation_ctx.bot.db.count_recent(user.id, 'warn_user', escalation_ctx.window_minutes)
            warn_number = pre + 1
            thresholds = escalation_ctx.bot.policy.escalation.parsed.get('warn_user', [])
            nxt = None
            for cnt, follow in thresholds:
                if cnt > warn_number:
                    nxt = (cnt, follow)
                    break
            if nxt:
                next_threshold_text = f"Next action at warning #{nxt[0]}: {nxt[1]}"
        except Exception as e:  
            log_debug("action.warn.count_failed", error=str(e))
        appeals_conf = getattr(escalation_ctx.bot.policy, 'appeals', None)
        if appeals_conf and guild:
            ch = find_text_channel(guild, getattr(appeals_conf, 'channel', None))
            if ch:
                appeals_text = f"Appeal in #{ch.name} if you believe this is in error."
    header = f"You received a moderation warning in '{getattr(guild, 'name', '?')}'." if guild else "You received a moderation warning."
    lines = [header, f"Reason: {reason}"]
    if warn_number is not None and window_mins is not None:
        lines.append(f"This is warning #{warn_number} in the last {window_mins} minutes.")
    if next_threshold_text:
        lines.append(next_threshold_text)
    if appeals_text:
        lines.append(appeals_text)
    lines.append(f"Excerpt: {excerpt}")
    dm_text = "\n".join(lines)
    try:
        await user.send(dm_text)
        log_info("action.warn_user.dm_sent", user_id=user.id, warn_number=warn_number)
    except Exception:
        log_warning("action.warn_user.dm_failed", user_id=user.id)
        try:
            await message.channel.send(f"{user.mention} this message violated server rules. ({reason})")
        except Exception as e:  # noqa: BLE001
            log_error("action.warn_user.channel_notify_failed", user_id=user.id, error=str(e))


async def action_timeout_member(message: discord.Message, minutes: int, reason: str) -> bool:
    member: discord.Member = message.author  # type: ignore
    guild = message.guild
    bot_member = getattr(guild, 'me', None) if guild else None
    protected_ids = {getattr(guild, 'owner_id', None), getattr(bot_member, 'id', None)}
    if member.id in protected_ids:
        log_info(
            "action.timeout.skip_protected",
            user_id=member.id,
            owner_id=getattr(guild, 'owner_id', None),
            bot_id=getattr(bot_member, 'id', None),
        )
        return False
    try:
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        used_api = None
        if hasattr(member, 'timeout') and callable(getattr(member, 'timeout')):
            await member.timeout(until, reason=reason)  # type: ignore[attr-defined]
            used_api = 'member.timeout()'
        else:
            await member.edit(communication_disabled_until=until, reason=reason)
            used_api = 'member.edit(communication_disabled_until=...)'
        log_info(
            "action.timeout.success",
            user_id=member.id,
            minutes=minutes,
            until=until.isoformat(),
            api=used_api,
        )
        return True
    except discord.Forbidden:
        log_error("action.timeout.forbidden", user_id=member.id)
    except AttributeError:
        log_error("action.timeout.unsupported", user_id=member.id)
    except Exception as e:  # noqa: BLE001
        log_error("action.timeout.error", user_id=member.id, error=str(e))
    return False


async def action_escalate(message: discord.Message, label: str, reason: str, escalation_ctx=None) -> bool:
    guild = message.guild
    if not guild:
        log_warning("action.escalate.no_guild")
        return False
    cfg = getattr(getattr(escalation_ctx, 'bot', None), 'config', None) if escalation_ctx else None
    channel, role_mention = resolve_escalation_target(guild, cfg, fallback_channel="appeals")
    if channel is None:
        log_error("action.escalate.no_channel")
        return False
    author = message.author
    snippet = message.content[:180]
    try:
        await channel.send(f"{role_mention}[ESCALATION:{label}] user={author} (id={author.id}) | {reason} | excerpt=\"{snippet}\"")
        log_info("action.escalate.sent", label=label, user_id=author.id, channel_id=getattr(channel, 'id', None))
        return True
    except Exception as e:  # noqa: BLE001
        log_error("action.escalate.error", label=label, user_id=author.id, error=str(e))
        return False


def _build_ask_llm_prompt(message: discord.Message, toxicity: float) -> str:
    policy_brief = (
        "Borderline moderation decision. Decide if the message should receive a warning, be escalated, or ignored.\n"
        "Return STRICT JSON: { 'decision': 'warn|ignore|escalate|delete', 'reason': 'brief rationale', 'confidence': 0.0-1.0 }\n"
    )
    return (
        f"{policy_brief}ToxicityScore: {toxicity:.2f}\nMessage: "
        + json.dumps(message.content)
        + "\nIf it clearly violates severe rules suggest 'escalate' only if human review is needed. Use 'warn' for mild breach; 'ignore' if compliant."
    )


def _parse_llm_decision(raw: str) -> Optional[str]:
    try:
        j = json.loads(raw)
        d = j.get('decision')
        if isinstance(d, str):
            d = d.lower().strip()
            if d in {'warn', 'ignore', 'escalate', 'delete'}:
                return d
    except Exception:
        pass
    m = _RE_DECISION.search(raw.lower())
    if m:
        return m.group(1)
    return None


async def action_ask_llm(message: discord.Message, toxicity: float, escalation_ctx=None) -> bool:
    bot = getattr(escalation_ctx, 'bot', None)
    if not bot:
        return False

    mcp_url = getattr(bot.config, 'mcp_server_url', None)
    if not mcp_url:
        # Fallback to old logic if MCP is not configured
        return await _legacy_action_ask_llm(message, toxicity, escalation_ctx)

    from ....infrastructure.mcp_client import MCPClient
    mcp_client = MCPClient(mcp_url)

    started = time.perf_counter()
    try:
        tools = await mcp_client.get_tools()
        if not tools:
            # if tools fetch failed, fallback
            return await _legacy_action_ask_llm(message, toxicity, escalation_ctx)

        # Build MCP-style messages (chat-style)
        user_prompt = _build_mcp_prompt(message, toxicity)
        messages = [
            {"role": "system", "content": "You are a moderation assistant. Use the provided tools when appropriate."},
            {"role": "user", "content": user_prompt},
        ]

        payload = {"context": {"messages": messages}, "tools": {"tools": tools.get("tools", [])}}
        # Be tolerant of different MCPClient.process signatures:
        tools_list = tools.get("tools", []) if isinstance(tools, dict) else (tools or [])
        try:
            # Most implementations expect two positional args: (messages, tools)
            mcp_response = await mcp_client.process(messages, tools_list)
        except TypeError:
            # Fallback: some clients expect a single payload dict
            try:
                mcp_response = await mcp_client.process(payload)
            except Exception as e:
                log_error('action.ask_llm.mcp_error', error=f"mcp client call failed: {e}")
                return await _legacy_action_ask_llm(message, toxicity, escalation_ctx)

        latency_ms = int((time.perf_counter() - started) * 1000)

        tool_calls_raw = (mcp_response or {}).get("tool_calls", [])
        tool_calls = _normalize_tool_calls(tool_calls_raw)

        evidence = {
            'message_id': message.id,
            'excerpt': message.content[:200],
            'toxicity': round(toxicity, 4),
            'mcp_response': mcp_response,
            'latency_ms': latency_ms,
        }
        if escalation_ctx:
            escalation_ctx.bot.db.log_action(
                getattr(message.guild, 'id', None),
                getattr(message.channel, 'id', None),
                getattr(bot.user, 'id', None),
                'ask_llm_mcp',
                message.author.id,
                f"toxicity={toxicity:.2f}",
                evidence=evidence,
            )

        for call in tool_calls:
            # tolerate different key names
            if isinstance(call, str):
                call = {"name": call, "arguments": {}}
            tool_name = call.get("name")
            tool_args = call.get("arguments", {}) or {}

            if tool_name == "delete_message":
                await action_delete_message(message, tool_args.get("reason", "MCP Decision"))
                if escalation_ctx:
                    escalation_ctx.record('delete_message', message.author.id)
            elif tool_name == "warn_user":
                await action_warn_user(message, tool_args.get("reason", "MCP Decision"), escalation_ctx)
                if escalation_ctx:
                    escalation_ctx.record('warn_user', message.author.id)
            elif tool_name == "timeout_member":
                # tolerate both "minutes" and "duration_minutes"
                minutes = tool_args.get("minutes", tool_args.get("duration_minutes", 30))
                await action_timeout_member(message, int(minutes), tool_args.get("reason", "MCP Decision"))
                if escalation_ctx:
                    escalation_ctx.record(f'timeout_member({minutes})', message.author.id)
            elif tool_name == "ignore":
                # nothing to do
                pass
            elif tool_name == "escalate":
                label = tool_args.get("label", "human_mods")
                reason = tool_args.get("reason", f"toxicity={toxicity:.2f}")
                await action_escalate(message, label, reason, escalation_ctx)
                if escalation_ctx:
                    escalation_ctx.record(f'escalate({label})', message.author.id)

        return True

    except Exception as e:
        log_error('action.ask_llm.mcp_error', error=str(e))
        # fallback to legacy path if something goes wrong
        try:
            return await _legacy_action_ask_llm(message, toxicity, escalation_ctx)
        except Exception:
            return False


def _normalize_tool_calls(raw):
    """
    Normalize various possible tool_calls representations into a list of
    {"name": str, "arguments": dict} dicts.
    """
    normalized = []
    if not raw:
        return normalized
    # if a single dict with tool_calls key
    if isinstance(raw, dict) and "tool_calls" in raw:
        raw = raw["tool_calls"]
    # list expected
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "name" in item:
                args = item.get("arguments") or item.get("args") or {}
                normalized.append({"name": item["name"], "arguments": args})
            elif isinstance(item, str):
                # try parse JSON string
                try:
                    j = json.loads(item)
                    if isinstance(j, dict) and "name" in j:
                        args = j.get("arguments") or j.get("args") or {}
                        normalized.append({"name": j["name"], "arguments": args})
                        continue
                except Exception:
                    pass
                # heuristic: map keyword to tool
                low = item.lower()
                if "warn" in low:
                    normalized.append({"name": "warn_user", "arguments": {}})
                elif "delete" in low:
                    normalized.append({"name": "delete_message", "arguments": {}})
                elif "timeout" in low:
                    normalized.append({"name": "timeout_member", "arguments": {"minutes": 30}})
                elif "ignore" in low:
                    normalized.append({"name": "ignore", "arguments": {}})
            else:
                # last resort stringify and attempt JSON parse
                try:
                    s = json.dumps(item)
                    j = json.loads(s)
                    if isinstance(j, dict) and "name" in j:
                        normalized.append({"name": j["name"], "arguments": j.get("arguments", {})})
                except Exception:
                    continue
    else:
        # single dict mapping to a decision
        if isinstance(raw, dict):
            dec = raw.get("decision") or raw.get("action")
            if dec:
                dec = dec.lower()
                if dec == "warn":
                    normalized.append({"name": "warn_user", "arguments": {"reason": raw.get("reason", "")}})
                elif dec == "delete":
                    normalized.append({"name": "delete_message", "arguments": {"reason": raw.get("reason", "")}})
                elif dec == "ignore":
                    normalized.append({"name": "ignore", "arguments": {}})
    return normalized


def _build_mcp_prompt(message: discord.Message, toxicity: float) -> str:
    # Keep prompt concise; MCP server expects chat messages, so content only here
    return (
        "A Discord message has been flagged as borderline. Decide which moderation tool(s) to call. "
        "Return a JSON array of tool-calls, each: {\"name\": \"<tool_name>\", \"arguments\": {...}}.\n\n"
        f"ToxicityScore: {toxicity:.2f}\nMessage:\n{message.content}\n\n"
        "Tools available: delete_message, warn_user(reason), timeout_member(duration_minutes, reason), ignore, escalate(label, reason)."
    )


async def _legacy_action_ask_llm(message: discord.Message, toxicity: float, escalation_ctx=None) -> bool:
    provider = getattr(getattr(escalation_ctx, 'bot', None), 'llm', None) if escalation_ctx else None
    decision = None
    raw = ''
    started = time.perf_counter()
    try:
        if not provider:
            raise RuntimeError('LLM provider unavailable')
        prompt = _build_ask_llm_prompt(message, toxicity)
        raw = await provider.complete(prompt)
        decision = _parse_llm_decision(raw)
    except Exception as e:  # noqa: BLE001
        log_error('action.ask_llm.error', error=str(e))
    latency_ms = int((time.perf_counter() - started) * 1000)
    evidence = {
        'message_id': message.id,
        'excerpt': message.content[:200],
        'toxicity': round(toxicity, 4),
        'llm_raw': raw[:800],
        'decision': decision or 'none',
        'latency_ms': latency_ms,
    }
    if escalation_ctx:
        escalation_ctx.bot.db.log_action(
            getattr(message.guild, 'id', None),
            getattr(message.channel, 'id', None),
            getattr(escalation_ctx.bot.user, 'id', None) if getattr(escalation_ctx.bot, 'user', None) else None,
            'ask_llm_decision',
            message.author.id,
            f"decision={decision or 'none'} toxicity={toxicity:.2f}",
            evidence=evidence,
        )
    if decision == 'warn':
        await action_warn_user(message, f"toxicity={toxicity:.2f} (ask_llm)", escalation_ctx=escalation_ctx)
        if escalation_ctx:
            escalation_ctx.record('warn_user', message.author.id)
    elif decision == 'escalate':
        esc_ok = await action_escalate(message, 'human_mods', f"toxicity={toxicity:.2f} (ask_llm)", escalation_ctx)
        if esc_ok and escalation_ctx:
            escalation_ctx.record('escalate(human_mods)', message.author.id)
    elif decision == 'delete':
        await action_delete_message(message, f"toxicity={toxicity:.2f} (ask_llm)")
    return True

__all__ = [
    'action_delete_message', 'action_warn_user', 'action_timeout_member', 'action_escalate', 'action_ask_llm', '_legacy_action_ask_llm'
]
