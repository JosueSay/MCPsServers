# MCP (Model Context Protocol) - FEL Server

This document describes how the MCP server works without an SDK (STDIN/STDOUT + JSON-RPC 2.0), its execution flow, tool parameters, return values, and how to test it from the terminal. The conceptual reference is based on Anthropic’s public MCP architecture and introductory guides.

## 1. What MCP Is in This Context

* **Server (capability provider)**: your `server_stdio.py` process, which exposes tools (`fel_validate`, `fel_render`, `fel_batch`) via **JSON-RPC 2.0** over STDIN/STDOUT.
* **Host / Client**: the process that launches the server and sends MCP calls (e.g., a console chatbot or a terminal `printf`).
* **Key messages**:

  * `initialize` -> handshake and capability declaration.
  * `tools/list` -> list available tools.
  * `tools/call` -> invoke a tool with its `arguments`.

## 2. Diagram (Mermaid)

```mermaid
sequenceDiagram
    autonumber
    participant Host as Host/Client (Chat CLI)
    participant Server as MCP Server (server_stdio.py)
    participant FEL as FEL Logic (config.py/fel_pdf.py)

    Note over Host,Server: Transport: STDIN/STDOUT (one JSON message per line)

    Host->>Server: initialize { jsonrpc:"2.0", id:1, method:"initialize", params:{} }
    Server-->>Host: result { protocolVersion, serverInfo, capabilities }

    Host->>Server: tools/list { id:2, method:"tools/list" }
    Server-->>Host: result { tools:[fel_validate, fel_render, fel_batch] }

    Host->>Server: tools/call { id:3, method:"tools/call", params:{ name:"fel_validate", arguments:{ xml_path:"data/xml/factura.xml" } } }
    Server->>FEL: readFelXml(xmlPath)
    FEL-->>Server: FEL data + totals
    Server-->>Host: result { content:[{ type:"text", text:"{ ok, issues, totals }" }] }

    Host->>Server: tools/call { id:4, name:"fel_render", arguments:{ xml_path, logo_path?, theme?, out_path? } }
    Server->>FEL: generatePdf(xmlPath, logoPath, outputPdf, ... )
    FEL-->>Server: PDF generated
    Server-->>Host: result { content:[{ type:"text", text:"{ ok:true, pdf_path }" }] }

    Host->>Server: tools/call { id:5, name:"fel_batch", arguments:{ dir_xml, out_dir? } }
    Server->>FEL: generatePdf() per XML + manifest.json
    FEL-->>Server: count + paths
    Server-->>Host: result { content:[{ type:"text", text:"{ ok, count, out_dir, manifest_path }" }] }
```

## 3. Tool API

### 3.1 `fel_validate`

* **Description**: Validates an FEL XML, audits **12% VAT** and checks **total = subtotal + VAT**, and verifies required fields.
* **Input (`arguments`)**:

  * `xml_path` (string, required): path to the FEL XML.
* **Return (`result.content[0].text`)**: JSON as text:

```json
{
  "ok": true,
  "issues": [],
  "totals": { "subtotal": "8010.59", "iva": "961.27", "total": "8971.86" }
}
```

* `ok` (bool): `true` if no inconsistencies are found.
* `issues` (string\[]): list of detected issues.
* `totals` (strings): monetary values formatted with two decimals.

### 3.2 `fel_render`

* **Description**: Generates a **branded PDF** (logo, fonts, colors) from an FEL XML.
* **Input (`arguments`)**:

  * `xml_path` (string, required): FEL XML path.
  * `logo_path` (string|null, optional): path to a logo; if `null`, uses `LOGO_PATH` by default.
  * `theme` (string|null, optional): reserved for future styles.
  * `out_path` (string|null, optional): PDF output path; if `null`, uses `OUTPUT_PDF` by default.
* **Return**:

```json
{ "ok": true, "pdf_path": "data/out/factura.pdf" }
```

### 3.3 `fel_batch`

* **Description**: Processes a directory of FEL XMLs, generates a PDF per file, and creates a `manifest.json`.
* **Input**:

  * `dir_xml` (string, required): directory containing `*.xml` files.
  * `out_dir` (string|null, optional): output directory (default `data/out`).
* **Return**:

```json
{ "ok": true, "count": 5, "out_dir": "data/out", "manifest_path": "data/out/manifest.json" }
```

## 4. MCP Contract Implemented

* **Transport**: STDIN/STDOUT, one JSON message per line.
* **JSON-RPC schema**: each request includes `jsonrpc:"2.0"`, `id`, `method`, and optional `params`.
* **Supported methods**:

  * `initialize` -> returns `{ protocolVersion, serverInfo, capabilities }`.
  * `tools/list` -> returns `{ tools:[...] }` with `name`, `description`, and `inputSchema` (JSON Schema).
  * `tools/call` -> receives `{ name, arguments }`, executes the tool, and responds with `{ result: { content:[...] } }`.
* **Errors**: standard JSON-RPC format:

```json
{ "jsonrpc":"2.0", "id": <id>, "error": { "code": <int>, "message": "<desc>" } }
```

## 5. Parameters and Environment

The server uses `config.py`, which reads variables from `.env`:

* **Input/Output**: `FEL_XML_PATH`, `FEL_LOGO_PATH`, `FEL_OUTPUT_PDF`.
* **Fonts/Themes**: `FEL_ACTIVE_FONT`, `FEL_FONT_DIR_MONTSERRAT`, `FEL_FONT_DIR_ROBOTOMONO`, `FEL_THEME`.
* **Layout**: `FEL_QR_SIZE`, `FEL_TOP_BAR_HEIGHT`.
* **Footer**: `FEL_WEBSITE`, `FEL_PHONE`, `FEL_EMAIL`.

> At runtime, `fel_render` and `fel_batch` allow paths that override the defaults.

## 6. Execution Flow

1. **Startup**: the Host launches `server_stdio.py` as a subprocess.
2. **Handshake**: Host sends `initialize`; Server returns capabilities.
3. **Discovery**: Host calls `tools/list` to get tools and their schemas.
4. **Invocation**: Host calls `tools/call` with `{ name, arguments }`:

   * `fel_validate` -> extracts data with `readFelXml()`, checks VAT and totals, returns diagnostics.
   * `fel_render` -> calls `generatePdf()` with paths/theme, returns PDF path.
   * `fel_batch` -> iterates XMLs in `dir_xml`, generates PDFs, creates `manifest.json`.
5. **Result**: Server wraps the response in `result.content[0].text` (JSON as text) and sends it to Host.

## 7. Example Calls (Terminal)

### 7.1 Initialization & Tool Listing

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
| python servers/fel_mcp_server/server_stdio.py
```

### 7.2 XML Validation

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fel_validate","arguments":{"xml_path":"data/xml/factura.xml"}}}' \
| python servers/fel_mcp_server/server_stdio.py
```

### 7.3 PDF Rendering

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fel_render","arguments":{"xml_path":"data/xml/factura.xml","logo_path":"data/logos/logo.jpg","out_path":"data/out/factura.pdf"}}}' \
| python servers/fel_mcp_server/server_stdio.py
```

### 7.4 Batch & Manifest

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fel_batch","arguments":{"dir_xml":"data/xml","out_dir":"data/out"}}}' \
| python servers/fel_mcp_server/server_stdio.py
```

## 8. Considerations and Best Practices

* **Monetary format**: parse with `Decimal`, remove commas, enforce two decimals (`ROUND_HALF_UP`).
* **Errors**:

  * Ensure files exist (XML/Logo).
  * Check write permissions for `out_dir`.
  * Any exception is returned as a JSON-RPC `error`.
* **Scalability**:

  * Support for `resources` or `prompts` can be added if needed.
  * Consider cancellation for long-running or streaming tasks.

## 9. Relevant File Structure

```bash
servers/
└─ fel_mcp_server/
   ├─ server_stdio.py     # MCP Server without SDK
   ├─ config.py           # centralized parameters (reads .env)
   └─ fel_pdf.py          # readFelXml(), generatePdf(), helpers
```
