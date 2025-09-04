# Console chatbot using Anthropic Messages API + MCP (stdio JSON-RPC).
# Docs: https://docs.anthropic.com/en/api/messages
# - Keeps short in/out history
# - Writes JSONL logs per session
# - Chat con Claude
# - MCP commands: fel_validate, fel_render, fel_batch

import os, sys, json, uuid, datetime
from typing import List, Dict
from dotenv import load_dotenv
from anthropic import Anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from mcp_client import McpStdioClient, prettyJsonFromMcpResult

load_dotenv()
console = Console()

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL   = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
LOG_DIR = os.getenv("LOG_DIR", "./logs/sessions")
MCP_FEL_CMD = os.getenv("MCP_FEL_CMD", "python servers/fel_mcp_server/server_stdio.py")

if not API_KEY:
    console.print("[red]Missing ANTHROPIC_API_KEY[/red]")
    sys.exit(1)

os.makedirs(LOG_DIR, exist_ok=True)
session_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
log_path = os.path.join(LOG_DIR, f"{session_id}.jsonl")

def logEvent(event: dict):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def readUserInput(prompt: str = "[bold cyan]You[/] › ") -> str:
    """Lee una línea y normaliza comandos de salida."""
    s = console.input(prompt).strip()
    if s in ("/quit", "/exit"):
        return "__EXIT__"     # sentinel
    return s

def printToolsPretty(tools: dict):
    tbl = Table(title="MCP Tools")
    tbl.add_column("name", style="bold")
    tbl.add_column("description")
    tbl.add_column("required args")
    for t in tools["result"]["tools"]:
        req = ", ".join(t["inputSchema"].get("required", []))
        tbl.add_row(t["name"], t.get("description",""), req)
    console.print(tbl)

def main():
    client = Anthropic(api_key=API_KEY)
    mcp = McpStdioClient(MCP_FEL_CMD)
    mcp.start()
    _ = mcp.listTools()

    console.rule("[bold]Claude Console + MCP (FEL)")
    console.print("[dim]commands: /exit | /clear | /tools | fel_validate <xml> | fel_render <xml> [logo] [theme] [out] | fel_batch <dir_xml> [out_dir][/dim]")

    history: List[Dict[str, str]] = []

    try:
        for user in iter(readUserInput, "__EXIT__"):
            if not user:
                continue

            if user == "/clear":
                history.clear()
                console.print("[green]history cleared[/green]")
                continue
            
            if user == "/tools":
                tools = mcp.listTools()
                printToolsPretty(tools)
                logEvent({"type":"mcp","tool":"tools/list","result":tools})
                continue

            parts = user.split()
            head = parts[0].lower()

            # --- comandos MCP ---
            try:
                if head == "fel_validate" and len(parts) >= 2:
                    xml_path = parts[1]
                    resp = mcp.callTool("fel_validate", {"xml_path": xml_path})
                    text = prettyJsonFromMcpResult(resp)
                    console.print(Markdown(f"```json\n{text}\n```"))
                    logEvent({"type":"mcp","tool":"fel_validate","args":{"xml_path":xml_path},"result":text})
                    continue

                if head == "fel_render" and len(parts) >= 2:
                    xml_path = parts[1]
                    logo_path = parts[2] if len(parts) >= 3 else None
                    theme     = parts[3] if len(parts) >= 4 else None
                    out_path  = parts[4] if len(parts) >= 5 else None
                    resp = mcp.callTool("fel_render", {
                        "xml_path": xml_path, "logo_path": logo_path, "theme": theme, "out_path": out_path
                    })
                    text = prettyJsonFromMcpResult(resp)
                    console.print(Markdown(f"```json\n{text}\n```"))
                    logEvent({"type":"mcp","tool":"fel_render","args":{"xml_path":xml_path,"logo_path":logo_path,"theme":theme,"out_path":out_path},"result":text})
                    continue

                if head == "fel_batch" and len(parts) >= 2:
                    dir_xml = parts[1]
                    out_dir = parts[2] if len(parts) >= 3 else None
                    resp = mcp.callTool("fel_batch", {"dir_xml": dir_xml, "out_dir": out_dir})
                    text = prettyJsonFromMcpResult(resp)
                    console.print(Markdown(f"```json\n{text}\n```"))
                    logEvent({"type":"mcp","tool":"fel_batch","args":{"dir_xml":dir_xml,"out_dir":out_dir},"result":text})
                    continue
            except Exception as e:
                console.print(f"[red]MCP error:[/red] {e}")
                logEvent({"type":"mcp_error","input":user,"error":str(e)})
                continue

            # --- chat con Claude ---
            recent = history[-10:]
            stitched = "".join(f"{h['role']}: {h['content']}\n" for h in recent) + f"user: {user}"

            try:
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=800,
                    messages=[{"role": "user", "content": stitched}],
                )
                text = resp.content[0].text if resp.content else ""
            except Exception as e:
                text = f"Error: {e}"

            console.print(Markdown(text))
            logEvent({"type":"llm","model":MODEL,"input":user,"output":text})
            history.append({"role":"user","content":user})
            history.append({"role":"assistant","content":text})

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
    finally:
        mcp.stop()
        console.print(f"[dim]log: {log_path}[/dim]")

if __name__ == "__main__":
    main()