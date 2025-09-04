"""
Minimal JSON-RPC client for an MCP server over stdio.
- Spawns the MCP server process
- Sends one JSON-RPC request per line
- Returns the matching response

Public API:
  McpStdioClient.start()
  McpStdioClient.stop()
  McpStdioClient.listTools()
  McpStdioClient.callTool(name, arguments)
  prettyJsonFromMcpResult(resp)
"""

import json
import queue
import threading
import subprocess
from typing import Any, Dict, Optional


class McpStdioClient:
    """Tiny stdio JSON-RPC client for MCP servers."""
    def __init__(self, cmd: str):
        self.cmd = cmd
        self.proc: Optional[subprocess.Popen[str]] = None
        self.readerThread: Optional[threading.Thread] = None
        self.outQueue: "queue.Queue[dict]" = queue.Queue()
        self.msgId = 0

    def start(self) -> None:
        """Spawn the MCP server and perform initialize handshake."""
        if self.proc:
            return
        self.proc = subprocess.Popen(
            self.cmd.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,   # line-buffered
        )

        def readerLoop() -> None:
            assert self.proc and self.proc.stdout
            for line in self.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception as e:
                    obj = {"jsonrpc": "2.0", "error": {"code": -32700, "message": f"parse error: {e}; line={line}"}}
                self.outQueue.put(obj)

        self.readerThread = threading.Thread(target=readerLoop, daemon=True)
        self.readerThread.start()

        # Basic handshake
        _ = self.sendRequest("initialize", {})

    def stop(self) -> None:
        """Terminate the MCP server process."""
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

    def sendRequest(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for the response with the same id."""
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("MCP process not started")
        self.msgId += 1
        req = {"jsonrpc": "2.0", "id": self.msgId, "method": method, "params": params}
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

        while True:
            resp = self.outQueue.get()
            if isinstance(resp, dict) and resp.get("id") == self.msgId:
                return resp

    def listTools(self) -> Dict[str, Any]:
        """Return the MCP server tools description."""
        return self.sendRequest("tools/list", {})

    def callTool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a single MCP tool with arguments."""
        return self.sendRequest("tools/call", {"name": name, "arguments": arguments})


def prettyJsonFromMcpResult(resp: Dict[str, Any]) -> str:
    """
    Extract inner JSON from MCP tools/call envelope:
      result.content[0].text is a JSON string.
    Returns pretty-printed JSON text for terminal display.
    """
    try:
        content = resp["result"]["content"]
        if content and content[0].get("type") == "text":
            inner = content[0]["text"]
            parsed = json.loads(inner)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        return json.dumps(resp, ensure_ascii=False, indent=2)
    except Exception:
        return json.dumps(resp, ensure_ascii=False, indent=2)