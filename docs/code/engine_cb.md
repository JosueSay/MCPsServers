# Technical Glossary — `core/engine.py`

Module implementing the **orchestration layer** between:

* **Anthropic client** (`anthropic.Anthropic`) for the Claude LLM.
* **MCP client** (`McpStdioClient`) for FEL tools.

Enables integrating conversation flow with **automatic tool execution** when the model emits `tool_use` blocks.

## Dependencies

* **Standard library**: `json`, `typing.Any`.
* **External SDK**: `anthropic.Anthropic` (official client).
* **Local modules**: `McpStdioClient`, `parseTextBlock` (from `mcp_stdio.py`).

## Utility Functions

### `usageDict(resp: Any) -> dict[str, int]`

**Purpose:** Extract token usage metrics from an SDK response, if available.

**Input:** `resp` (Anthropic response object).

**Output:** dictionary with keys:

```python
{
  "input_tokens": int,
  "output_tokens": int,
  "cache_creation_input_tokens": int,
  "cache_read_input_tokens": int
}
```

Returns `{}` if `.usage` attribute is missing.

### `serializeBlocks(blocks: list[Any]) -> list[dict[str, Any]]`

**Purpose:** Convert typed SDK blocks (`TextBlock`, `ToolUseBlock`, `ToolResultBlock`) into JSON-serializable form.

**Input:** list of response objects.

**Output:** list of dicts with fields `type`, `text` / `id` / `name` / `input` / `tool_use_id` / `content`.

**Use:** logging and debugging traces.

### `buildAnthropicTools(toolsCatalog: dict) -> list[dict]`

**Purpose:** Convert MCP catalog (`tools/list`) into Anthropic tool descriptors.

**Input:** dict with `tools` (each with `name`, `description`, `inputSchema`).

**Output:** list of Anthropic-formatted tools:

```python
[
  {"name": str, "description": str, "input_schema": {...}},
  ...
]
```

### `isPathAllowed(pathStr: str, allowedRoots: list[str]) -> bool`

**Purpose:** Sandbox enforcement -> restrict access to allowed subdirectories.

**Input:** `pathStr` (file path), `allowedRoots` (list of root dirs).

**Logic:** resolves absolute path and checks `startswith(base + os.sep)`.

**Output:** `True` if path is allowed.

### `sanitizeMcpArgs(args: dict, allowedRoots: list[str]) -> dict`

**Purpose:** Validate/sanitize path arguments before invoking MCP tools.

**Input:** dict with possible keys: `xml_path`, `logo_path`, `out_path`, `dir_xml`, `out_dir`.

**Output:** same dict if valid; raises `ValueError` if any path violates sandbox.

### `contentBlocksToParams(blocks: list[Any]) -> list[dict]`

**Purpose:** Convert SDK blocks into `ContentBlockParam` for message API forwarding.

**Filters:** only `text` and `tool_use`.

**Output:** list of dicts with `type`, `text`, or `tool_use` (`id`, `name`, `input`).

## Class `ChatEngine`

### Purpose

UI-agnostic layer centralizing:

* Anthropic client (`self.client`).
* MCP stdio client (`self.mcp`).

Exposed to CLI/Web frontends to:

* list tools (`listTools`),
* invoke tools (`callTool`),
* run conversation turns (`chatTurn`).

### Attributes

* `client`: `Anthropic` instance.
* `model`: string (e.g., `"claude-sonnet-4-20250514"`).
* `systemPrompt`: system prompt.
* `routerDebug`: bool (whether to log traces).
* `allowedRoots`: sandboxed paths.
* `mcp`: stdio client (`McpStdioClient`).
* `toolsCatalog`: cached MCP catalog.

### `__init__(...)`

Receives:

* `apiKey`, `model`, `mcpCmd`, `systemPrompt`.
* `allowedRoots` (default = `["data/xml", "data/out", "data/logos"]`).
* `routerDebug` (default `True`).

Creates Anthropic and MCP clients.

### `start(self) -> None`

* Starts MCP server (`self.mcp.start()`).
* Caches catalog with `self.mcp.listTools()`.

### `stop(self) -> None`

* Stops MCP process (`self.mcp.stop()`).

### `listTools(self) -> dict`

* Returns `self.toolsCatalog` (cached on start).

### `callTool(self, name: str, args: dict[str, Any]) -> Any`

* Sanitizes arguments with `sanitizeMcpArgs`.
* Calls `self.mcp.callTool(name, safe)` -> raw JSON-RPC result.
* Passes through `parseTextBlock` -> tries to decode JSON.
* Returns Python object or string.

### `chatTurn(self, history: list[dict], userText: str, maxHops: int = 3) -> dict[str, Any]`

**Purpose:** Execute a **conversation turn** with native tool-use support.

**Inputs:**

* `history`: list of previous messages (`{"role":..., "content":...}`).
* `userText`: current user input.
* `maxHops`: max iterations (default 3).

**Flow:**

1. Build `messages = history + [userText]`.
2. Prepare `tools = buildAnthropicTools(self.toolsCatalog)`.
3. Call `self.client.messages.create(...)` with:

   * model, `tools`, `tool_choice="auto"`, `system=self.systemPrompt`, etc.
4. Obtain blocks (`resp.content`).
5. Split into:

   * `toolUses`: blocks of type `tool_use`.
   * `textBlocks`: text blocks.
6. If `routerDebug` -> append snapshot to `trace` with `serializeBlocks` + `usageDict`.

**If there are `toolUses`:**

* Convert blocks to `assistantParams`.
* For each `tool_use`:

  * Sanitize args -> call MCP -> parse result.
  * Build `tool_result` block with JSON serialized as text.
  * Record in `toolCalls`.
* Insert into `messages`:

  * `assistantParams` (model’s intent),
  * `resultsForModel` (tool responses),
  * a nudge: `"Return one concise answer in the user's language; do not show raw JSON."`.
* Continue to next hop.

**If no `toolUses`:**

* Concatenate `textBlocks` as `finalText`.
* Return:

```python
{
  "finalText": str,
  "router": {"trace": [...]},   # if debug enabled
  "tools": {"calls": [...]}
}
```

**If `maxHops` exceeded:**

* Returns safe response `"(no answer)"`.

## Example Usage

```python
from core.engine import ChatEngine

engine = ChatEngine(
    apiKey="sk-ant-...",
    model="claude-sonnet-4-20250514",
    mcpCmd="python servers/fel_mcp_server/server_stdio.py",
    systemPrompt="You are a helpful assistant...",
    allowedRoots=["data/xml", "data/out", "data/logos"],
    routerDebug=True,
)

engine.start()

history = []
turn = engine.chatTurn(history, "Validate the invoice data/xml/factura.xml")
print(turn["finalText"])

engine.stop()
```
