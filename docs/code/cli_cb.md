# Technical Glossary — `apps/cli/chat.py`

CLI **frontend** (thin UI layer) for conversing with Claude and **using MCP tools** from the console.
Renders a **REPL**, delegates orchestration to `core.engine.ChatEngine`, and if `ROUTER_DEBUG=1`, displays **traces** and **tool summaries**.

## Purpose and Scope

* Provide a minimal command-line interface.
* List MCP tools, invoke them manually, or let the LLM choose automatically.
* Record each session in **JSONL** under `LOG_SESSION` and rpc in `LOG_RPC`.

## Key Dependencies

* **Stdlib**: `os`, `sys`, `json`, `uuid`, `datetime`, `pathlib`, `typing.Any`.
* **Third-party**: `python-dotenv` (`load_dotenv`), `rich` (console, tables, markdown).
* **Local modules**: `core.engine.ChatEngine`, `core.settings` (API key and configuration).

## REPL Commands

* `/tools` -> display MCP catalog in a table.
* `/clear` -> clear the short session history (context).
* `/exit` or `/quit` -> terminate the session.
* **Optional manual shortcuts**:

  * `fel_validate <xml>`
  * `fel_render <xml> [logo] [theme] [out]`
  * `fel_batch  <dir_xml> [out_dir]`
* Any other text is sent to the **LLM**, which decides whether to use tools.

## Environment Variables Used

From `core.settings`: `API_KEY`, `MODEL`, `MCP_FEL_CMD`, `LOG_SESSION`, `LOG_RPC`, `ROUTER_DEBUG`, `SYSTEM_PROMPT`, `ALLOWED_ROOTS`.
Program **fails fast** if `ANTHROPIC_API_KEY` is missing.

## Structure and Functions

### 1. Load & Setup

* Adjust `sys.path` to allow `import core.*` when executed from the project root.
* `load_dotenv()` to read `.env`.
* Construct `rich.Console()`.
* **Validate API Key** and create per-session log file:

  `logs/sessions/<YYYYMMDD-HHMMSS-<id>>.jsonl`.

### 2. `logEvent(event: dict) -> None`

**Purpose:** append structured events (JSON) to the **session log**.

**I/O:** writes one JSONL line per event.

### 3. `printJsonBlock(obj: Any) -> None`

**Purpose:** render objects/strings as a `json` block in the console using `rich`.

**Use:** display tool results or traces.

### 4. `readUserInput(prompt: str = "[bold cyan]You[/] › ") -> str`

**Purpose:** read **one** line of user input with styled prompt.

**Behavior:** returns sentinel `"__EXIT__"` if user enters `/exit` or `/quit`.

### 5. `printToolsPretty(toolsCatalog: dict) -> None`

**Purpose:** display MCP tool table (`name | description | required args`).

**Detail:** extracts `required` from `inputSchema` (JSON Schema).

### 6. `main() -> None`

**Role:** main **interactive loop**.

**Flow:**

1. Banner + command listing.
2. Instantiate `ChatEngine(...)` with config from `core.settings` and call `engine.start()`.
3. Maintain a **short history** `history: list[dict[str, Any]]` (text only).
4. Read loop:

   * `"/clear"` -> clear history.
   * `"/tools"` -> list tools (`engine.listTools()`), print and log `{"type":"mcp","op":"tools/list",...}`.
   * **Manual shortcuts**:

     * `fel_validate <xml>` -> `engine.callTool("fel_validate", {"xml_path": ...})`.
     * `fel_render <xml> [logo] [theme] [out]` -> build args, call tool.
     * `fel_batch  <dir_xml> [out_dir]` -> same.
       Results -> `printJsonBlock(...)` + `logEvent(...)`.
   * **Free turn**: send text to LLM via `engine.chatTurn(history, user)`.

     * If `ROUTER_DEBUG`:

       * Print `{"source":"router","trace":[...]}` with `serializeBlocks` and usage.
       * If automatic tools used, print `{"source":"tools","calls":[...]}`.
     * Print final response `turn["finalText"]` with `Markdown`.
     * Log: `{"type":"llm_auto", "model": MODEL, "input": user, "output": final}`.
     * Update `history` (user + assistant).
5. `KeyboardInterrupt` -> message, then `finally: engine.stop()`; display log path.

## Interaction with `ChatEngine`

* CLI **does not** call LLM directly; everything goes through `ChatEngine`.
* `engine.callTool(...)` applies **path sandboxing** and parses MCP response (JSON text -> object).
* `engine.chatTurn(...)` enables **automatic tool-use** with `tool_choice="auto"` and optional traces.

## Logging (JSONL format)

Example events:

* `{"type":"mcp","op":"tools/list", "result": {...}}`
* `{"type":"mcp_manual","tool":"fel_render","args":{...},"result":{...}}`
* `{"type":"llm_auto","model": "...","input": "...","output": "..."}`

Written to `LOG_SESSION` and optionally rendered in the console.

## Errors and Handling

* Missing `API_KEY` -> abort with `[red]Missing ANTHROPIC_API_KEY[/red]`.
* MCP errors in shortcuts -> print `[red]MCP error:[/red] ...` and log as `mcp_manual_error`.
* `finally` ensures `engine.stop()` closes the MCP subprocess.
