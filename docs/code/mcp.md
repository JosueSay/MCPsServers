# Technical Glossary

Minimal **MCP** server over **STDIN/STDOUT** (no SDK), exposing three tools for working with **FEL**:

* `fel_validate`: validates totals and required fields in a FEL XML.
* `fel_render`: generates a **watermarked PDF** from a FEL XML.
* `fel_batch`: processes a directory of XMLs and generates PDFs + `manifest.json`.

Reads **JSON-RPC 2.0** line by line from `STDIN` and writes responses to `STDOUT`.

## Dependencies and Modules

* **Standard library**: `sys`, `json`, `os`, `glob`, `decimal` (`Decimal`, `ROUND_HALF_UP`), `typing.Any`.
* **Local modules**:

  * `config.py` -> constants: `XML_PATH`, `LOGO_PATH`, `OUTPUT_PDF`, `DEFAULT_QR_SIZE`, `DEFAULT_TOP_BAR_HEIGHT`.
  * `fel_pdf.py` -> functions: `readFelXml(xmlPath)`, `generatePdf(...)`.

> **Note**: Although `XML_PATH`, `LOGO_PATH`, etc. are imported from `config.py`, the tools accept paths via arguments that **override** these defaults.

## MCP Response Conventions

All JSON-RPC responses follow:

```json
{ "jsonrpc": "2.0", "id": <msgId>, "result": <obj> }
```

When the response is for `tools/call`, the **MCP result** is wrapped as:

```json
{
  "result": {
    "content": [
      { "type": "text", "text": "<json as text>" }
    ]
  }
}
```

On error:

```json
{ "jsonrpc": "2.0", "id": <msgId>, "error": { "code": <int>, "message": "<description>" } }
```

## Functions

### 1. `sendResponse(msgId: Any, result: Any = None, error: dict[str, Any] | None = None) -> None`

**Purpose**: write a **single** JSON-RPC response to `STDOUT` and flush the buffer.

**Inputs**:

* `msgId`: request identifier.
* `result`: content for `result` (mutually exclusive with `error`).
* `error`: JSON-RPC error object `{code:int, message:str}`.

**Output**: `None` (side effect: I/O to `STDOUT`).

**Behavior**: serializes with `json.dumps(..., ensure_ascii=False)`, appends `\n`, and flushes.

**Errors**: if both `result` and `error` are `None`, sends `result: null` (valid).

### 2. `getCapabilities() -> dict[str, Any]`

**Purpose**: declare minimal MCP capabilities.

**Output**:

```python
{
  "protocolVersion": "2024-11-05",
  "serverInfo": {"name": "fel-stdio", "version": "0.1.0"},
  "capabilities": {"tools": {}}
}
```

**Usage**: response to `initialize`. Independent of `env`.

### 3. `listTools() -> dict[str, Any]`

**Purpose**: describe available tools and their **input JSON Schemas**.

**Output**:

```python
{
  "tools": [
    {
      "name": "fel_validate",
      "description": "...",
      "inputSchema": {
        "type": "object",
        "properties": {"xml_path": {"type": "string"}},
        "required": ["xml_path"]
      }
    },
    {
      "name": "fel_render",
      "description": "...",
      "inputSchema": {
        "type": "object",
        "properties": {
          "xml_path": {"type": "string"},
          "logo_path": {"type": ["string", "null"]},
          "theme": {"type": ["string", "null"]},
          "out_path": {"type": ["string", "null"]}
        },
        "required": ["xml_path"]
      }
    },
    {
      "name": "fel_batch",
      "description": "...",
      "inputSchema": {
        "type": "object",
        "properties": {
          "dir_xml": {"type": "string"},
          "out_dir": {"type": ["string", "null"]}
        },
        "required": ["dir_xml"]
      }
    }
  ]
}
```

**Note**: Schemas are used by the Host to validate/help the LLM.

### 4. `parseMoney(value: Any) -> Decimal`

**Purpose**: convert monetary values with thousand separators to `Decimal`.

**Input**: `value` (e.g., `"1,234.56"` or `8010.59`).

**Output**: `Decimal("1234.56")`.

**Details**: `str(value).replace(",", "") -> Decimal(...)`.

**Errors**: may raise `InvalidOperation` if `value` is unparseable.

### 5. `validateFel(xmlPath: str) -> dict[str, Any]`

**Purpose**: validate a **FEL XML**:

* calculate VAT (12%) and check `total = subtotal + VAT`,
* verify required fields: `numero_autorizacion`, `nit`, `id_receptor`, `monto`.

**Inputs**: `xmlPath` (FEL XML path as string).

**Flow**:

1. `data = readFelXml(xmlPath)` (extracts fields and totals as formatted **strings**).
2. Parse monetary values using `parseMoney`.
3. Expected calculation:

   * `expectedIva = subtotal * 0.12` (`quantize(0.01, ROUND_HALF_UP)`),
   * `expectedTotal = subtotal + expectedIva`.
4. Compare with 0.01 tolerance: if different -> add message to `issues`.
5. Check required fields: if missing -> add `"Missing field: <key>"`.

**Output**:

```python
{
  "ok": bool,                 # True if no issues
  "issues": list[str],        # discrepancy messages
  "totals": {
    "subtotal": str, "iva": str, "total": str  # as strings (no commas)
  }
}
```

**Dependencies**: `readFelXml`, `Decimal`, `ROUND_HALF_UP`, `parseMoney`.

**Errors**: propagates exceptions from `readFelXml` (e.g., missing file) or parsing.

### 6. `renderFel(xmlPath: str, logoPath: str | None, theme: str | None, outPath: str | None) -> dict[str, Any]`

**Purpose**: generate a **PDF** with ReportLab from a FEL XML.

**Inputs**:

* `xmlPath` (**req.**): FEL XML.
* `logoPath` (*opt.*): if `None`, uses `LOGO_PATH` from `config.py`.
* `theme` (*opt.*): reserved for future styles (not used yet).
* `outPath` (*opt.*): if `None`, uses `OUTPUT_PDF`.

**Flow**:

* Resolve `logo` and `out` with defaults.
* Call `generatePdf(xmlPath=..., logoPath=..., outputPdf=..., topBarHeight=DEFAULT_TOP_BAR_HEIGHT, qrSize=DEFAULT_QR_SIZE)`.

**Output**:

```python
{ "ok": True, "pdf_path": out }
```

**Dependencies**: `generatePdf`, constants from `config.py`.

**Effects**: writes PDF to disk; creates directories as needed.

**Errors**: any `generatePdf` exception (e.g., missing fonts/files).

### 7. `batchFel(dirXml: str, outDir: str | None) -> dict[str, Any]`

**Purpose**: process **all** `*.xml` in `dirXml`, generate one PDF per file, and build `manifest.json`.

**Inputs**:

* `dirXml` (**req.**): folder path with XMLs.
* `outDir` (*opt.*): output folder; if `None`, uses `data/out`.

**Flow**:

1. Normalize `outDir` and `os.makedirs(outDir, exist_ok=True)`.
2. Iterate `glob.glob(dirXml/*.xml)` (sorted).
3. For each XML:

   * compose `pdfPath = outDir/<name>.pdf`,
   * call `generatePdf(...)` with `LOGO_PATH` and default sizes,
   * add `{"xml": xml, "pdf": pdfPath}` to `manifest`.
4. Write `manifest.json` in `outDir`.

**Output**:

```python
{
  "ok": True,
  "count": <int>,                   # number of XMLs processed
  "out_dir": "<path>",
  "manifest_path": "<path>/manifest.json"
}
```

**Dependencies**: `glob`, `os`, `json`, `generatePdf`, `LOGO_PATH`.

**Effects**: creates PDFs and `manifest.json` on disk.

**Errors**: XML reading or disk writing errors propagate; if no `*.xml`, `count` is `0` and manifest is `[]`.

### 8. `callTool(name: str, args: dict[str, Any]) -> dict[str, Any]`

**Purpose**: **router** for `tools/call` to the corresponding FEL function.

**Inputs**:

* `name`: `"fel_validate" | "fel_render" | "fel_batch"`.
* `args`: dictionary of arguments according to the tool’s JSON Schema.

**Flow**:

* `fel_validate` -> `validateFel(args["xml_path"])`
* `fel_render` -> `renderFel(args["xml_path"], args.get("logo_path"), args.get("theme"), args.get("out_path"))`
* `fel_batch` -> `batchFel(args["dir_xml"], args.get("out_dir"))`
* If `name` does not match -> `raise ValueError("Unknown tool ...")`

**Output**: dict with operation response (see previous functions).
**Errors**: `KeyError` if required args missing; `ValueError` if tool unknown.

### 9. `main() -> None`

**Purpose**: **main JSON-RPC loop** over `STDIN`.

**Flow** (per line):

1. `req = json.loads(line)` (ignores invalid format via global `except`).
2. Extract `method` and `id` (`msgId`).
3. Dispatch:

   * `"initialize"` -> `sendResponse(id, getCapabilities())`
   * `"tools/list"` -> `sendResponse(id, listTools())`
   * `"tools/call"` ->

     * `params = req.get("params", {})`
     * `name = params.get("name")`
     * `arguments = params.get("arguments", {})`
     * `result = callTool(name, arguments)`
     * Wrap MCP: `{"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}`
     * `sendResponse(id, wrapper)`
   * Other method -> `sendResponse(id, error={"code": -32601, "message": f"Method not found: {method}"})`
4. Global errors -> `sendResponse(id, error={"code": -32000, "message": str(e)})`

**Effects**: continuous read from `STDIN` and write to `STDOUT`.

**Termination**: process ends on EOF or external signal.

## Method ↔ Tool Mapping

| JSON-RPC Method | Description                  | Response (`result`)                             |
| --------------- | ---------------------------- | ----------------------------------------------- |
| `initialize`    | Handshake and capabilities   | `{ protocolVersion, serverInfo, capabilities }` |
| `tools/list`    | Catalog of tools and schemas | `{ tools: [...] }`                              |
| `tools/call`    | FEL tool invocation          | `{ content: [{type:"text", text:"<json>"}] }`   |

## I/O Examples

**1. initialize + tools/list:**

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
| python servers/fel_mcp_server/server_stdio.py
```

**2. fel_validate:**

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fel_validate","arguments":{"xml_path":"data/xml/factura.xml"}}}' \
| python servers/fel_mcp_server/server_stdio.py
```

**3. fel_render:**

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fel_render","arguments":{"xml_path":"data/xml/factura.xml","logo_path":"data/logos/logo.jpg","out_path":"data/out/factura.pdf"}}}' \
| python servers/fel_mcp_server/server_stdio.py
```

**4. fel_batch:**

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fel_batch","arguments":{"dir_xml":"data/xml","out_dir":"data/out"}}}' \
| python servers/fel_mcp_server/server_stdio.py
```
