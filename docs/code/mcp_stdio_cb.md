# Technical Glossary — `core/mcp_stdio.py`

Implementation of an **MCP client** over **STDIN/STDOUT** that communicates **line-by-line JSON-RPC** with a server (e.g., `server_stdio.py`).

Allows any Python component to:

* launch an external MCP server,
* initialize it,
* list its tools (`tools/list`),
* invoke a tool (`tools/call`).

## Dependencies

* **Standard library**: `subprocess`, `json`, `threading`, `queue`, `time`, `typing.Any`, `typing.Optional`.
  No external libraries required.

## Class `McpStdioClient`

### Responsibilities

* `start()`: starts the MCP server process, launches a reader thread, and sends `initialize`.
* `stop()`: terminates the process if still running.
* `listTools()`: performs RPC using the `tools/list` method.
* `callTool(name, args)`: performs RPC using the `tools/call` method.

### Design

* Uses a **background thread** (`pumpStdout`) to continuously read server output and push each raw line into a queue (`queue.Queue`).
* `rpc()` writes a JSON-RPC request to `stdin` and waits in the queue until a JSON with the matching `id` appears.
* Handles non-JSON lines or extra messages in the server’s `stdout`.
* Assumes **only one request in flight at a time** in this minimal implementation.

### `__init__(self, cmd: str, startupTimeoutSec: float = 8.0)`

* **cmd**: command to execute the server (e.g., `"python servers/fel_mcp_server/server_stdio.py"`).
* **startupTimeoutSec**: seconds to wait for a response (default 8.0).
* Initializes: `proc=None`, `outQ=queue.Queue()`, `_id=0`, `_lock=threading.Lock()`.

### `start(self) -> None`

* Launches the server (`subprocess.Popen`) with `stdin`, `stdout`, `stderr` connected (text mode, line-buffered).
* Starts a **daemon thread** with `pumpStdout` to capture each line from the server `stdout`.
* Sends an initial `initialize` request using `rpc()`.
* **Output**: `None`.

### `stop(self) -> None`

* If `proc` is alive, attempts to terminate it with `terminate()`.
* Ignores errors.
* **Output**: `None`.

### `listTools(self) -> dict[str, Any]`

* Constructs a JSON-RPC payload:

```json
{ "jsonrpc":"2.0", "id":<id>, "method":"tools/list" }
```

* Sends it via `rpc()` and returns the parsed response as a dictionary.
