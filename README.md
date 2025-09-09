# Claude Console + MCP (FEL)

This project implements a **console-based chatbot** that connects to **Anthropic Claude** via API and integrates with **Model Context Protocol (MCP)** servers.  
The chatbot can **maintain conversational context**, automatically decide when to use tools, and log all interactions in structured JSONL files.  
It includes a custom **FEL MCP server** that validates and renders **Guatemalan FEL electronic invoices** into branded PDFs.

> **Monorepo notice:** This repository consolidates two implemented codebases: the **chatbot (CLI/UI)** and the **local FEL MCP server**.  
>
> It also links to a third repository used **only as reference** for API connection patterns.

## 🔗 Related repositories

- [Chatbot (CLI / UI)](https://github.com/JosueSay/ChatBotMCP) — Implemented and unified in this monorepo.
- [MCP FEL (Local)](https://github.com/JosueSay/MCPLocalFEL) — Implemented and unified in this monorepo.
- [Reference: OpenAI Chat API Example](https://github.com/JosueSay/Selectivo_IA/blob/main/docs_assistant/README.md) — Reference only (used for connection patterns, instruction context).

## ✨ Features

- Connects to **Anthropic Claude API** (LLM).
- Maintains conversational context during a session.
- Supports **manual and automatic tool usage**.
- Integrated **FEL MCP tools**:
  - `fel_validate`: Validate XML totals (subtotal, VAT 12%, total).
  - `fel_render`: Render branded PDF invoices from FEL XML.
  - `fel_batch`: Render multiple XML invoices into PDFs + manifest.
- Session logs stored as **structured JSONL**.
- Path sandboxing (`ALLOWED_ROOTS`) to prevent unsafe file access.

## ⚙️ Requirements

- **Python** 3.12
- **Ubuntu 22.04 (WSL)** or Linux environment
- Virtual environment (recommended)

## 🔧 Installation

When starting the chatbot, you can now run **multiple MCP servers at the same time**.  
This allows you to combine local tools (e.g., FEL) with external integrations like **Filesystem** and **GitHub**.

### Environment Variables

Edit your `.env` with the following variables:

```env
# ---- Keys ----
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-sonnet-4-20250514 # optional, other models: https://docs.anthropic.com/en/api/models-list
GITHUB_TOKEN=your_token # Personal Access Token (fine-grained or classic)

# ---- MCPS ----
MCP_FEL_CMD="/ABSOLUTE/PATH/venv/bin/python /ABSOLUTE/PATH/servers/fel_mcp_server/server_stdio.py"
MCP_URL=url_mcp # pending

# Multiple MCP servers (comma-separated)
# Recommended order: FEL (local), Filesystem (Docker), GitHub (Docker)
MCP_CMDS="/ABSOLUTE/PATH/venv/bin/python /ABSOLUTE/PATH/servers/fel_mcp_server/server_stdio.py,docker run --rm -i -v /ABSOLUTE/PATH/data/testing:/data node:22 npx -y @modelcontextprotocol/server-filesystem /data,docker run --rm -i -e GITHUB_TOKEN node:22 npx -y @modelcontextprotocol/server-github"

# ---- Chat Config ----
LOG_DIR=/ABSOLUTE/PATH/TO/REPO/data/logs/sessions
ROUTER_DEBUG=0 # 1: active | 0: inactive
```

### GitHub MCP

To use the **GitHub MCP** you need:

1. Create a **personal token** (fine-grained or classic).

2. Clone the official MCP servers repository to an absolute path:

   ```bash
   git clone https://github.com/modelcontextprotocol/servers.git
   ```

3. Replace `/ABSOLUTE/PATH/servers` in your `.env` with the actual path to the cloned repo.

This way, the chatbot can launch and orchestrate multiple MCPs in parallel.

## 🚀 Usage

Start the chatbot from the project root:

```bash
python apps/cli/chat.py
```

You will see:

```bash
───────────────────── Claude Console + MCP (FEL) ──────────────────────
commands: /exit | /clear | /tools | fel_validate <xml> | fel_render <xml> | fel_batch <dir_xml>
You ›
```

### Example

```text
You › /tools
MCP Tools
name         | description                                  | required args
-------------|----------------------------------------------|---------------
fel_validate | Validate FEL XML totals and required fields  | xml_path
fel_render   | Render branded PDF from FEL XML              | xml_path
fel_batch    | Render directory of FEL XMLs -> manifest.json | dir_xml
```

```bash
You › puedes validar precios de data/xml/factura.xml?
La validación de la factura fue exitosa. Los totales calculados son:

 • Subtotal: Q8,010.59
 • IVA (12%): Q961.27
 • Total: Q8,971.86

No se encontraron errores en los precios ni en los campos requeridos.
```

If absolute paths for the official MCP servers were set, you can now have more tools available: **FEL + System Files + GitHub**.

![Official MCP Tools in Action](./images/mcp_tools.png)

## 🗂 Project Structure

```bash
.
├── apps/
│   ├── cli/
│   │   └── chat.py           # CLI chatbot frontend
│   └── ui/                   # Pending: future UI frontend
├── core/
│   ├── engine.py             # Orchestration layer (Claude + MCP)
│   ├── mcp_stdio.py          # Minimal JSON-RPC client for MCP servers
│   └── settings.py           # Environment and configuration
├── servers/fel_mcp_server/   # FEL MCP server (validate, render, batch)
├── data/
│   ├── logos/                # Image logo
│   ├── xml/                  # Sample FEL XML input
│   └── out/                  # PDF output
├── logs/sessions/            # Session logs (.jsonl)
├── assets/
│   ├── fonts/                # Custom fonts (Montserrat, Roboto Mono)
│   └── images/               # Icons (phone, email, web)
└── docs/                     # Documentation MCP + Code
```

## 📝 Logs

Every session is automatically logged in `logs/sessions/` as **JSONL**.

Example log entries:

```json
{
  "type": "mcp",
  "op": "tools/list",
  "result": { ... }
}
{
  "type": "llm_auto",
  "model": "claude-sonnet-4-20250514",
  "input": "puedes validar precios de data/xml/factura.xml?",
  "output": "La validación de la factura fue exitosa..."
}
```

These logs allow you to trace **tool usage**, **LLM decisions**, and **outputs**.

## 🔒 Security Notes

- `ALLOWED_ROOTS` defines directories where MCP tools can access files (`data/xml`, `data/out`, `data/logos` by default).
- Any path outside of these roots will be **blocked** for safety.
- Logs may contain sensitive invoice data -> review before sharing.

## 📚 References

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Anthropic API Docs](https://docs.anthropic.com/en/api)
- [Antrhopic Build an MCP Server](https://modelcontextprotocol.io/quickstart/server)
- [JSON-RPC 2.0](https://www.jsonrpc.org/)

## 🖥️ Using with Claude Desktop + MCP

You can also run the FEL server directly inside **Claude Desktop** via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).

### 1. Install Claude Desktop

Download and install Claude from here:
👉 [https://claude.ai/download](https://claude.ai/download)

> ⚠️ Claude Desktop is available for **Windows/macOS**.
>
> Our FEL server was designed to run inside **WSL (Ubuntu)**.

### 2. Configure MCP

Open Claude Desktop and go to:
**File -> Settings -> Developer -> Edit Config**

This will open the configuration folder. Edit the file `claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "FEL": {
      "command": "wsl.exe",
      "args": [
        "-e",
        "<absolute_path>/venv/bin/python",
        "<absolute_path>/servers/fel_mcp_server/server_stdio.py"
      ]
    }
  }
}
```

🔑 **Note**:
Replace `<absolute_path>` with the full absolute path inside WSL, e.g.:
`/mnt/d/repositorios/UVG/2025/MCPsServers`

### 3. Restart Claude Desktop

After saving the config file, restart Claude Desktop from **PowerShell**:

```powershell
Stop-Process -Name "Claude" -Force; Start-Process "<absolute_path>\Claude.exe"
```

Here `<absolute_path>\Claude.exe` should be replaced with the full path to your Claude installation, for example:
`C:\Users\<username>\AppData\Local\AnthropicClaude\Claude.exe`

## 🎬 Test Example

- [Watch the video with my chatbot](https://youtu.be/RaGJxHGllNY)
- [Watch the video with Claude Desktop](https://youtu.be/_vuhF7jKm1M)
