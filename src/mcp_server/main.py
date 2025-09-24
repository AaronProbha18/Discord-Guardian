"""
MCP Tool Server for the Discord Moderator Bot (FastMCP-based).
Run:
  uv run python -m mcp_server.main
"""
from fastmcp import FastMCP
import inspect
from typing import Any, Callable
import asyncio
import json
import re
import time

from modbot.config.settings import load_config
from modbot.infrastructure.providers.llm.factory import create_llm_provider as get_llm_provider  # same pattern as bot client

CONFIG = load_config()


def init_llm():
    llm = None
    try:
        llm = get_llm_provider(CONFIG)
        print(f"MCP Server: LLM provider '{getattr(CONFIG, 'model_provider', 'unknown')}' initialized.")
    except Exception as e:
        print(f"MCP Server: LLM provider initialization failed (continuing): {e}")
    return llm


llm_provider = init_llm()


# --------------------------------------------------
# Tool registry (for /mcp/tools endpoint contract)
# --------------------------------------------------
TOOLS_REGISTRY: list[dict] = []


def _python_type_to_json(t: Any) -> str:
    if t in (int, "int"): return "integer"
    if t in (float, "float"): return "number"
    if t in (bool, "bool"): return "boolean"
    return "string"


def register_tool(func: Callable):
    """
    Capture a simplified JSON schema for the tool's parameters
    before FastMCP wraps it.
    """
    # If already a wrapped object (should not happen now, but defensive):
    original = getattr(func, "__wrapped__", None)
    if original and callable(original):
        func = original  # unwrap

    if any(entry["name"] == func.__name__ for entry in TOOLS_REGISTRY):
        return func  # avoid duplicate

    sig = inspect.signature(func)
    properties = {}
    required = []
    for name, param in sig.parameters.items():
        ann = param.annotation if param.annotation is not inspect._empty else str
        properties[name] = {"type": _python_type_to_json(ann)}
        if param.default is inspect._empty:
            required.append(name)

    TOOLS_REGISTRY.append(
        {
            "name": func.__name__,
            "description": (func.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
    )
    return func


# --------------------------------------------------
# Helper: call provider and normalize response
# --------------------------------------------------
async def _call_provider_and_extract_tool_calls(provider, messages, tools):
    """
    Calls the provider using the most likely method names and extracts a list of tool calls.
    Returns list of tool call dicts (or empty list on failure).
    """
    # Normalize messages into a prompt / chat structure
    prompt = None
    chat_messages = None
    if isinstance(messages, list) and len(messages) == 1 and isinstance(messages[0], str):
        prompt = messages[0]
    elif isinstance(messages, list) and all(isinstance(m, dict) for m in messages):
        chat_messages = messages
    else:
        # join strings or stringify entries
        prompt = "\n".join(str(m) for m in messages)

    # Try provider method variants in priority order
    call_attempts = []
    result = None

    async def _maybe_await(val):
        if asyncio.iscoroutine(val) or asyncio.isfuture(val):
            return await val
        return val

    try:
        if hasattr(provider, "complete"):
            # provider.complete(prompt) -> often returns string or object
            call_attempts.append("complete")
            result = await _maybe_await(provider.complete(prompt if prompt is not None else json.dumps(chat_messages)))
        elif hasattr(provider, "generate"):
            call_attempts.append("generate")
            result = await _maybe_await(provider.generate(messages=chat_messages or [{"role":"user","content":prompt}], tools=tools))
        elif hasattr(provider, "get_response"):
            call_attempts.append("get_response")
            result = await _maybe_await(provider.get_response(messages=chat_messages or [{"role":"user","content":prompt}], tools=tools))
        elif hasattr(provider, "create"):
            call_attempts.append("create")
            # Some providers expect {"messages": ...} or content
            result = await _maybe_await(provider.create(messages=chat_messages or [{"role":"user","content":prompt}]))
        else:
            # Fallback: try calling provider directly if callable
            if callable(provider):
                call_attempts.append("callable")
                result = await _maybe_await(provider(prompt))
            else:
                print("MCP Server: No known call method on provider.")
                return []
    except Exception as e:
        print(f"MCP Server: provider call failed (methods tried={call_attempts}): {e}")
        return []

    # Inspect result to find textual output
    raw_text = None
    if isinstance(result, dict):
        # Common shapes: {'tool_calls': [...]}, {'choices': [{'text': '...'}]}, {'output': '...'}
        if "tool_calls" in result:
            return result.get("tool_calls", []) or []
        if "toolCalls" in result:
            return result.get("toolCalls", []) or []
        # choices -> try to extract first text
        choices = result.get("choices") or result.get("outputs") or result.get("items")
        if choices and isinstance(choices, (list, tuple)) and len(choices) > 0:
            first = choices[0]
            if isinstance(first, dict):
                raw_text = first.get("text") or first.get("content") or first.get("message") or json.dumps(first)
            else:
                raw_text = str(first)
        else:
            # maybe result contains 'text' or 'content'
            raw_text = result.get("text") or result.get("content") or None

    elif hasattr(result, "text"):
        raw_text = getattr(result, "text")
    elif isinstance(result, str):
        raw_text = result
    else:
        # try to stringify
        try:
            raw_text = json.dumps(result)
        except Exception:
            raw_text = str(result)

    if not raw_text:
        print("MCP Server: provider returned no text to parse for tool calls.")
        return []

    # Try to parse JSON from raw_text
    raw_text_str = raw_text.strip()
    # If wrapper like "```json\n{...}\n```", try to strip code fences
    if raw_text_str.startswith("```") and "```" in raw_text_str[3:]:
        # split fenced blocks and try to find JSON inside, tolerant of a language id like "json\n"
        parts = raw_text_str.split("```")
        for part in parts:
            s = part.strip()
            if not s:
                continue
            # If the part begins with a language tag followed by a newline, drop the first line.
            if "\n" in s:
                _, rest = s.split("\n", 1)
                candidate = rest.strip()
            else:
                candidate = s
            if candidate.startswith("{") or candidate.startswith("["):
                raw_text_str = candidate
                break
            # fallback: extract the first JSON object/array inside the part
            m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", s)
            if m:
                raw_text_str = m.group(1)
                break

    try:
        parsed = json.loads(raw_text_str)
        # parsed could be dict with 'tool_calls' or a list directly
        if isinstance(parsed, dict) and "tool_calls" in parsed:
            return parsed.get("tool_calls", []) or []
        if isinstance(parsed, list):
            return parsed
        # If dict but not tool_calls, try to convert expected shape
        # e.g., {'decision': 'warn', 'reason': '...', ...} -> map to tool calls
        if isinstance(parsed, dict):
            # attempt mapping: decision -> tool call
            decision = parsed.get("decision")
            if decision:
                decision = decision.lower()
                if decision == "warn":
                    return [{"name": "warn_user", "arguments": {"reason": parsed.get("reason", "MCP decision")}}]
                if decision == "delete":
                    return [{"name": "delete_message", "arguments": {"reason": parsed.get("reason", "MCP decision")}}]
                if decision == "ignore":
                    return [{"name": "ignore", "arguments": {}}]
                if decision == "escalate":
                    return [{"name": "ignore", "arguments": {}}]  # fallback; bot may escalate separately
    except Exception:
        # not JSON — fall through to heuristic parsing
        pass

    # Heuristic: look for a JSON object inside the text
    m = re.search(r"(\{[\s\S]*\})", raw_text_str)
    if m:
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, dict) and "tool_calls" in parsed:
                return parsed.get("tool_calls", []) or []
        except Exception:
            pass

    # Last resort: no structured tool calls found
    print("MCP Server: unable to extract tool_calls from provider response. Raw snippet:", raw_text_str[:400])
    return []


# --------------------------------------------------
# MCP Server subclass
# --------------------------------------------------
class ModeratorMCP(FastMCP):
    def __init__(self, title: str, llm_provider):
        super().__init__(title)
        self.llm = llm_provider

    async def process(self, request: dict) -> dict:
        """
        Expected request:
        {
          "context": {"messages": [...]},
          "tools": {"tools": [...]}
        }
        But accept also a bare list (treat as messages).
        Returns:
          {"tool_calls": [...]}
        """
        if not self.llm:
            return {"tool_calls": [], "error": "LLM provider not initialized"}
        try:
            # Normalize incoming payload: accept dict or list
            if isinstance(request, list):
                messages = request
                tools = []
            elif isinstance(request, dict):
                ctx = request.get("context", {})
                tools_block = request.get("tools", {})
                # support both dict and list shapes
                messages = ctx.get("messages", []) if isinstance(ctx, dict) else ctx or []
                tools = tools_block.get("tools", []) if isinstance(tools_block, dict) else tools_block or []
            else:
                messages = []
                tools = []

            # Debug log to help trace bad payloads
            print(f"MCP Server: processing request type={type(request).__name__} messages={len(messages) if hasattr(messages,'__len__') else 'unknown'} tools={len(tools) if hasattr(tools,'__len__') else 'unknown'}")

            tool_calls = await _call_provider_and_extract_tool_calls(self.llm, messages, tools)
            return {"tool_calls": tool_calls}
        except Exception as e:
            print(f"MCP Server: LLM call failed: {e}")
            return {"tool_calls": []}


app = ModeratorMCP("Discord Guardian MCP Server", llm_provider=llm_provider)


# --------------------------------------------------
# Tool definitions
# Decorator order: register_tool FIRST, then app.tool()
# --------------------------------------------------
@app.tool()
@register_tool
def delete_message():
    """Deletes the offending message."""
    return "Message deleted."


@app.tool()
@register_tool
def warn_user(reason: str):
    """Warns the user with a reason."""
    return f"User warned: {reason}"


@app.tool()
@register_tool
def timeout_member(duration_minutes: int, reason: str):
    """Timeouts the user."""
    return f"User timed out {duration_minutes}m. Reason: {reason}"


@app.tool()
@register_tool
def ignore():
    """No action taken."""
    return "Ignored."


# --------------------------------------------------
# Explicit endpoints matching bot expectations
# We run a standalone FastAPI app and delegate processing to the MCP instance.
# --------------------------------------------------
from fastapi import FastAPI, Request
import traceback

http_app = FastAPI()

@http_app.get("/mcp/tools")
async def list_tools():
    return {"tools": TOOLS_REGISTRY}


@http_app.post("/mcp")
async def mcp_dispatch(request: Request):
    """
    Read the raw body (JSON or other), log a preview, delegate to app.process,
    and always return a well-formed response. On exceptions print traceback
    and return an empty tool_calls list so the bot can continue.
    """
    try:
        # attempt to parse JSON body; fall back to raw bytes
        try:
            payload = await request.json()
        except Exception:
            raw = await request.body()
            try:
                payload = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                payload = raw.decode("utf-8", errors="replace")

        # Helpful debug logging
        preview = str(payload)[:1000]
        print(f"MCP Server: /mcp received payload type={type(payload).__name__} preview={preview!r}")

        resp = await app.process(payload)

        # Normalize unexpected shapes from process
        if not isinstance(resp, dict):
            print("MCP Server: app.process returned non-dict response:", resp)
            return {"tool_calls": []}
        if "tool_calls" not in resp:
            print("MCP Server: app.process missing 'tool_calls' key; returning safe default. resp:", resp)
            return {"tool_calls": []}
        return resp

    except Exception as e:
        # Print full traceback for debugging
        print("MCP Server: /mcp dispatch exception:", str(e))
        traceback.print_exc()
        # Return safe default to caller to avoid client-side failures
        return {"tool_calls": []}


# server start timestamp for health checks
START_TIME = time.time()

# health endpoint
@http_app.get("/health")
async def health():
    """
    Basic health/status endpoint for the MCP server.
    Returns LLM provider status, registered tool count and uptime.
    """
    uptime_seconds = int(time.time() - START_TIME)
    return {
        "status": "ok",
        "llm_provider": getattr(CONFIG, "model_provider", None),
        "llm_initialized": bool(llm_provider),
        "tools_registered": len(TOOLS_REGISTRY),
        "uptime_seconds": uptime_seconds,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(http_app, host="0.0.0.0", port=8000)