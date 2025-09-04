# Console chatbot using Anthropic Messages API.
# - Keeps short in/out history
# - Writes JSONL logs per session
# Docs: https://docs.anthropic.com/en/api/messages

import os, json, datetime, uuid, sys
from typing import List, Dict
from dotenv import load_dotenv
from anthropic import Anthropic
from rich.console import Console
from rich.markdown import Markdown

load_dotenv()
console = Console()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL   = os.getenv("ANTHROPIC_MODEL")
LOG_DIR = os.getenv("LOG_DIR", "./logs/sessions")

if not API_KEY:
    console.print("[red]Missing ANTHROPIC_API_KEY[/red]")
    sys.exit(1)

os.makedirs(LOG_DIR, exist_ok=True)
session_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
log_path = os.path.join(LOG_DIR, f"{session_id}.jsonl")

def logEvent(event: dict):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def main():
    client = Anthropic(api_key=API_KEY)
    console.rule("[bold]Claude Console Chat")
    console.print("[dim]commands: /exit | /clear[/dim]")

    # keep a compact rolling history
    history: List[Dict[str, str]] = []

    while True:
        user = console.input("[bold cyan]You[/] › ").strip()
        if user in ("/exit", "/quit"): break
        if user == "/clear":
            history = []
            console.print("[green]history cleared[/green]")
            continue
        if not user:
            continue

        # build prompt from rolling history (stateless API)
        # keep last 10 turns max to stay concise
        recent = history[-10:]
        stitched = ""
        for h in recent:
            stitched += f"{h['role']}: {h['content']}\n"
        stitched += f"user: {user}"

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

    console.print(f"[dim]log: {log_path}[/dim]")

if __name__ == "__main__":
    main()
