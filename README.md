# Discord Guardian (MCP Enabled)

This project provides a powerful, two-stage Discord moderation system designed to be both fast and intelligent. It uses a combination of a local pre-filter for instant action and a Large Language Model (LLM) for nuanced decision-making on borderline content, all orchestrated via the Model Context Protocol (MCP). MCP exposes moderation actions as structured tools, ensuring that LLMs can only perform approved, auditable actions through a constrained and observable interface.

## How It Works

The moderation logic follows a precise, policy-driven flow:

1.  **Message Interception**: The bot listens to every message in the channels it can access.
2.  **Toxicity Scoring**: Each message is scored for toxicity using a cascading provider system. It first tries the Perspective API (if a key is provided), falls back to a local `detoxify` model, and finally to a neutral score if neither is available.
3.  **Policy Evaluation**: The message's toxicity score is checked against the rules defined in `policies/moderation.yaml`.
4.  **Action Dispatching**: Based on the matched rule, one or more actions are triggered:
    *   **Immediate Action**: For clear violations (e.g., "Very High Toxicity"), the bot acts immediately by deleting the message and warning the user.
    *   **LLM Adjudication**: For "Borderline" content, the `ask_llm` action is triggered. The bot sends the message content to the MCP server, which uses an LLM (like Gemini or an Ollama model) to decide the best course of action from a list of available tools (`warn_user`, `delete_message`, `timeout_member`, or `ignore`).
5.  **Escalation Engine**: The bot tracks all moderation actions in a local SQLite database. If a user repeatedly violates rules within a configured time window (e.g., receives 2 warnings in 60 minutes), the escalation engine automatically applies a more severe action, like a timeout.
6.  **Audit Trail**: Every action taken by the bot is logged, providing a clear and auditable history of moderation events.

## Features

*   **Policy-Driven Logic**: Define all moderation rules in a simple `policies/moderation.yaml` file. No code changes needed to adjust thresholds.
*   **Two-Stage Moderation**: Combines a fast, local toxicity filter with intelligent, LLM-based adjudication for nuanced cases.
*   **Model Context Protocol (MCP)**: Exposes moderation actions as "tools" that an LLM can call using `FastMCP`, ensuring the LLM can only perform approved, structured actions.
*   **Automatic Escalations**: Automatically times out or escalates users who are repeatedly warned.
*   **Multi-Provider LLM Support**: Works with Ollama (for local models), OpenAI, Anthropic, and Gemini.
*   **Slash Commands**: Provides commands for checking bot status, reviewing moderation history, managing appeals, and more.
*   **Role Exemptions**: Easily exempt moderators or other trusted roles from moderation actions.
*   **Structured Logging**: All logs are structured (JSON format available) for easy parsing and monitoring.
*   **Local-First Development**: Can be fully run and tested locally without relying on external services.

## Project Structure

*   `src/modbot/`: The main bot application, containing all core logic.
    *   `domain/`: Business logic, models, and interfaces.
    *   `infrastructure/`: Database, LLM providers, and other external services.
    *   `discord/`: Discord-specific code, including commands and event handlers.
*   `src/mcp_server/`: The MCP server that exposes moderation actions as tools for the LLM.
*   `policies/moderation.yaml`: The heart of the bot, where you define all moderation rules.
*   `infra/docker-compose.yml`: Docker configuration for running services like Ollama.
*   `modbot.db`: SQLite database file created at runtime to store moderation history.

## Installation and Setup

### 1. Prerequisites
- Python 3.11+
- `uv` (optional, recommended for quick environment management)
- Docker (for running the local LLM via Ollama)

#### Getting a Discord Bot Token

To run the bot, you need a Discord bot token. Follow the official Discord guide:  
[Discord Developer Portal - Getting Started](https://discord.com/developers/docs/quick-start/getting-started)

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click "New App" and give it a name.
3. Under "Bot", click "Add Bot" and confirm.
4. Under "Bot" settings, click "Reset Token" and copy your bot token.
5. Add the token to your `.env` file as `DISCORD_TOKEN`.

#### Required Bot Permissions

When creating the bot make sure you **turn on** the following permissions:-

- Message Content Intent
- Server Members Intent

#### Getting a Perspective API Key

If you want to use the Perspective API for toxicity scoring, you need to obtain an API key from Google. Follow the official codelab guide here:  
[Setup Perspective API](https://developers.google.com/codelabs/setup-perspective-api#0)

Once you have your key, add it to your `.env` file as `PERSPECTIVE_API_KEY`.

### 2. Install dependencies

You can install project dependencies using the provided `uv` helper (recommended) or with `pip`.

Windows (PowerShell)
```powershell
# create & activate virtualenv
python -m venv .venv
# PowerShell activation
.\.venv\Scripts\Activate.ps1

# upgrade packaging tools
pip install --upgrade pip setuptools wheel

# Option A (recommended if you have 'uv'):
uv sync --extra dev

# Option B (pip): install editable package + extras (dev + llm)
pip install -e ".[dev,llm]"
```

POSIX (macOS / Linux)
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel

# Option A (recommended if you have 'uv'):
uv sync --extra dev

# Option B (pip): install editable package + extras (dev + llm)
pip install -e ".[dev,llm]"
```

Notes:
- `uv sync --extra dev` installs base + dev extras defined in pyproject.toml.
- If you prefer only core runtime deps, use `pip install -e .`
- The `llm` extras install optional LLM providers and are only needed if you use cloud providers or advanced local models.

### 3. Configure Environment
Copy `.env.example` to `.env` and fill the required values (Discord token, provider API keys, MCP_SERVER_URL, etc.)

```bash
copy .env.example .env            # Windows PowerShell
cp .env.example .env              # POSIX
```

### 4. Start services
- If using Ollama (local model), start it with Docker:
```bash
docker-compose -f infra/docker-compose.yml up ollama
```

- Start the MCP server:
```bash
# preferred (run module)
uv run python -m mcp_server.main

# or
uv run python src/mcp_server/main.py
```

- Start the bot
```bash
uv run -m modbot
```

### Option 2: With a Cloud LLM (No Docker)

This method is simpler if you don't have Docker or prefer not to run an LLM locally. You will need two separate terminals.

**1. Configure your `.env` file for a cloud provider (e.g., Gemini):**
Make sure you have set the `MODEL_PROVIDER` and the corresponding `API_KEY` in your `.env` file.
```dotenv
MODEL_PROVIDER=gemini
MODEL_NAME=gemini-1.5-flash
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

**2. Terminal 1: Start the MCP Tool Server**
This server exposes the moderation actions as tools for the LLM.
```bash
uv run python src/mcp_server/main.py
```

**3. Terminal 2: Start the Discord Bot**
Finally, start the bot itself.
```bash
uv run -m modbot
```

Your bot should now be online in Discord and fully operational, using the configured cloud LLM for decisions.

## Policy Configuration (`policies/moderation.yaml`)

This file is where you define all the bot's behavior. The bot loads this file on startup. It has two main sections: `rules` and `escalation`.

### Rules Explained
*   Each rule has a name (e.g., `"Very High Toxicity"`).
*   The `condition` is an expression that must be true for the rule to trigger. You can use `toxicity`, `contains_regex()`, and other helpers.
*   `actions` is a list of actions to perform. Actions can have arguments, like the reason for a warning.

### Escalation Explained
*   `window_minutes`: Defines the time frame (in minutes) for tracking repeat offenses.
*   `thresholds`: Defines what happens when a user accumulates a certain number of actions.
    *   `warns`: Tracks the `warn_user` action.
    *   `timeouts`: Tracks the `timeout_member` action.
    *   The syntax is `count -> action(args)`. You can chain multiple thresholds with a semicolon.

## Health endpoint

The MCP server exposes a simple health endpoint you can use to verify the service and LLM connectivity:

- URL: http://localhost:8000/health
- Returns JSON: status, llm_provider, llm_initialized (bool), tools_registered, uptime_seconds

Example (curl):
```bash
curl http://localhost:8000/health
# {"status":"ok","llm_provider":"gemini","llm_initialized":true,"tools_registered":4,"uptime_seconds":42}
```
