"""
CLI frontend for the Anthropic + MCP chat.

This module is a **thin UI layer**:
- It renders a simple REPL (console chat).
- It delegates orchestration (LLM + tool-use) to `core.engine.ChatEngine`.
- It prints debug traces and tool-call summaries when `ROUTER_DEBUG=1`.

Hotkeys / Commands
------------------
/tools                              : Show MCP tools table
/clear                              : Clear short history (context)
// exit via /exit or /quit

Manual shortcuts (optional):
  fel_validate <xml>
  fel_render   <xml> [logo] [theme] [out]
  fel_batch    <dir_xml> [out_dir]

All other inputs go to the LLM. The model decides when to call tools.
"""

from pathlib import Path
import sys

# Allow "core" imports when running from repo root or this file's folder
sys.path.append(str(Path(__file__).resolve().parents[2]))

import os
import json
import uuid
import datetime
from typing import Any
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from core.engine import ChatEngine
from core.settings import (
    API_KEY,
    MODEL,
    MCP_FEL_CMD,
    LOG_DIR,
    ROUTER_DEBUG,
    SYSTEM_PROMPT,
    ALLOWED_ROOTS,
)

console = Console()

# Fail fast if API key is missing
if not API_KEY:
    console.print("[red]Missing ANTHROPIC_API_KEY[/red]")
    sys.exit(1)

# Create a per-session JSONL log file
os.makedirs(LOG_DIR, exist_ok=True)
sessionId = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
logPath = os.path.join(LOG_DIR, f"{sessionId}.jsonl")


def logEvent(event: dict) -> None:
    """Append a structured event to the current JSONL session log."""
    with open(logPath, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def printJsonBlock(obj: Any) -> None:
    """Render a Python object or JSON string as a fenced JSON block in the console."""
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2)
    console.print(Markdown("```json\n" + text + "\n```"))


def readUserInput(prompt: str = "[bold cyan]You[/] › ") -> str:
    """
    Read a single line from the console.
    Returns the special sentinel '__EXIT__' when user types /exit or /quit.
    """
    s = console.input(prompt).strip()
    if s in ("/quit", "/exit"):
        return "__EXIT__"
    return s


def printToolsPretty(toolsCatalog: dict) -> None:
    """
    Display the MCP tool catalog in a compact table:
    name | description | required args (from JSON Schema 'required' list)
    """
    tbl = Table(title="MCP Tools")
    tbl.add_column("name", style="bold")
    tbl.add_column("description")
    tbl.add_column("required args")
    for t in toolsCatalog["result"]["tools"]:
        req = ", ".join(t["inputSchema"].get("required", []))
        tbl.add_row(t["name"], t.get("description", ""), req)
    console.print(tbl)


def main() -> None:
    """Interactive console loop that delegates orchestration to ChatEngine."""
    console.rule("[bold]Claude Console + MCP (FEL)")
    console.print(
        "[dim]commands: /exit | /clear | /tools | "
        "fel_validate <xml> | fel_render <xml> [logo] [theme] [out] | fel_batch <dir_xml> [out_dir][/dim]"
    )

    # UI-agnostic engine (safe to reuse for Web later)
    engine = ChatEngine(
        apiKey=API_KEY,
        model=MODEL,
        mcpCmd=MCP_FEL_CMD,
        systemPrompt=SYSTEM_PROMPT,   # "reply in user's language; only use FEL tools when needed"
        allowedRoots=ALLOWED_ROOTS,   # minimal path sandbox
        routerDebug=ROUTER_DEBUG,     # print router/tool traces when True
    )
    engine.start()

    # Keep a short rolling history (assistant/user text only)
    history: list[dict[str, Any]] = []

    try:
        # read lines until the sentinel is returned
        for user in iter(readUserInput, "__EXIT__"):
            if not user:
                continue

            # Utilities
            if user == "/clear":
                history.clear()
                console.print("[green]history cleared[/green]")
                continue

            if user == "/tools":
                tools = engine.listTools()
                printToolsPretty(tools)
                logEvent({"type": "mcp", "op": "tools/list", "result": tools})
                continue

            # Optional manual MCP shortcuts
            parts = user.split()
            head = parts[0].lower()
            try:
                if head == "fel_validate" and len(parts) >= 2:
                    res = engine.callTool("fel_validate", {"xml_path": parts[1]})
                    printJsonBlock(res)
                    logEvent({
                        "type": "mcp_manual",
                        "tool": "fel_validate",
                        "args": {"xml_path": parts[1]},
                        "result": res,
                    })
                    continue

                if head == "fel_render" and len(parts) >= 2:
                    args = {
                        "xml_path": parts[1],
                        "logo_path": parts[2] if len(parts) >= 3 else None,
                        "theme":     parts[3] if len(parts) >= 4 else None,
                        "out_path":  parts[4] if len(parts) >= 5 else None,
                    }
                    res = engine.callTool("fel_render", args)
                    printJsonBlock(res)
                    logEvent({"type": "mcp_manual", "tool": "fel_render", "args": args, "result": res})
                    continue

                if head == "fel_batch" and len(parts) >= 2:
                    args = {
                        "dir_xml": parts[1],
                        "out_dir": parts[2] if len(parts) >= 3 else None
                    }
                    res = engine.callTool("fel_batch", args)
                    printJsonBlock(res)
                    logEvent({"type": "mcp_manual", "tool": "fel_batch", "args": args, "result": res})
                    continue
            except Exception as e:
                console.print(f"[red]MCP error:[/red] {e}")
                logEvent({"type": "mcp_manual_error", "input": user, "error": str(e)})
                continue

            # Free-form turn: the model decides whether to use MCP tools
            turn = engine.chatTurn(history, user)

            if ROUTER_DEBUG:
                # Show router trace (all hops)
                printJsonBlock({"source": "router", "trace": turn.get("router", {}).get("trace", [])})
                # Show tool calls executed by the engine
                if turn.get("tools", {}).get("calls"):
                    printJsonBlock({"source": "tools", "calls": turn["tools"]["calls"]})

            # Final assistant text
            console.print(Markdown(turn["finalText"]))
            logEvent({"type": "llm_auto", "model": MODEL, "input": user, "output": turn["finalText"]})

            # Update short history (assistant & user text only)
            history.append({"role": "user", "content": user})
            history.append({"role": "assistant", "content": turn["finalText"]})

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
    finally:
        engine.stop()
        console.print(f"[dim]log: {logPath}[/dim]")


if __name__ == "__main__":
    main()
