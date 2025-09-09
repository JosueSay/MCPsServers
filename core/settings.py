import os
from dotenv import load_dotenv

try:
    load_dotenv()
except Exception:
    pass


def envBool(name: str, default: bool) -> bool:
    """Parse truthy/falsey values from env; supports 1/0, true/false, yes/no."""
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def envList(name: str, default_csv: str) -> list[str]:
    """Split comma-separated env var, trimming spaces and dropping empties."""
    raw = os.getenv(name, default_csv)
    return [p.strip() for p in raw.split(",") if p.strip()]


# ---- Core API / MCP configuration ------------------------------------------

API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Command to launch your MCP server (stdio JSON-RPC)
MCP_FEL_CMD: str = os.getenv("MCP_FEL_CMD", "python servers/fel_mcp_server/server_stdio.py")

# URL for remote MCP (HTTP JSON-RPC)
MCP_URL: str = os.getenv("MCP_URL", "")

# Logs directory (the CLI will create per-session JSONL files here)
LOG_DIR: str = os.getenv("LOG_DIR", "./logs/sessions")

# Show router/tool traces in the UI
ROUTER_DEBUG: bool = envBool("ROUTER_DEBUG", True)

# Minimal filesystem sandbox for tools that take paths
ALLOWED_ROOTS: list[str] = envList("ALLOWED_ROOTS", "data/xml,data/out,data/logos")

# System instruction for the model. You can override with SYSTEM_PROMPT in .env
_DEFAULT_PROMPT = (
    "You are a helpful general assistant. Always reply in the user's language. "
    "Use MCP tools whenever the request matches any available tool (FEL, filesystem, GitHub, Overwatch, etc). "
    "After using a tool, return one concise, human-readable answer that addresses the user's request; "
    "do not paste raw JSON. "
    "When rendering PDFs, clearly state the output path. "
    "When validating FEL invoices, summarize totals and any issues. "
    "When using filesystem tools, always prefer them for file or directory operations. "
    "When using GitHub tools, always prefer them for repository queries. "
    "Never answer directly if a relevant MCP tool exists."
)
SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", _DEFAULT_PROMPT)

MCP_CMDS: list[str] = envList("MCP_CMDS", "...")


__all__ = [
    "API_KEY",
    "MODEL",
    "MCP_FEL_CMD",
    "MCP_URL",
    "MCP_CMDS",
    "LOG_DIR",
    "ROUTER_DEBUG",
    "SYSTEM_PROMPT",
    "ALLOWED_ROOTS",
    "envBool",
    "envList",
]

