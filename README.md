# MCPsServers

## Structure

```bash
McpServers/
├─ README.md
├─ .env.example
├─ requirements.txt
├─ data/
│  ├─ xml/                  # Test FEL XML files
│  ├─ out/                  # Generated PDFs
│  └─ logos/                # Brand logos
├─ assets/
│  └─ fonts/                # .ttf (Montserrat/Roboto)
├─ apps/
│  └─ cli/
│     └─ chat.py            # Console chatbot (Claude API + logs)
├─ servers/
│  └─ fel_mcp_server/
│     ├─ server.py          # Local MCP server (FEL→PDF/validation/batch)
│     ├─ fel_pdf.py         # Reuses your ReportLab/XML logic
│     └─ sat_qr.py          # URL/QR code builder
├─ mcp_clients/
│  ├─ filesystem.json       # Official MCP client config: filesystem
│  └─ git.json              # Official MCP client config: git
└─ logs/
   └─ sessions/             # .jsonl with history and MCP calls
```
