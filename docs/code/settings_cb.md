# Technical Glossary — `core/settings.py`

**Configuration layer** for the chatbot/MCP. Loads environment variables from `.env`, exposes "helpers" for safe parsing, and publishes constants used by the CLI and engine.

## Dependencies

* `os`: for reading environment variables.
* `dotenv.load_dotenv()`: lazy loading of `.env` (optional; errors ignored).

## Load Flow

1. Attempts `load_dotenv()` (inside `try/except` to avoid failing if the library or file is missing).
2. Defines utility functions `envBool` and `envList`.
3. Reads environment variables and sets reasonable **defaults**.
4. Exports symbols via `__all__`.

## Helpers

### `envBool(name: str, default: bool) -> bool`

* **Purpose:** Parse boolean flags from env.
* **Input:** `name` (env key), `default` (fallback value).
* **Accepted as `True`:** `1`, `true`, `yes`, `on`.
* **Accepted as `False`:** `0`, `false`, `no`, `off`.
* **Return:** `bool`.
* **Edge case:** if the variable **does not exist** or the value does not match the lists above -> returns `default`.

### `envList(name: str, default_csv: str) -> list[str]`

* **Purpose:** Read comma-separated lists from env.
* **Input:** `name` and a `default_csv` string (e.g., `"a,b,c"`).
* **Cleaning:** `strip()` each element and discard empty strings.
* **Return:** `list[str]`.

## Configuration Variables (exported)

> All can be overridden in `.env`. Defaults in parentheses.

* `API_KEY: str` -> `ANTHROPIC_API_KEY` (`""`)

  **Note:** CLI aborts if empty.

* `MODEL: str` -> `ANTHROPIC_MODEL` (`"claude-sonnet-4-20250514"`)
* `MCP_FEL_CMD: str` -> command to launch the MCP **stdio server**

  Default: `"python servers/fel_mcp_server/server_stdio.py"`.
* `LOG_DIR: str` -> folder for **session logs** (`"./logs/sessions"`).
* `ROUTER_DEBUG: bool` -> router/tool usage trace (`True` by default, via `envBool`).
* `ALLOWED_ROOTS: list[str]` -> sandbox for tool file access (`"data/xml,data/out,data/logos"`, via `envList`).
* `SYSTEM_PROMPT: str` -> system prompt for the LLM; if missing, uses embedded `_DEFAULT_PROMPT`.
  The prompt instructs: **respond in the user’s language**, use tools **only** for FEL, **do not** output raw JSON, and **explain** output paths / validation diagnostics.

`__all__` controls which symbols are importable from other modules.

## _DEFAULT_PROMPT (summary)

* Always respond in the user’s language.
* Use MCP tools **exclusively** for FEL tasks (validate, render, batch).
* After using a tool, return a **concise, human-readable response** (no raw JSON).
* When rendering, **state the PDF path**; when validating, **summarize totals and findings**.

## Security and Best Practices

* **Keys:** do not commit `.env`; use `ANTHROPIC_API_KEY` in deployments.
* **Sandbox:** keep `ALLOWED_ROOTS` restrictive to prevent reads/writes outside `data/*`.
* **Logs:** `LOG_DIR` may contain sensitive data (invoices); review before sharing.

## Example `.env`

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# MCP stdio server
MCP_FEL_CMD=python servers/fel_mcp_server/server_stdio.py

# Logs and debugging
LOG_DIR=./logs/sessions
ROUTER_DEBUG=1

# File sandbox
ALLOWED_ROOTS=data/xml,data/out,data/logos

# System prompt (optional)
SYSTEM_PROMPT=You are a helpful general assistant...
```
