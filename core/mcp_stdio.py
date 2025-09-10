import subprocess
import json
import threading
import queue
import time
from typing import Any, Optional
from .rpc_logger import logRPC

class McpStdioClient:
    """
    JSON-RPC (line-delimited) client for an MCP server over stdio.

    Responsibilities
    ---------------
    • start(): launch the server process and perform 'initialize'
    • stop():  terminate the process
    • listTools(): JSON-RPC 'tools/list'
    • callTool(name, arguments): JSON-RPC 'tools/call'

    Design notes
    ------------
    • A background thread continuously reads server stdout and pushes lines into a queue.
    • rpc() pulls lines, discarding non-JSON or JSON without a matching 'id'. This allows
      the server to print diagnostics to stdout without breaking the protocol.
    • Intended for a single in-flight request at a time in this minimal implementation.
    """

    def __init__(self, cmd: str, startupTimeoutSec: float = 8.0):
        self.cmd = cmd
        self.proc: Optional[subprocess.Popen] = None
        self.outQ: "queue.Queue[str]" = queue.Queue()
        self._id = 0
        self._lock = threading.Lock()
        self.startupTimeoutSec = startupTimeoutSec

    def start(self) -> None:
        """Spawn the MCP server process, start the stdout pump, and send 'initialize'."""
        self.proc = subprocess.Popen(
            self.cmd.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # kept for debugging; not consumed here
            text=True,
            bufsize=1,               # line-buffered
        )
        threading.Thread(target=self.pumpStdout, daemon=True).start()
        _ = self.rpc({"jsonrpc": "2.0", "id": self.nextId(), "method": "initialize", "params": {}})

    def stop(self) -> None:
        """Terminate the process if still running."""
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass

    def listTools(self) -> dict[str, Any]:
        """Call JSON-RPC method 'tools/list' and return the raw JSON response."""
        return self.rpc({
            "jsonrpc": "2.0",
            "id": self.nextId(),
            "method": "tools/list",
        })

    def callTool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call JSON-RPC method 'tools/call' with a tool name and arguments."""
        return self.rpc({
            "jsonrpc": "2.0",
            "id": self.nextId(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })

    # ---------------------- internals ----------------------

    def nextId(self) -> int:
        """Return a new monotonically increasing request id (thread-safe)."""
        with self._lock:
            self._id += 1
            return self._id

    def pumpStdout(self) -> None:
        """
        Continuously read stdout from the server and enqueue raw lines.
        rpc() is responsible for JSON parsing and id correlation.
        """
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            if line:
                self.outQ.put(line)

    def rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Send a single JSON-RPC request to the MCP server (via stdio) and wait for the response.

        Behavior:
        ---------
        • Logs the outgoing request with logRPC("send", payload).
        • Writes the request to the server's stdin.
        • Reads lines from the server's stdout until a valid JSON response with the same 'id' is found.
        • Logs each valid JSON line received with logRPC("recv", data).
        • Non-JSON lines or messages with mismatched 'id' are ignored, allowing the server to emit diagnostics.

        Parameters:
        -----------
        payload : dict
            The JSON-RPC request object, including "jsonrpc", "id", "method", and optional "params".

        Returns:
        --------
        dict
            The JSON-RPC response object matching the request 'id'.

        Raises:
        -------
        TimeoutError
            If no valid response is received within the configured startupTimeoutSec.
        """
        assert self.proc and self.proc.stdin

        # Log outgoing request
        logRPC("send", payload)

        # Send request to the MCP server
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

        deadline = time.time() + self.startupTimeoutSec
        while time.time() < deadline:
            try:
                line = self.outQ.get(timeout=0.5)
            except queue.Empty:
                continue

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # Ignore non-JSON lines
                continue

            # Log all valid JSON messages
            logRPC("recv", data)

            if data.get("id") == payload.get("id"):
                return data

        raise TimeoutError("MCP server did not respond on time.")

def prettyJsonFromMcpResult(result: dict[str, Any]) -> str:
    """
    Extract the first 'text' block from an MCP 'tools/call' envelope.
    Returns the text as-is (may itself be a JSON string).
    """
    content = result.get("result", {}).get("content", [])
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict) and item.get("type") == "text":
            return item.get("text", "")
    return ""


def parseTextBlock(result: dict[str, Any]) -> Any:
    """
    Like prettyJsonFromMcpResult(), but attempts to parse the text as JSON.
    Returns a Python object if parsing succeeds; otherwise returns the raw string.
    """
    raw = prettyJsonFromMcpResult(result)
    try:
        return json.loads(raw)
    except Exception:
        return raw
