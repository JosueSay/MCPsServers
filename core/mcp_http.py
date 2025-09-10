import requests
import json
import uuid
from .rpc_logger import logRPC

class McpHttpClient:
    """
    Minimal HTTP client for communicating with a remote MCP server
    using JSON-RPC over HTTP.
    """

    def __init__(self, base_url: str):
        """
        Initialize the HTTP client.
        
        Args:
            base_url (str): Base URL of the MCP server.
        """
        self.base_url = base_url.rstrip("/")   # Ensure no trailing slash
        self.session = requests.Session()      # Reuse HTTP session
        self.tools_cache = {}                  # Cache for tools list

    def rpc(self, method: str, params: dict | None = None) -> dict:
        """
        Perform a JSON-RPC request to the MCP server.

        Args:
            method (str): RPC method name.
            params (dict | None): Optional parameters.

        Returns:
            dict: The 'result' field from the server response.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),  # Unique request ID
            "method": method,
        }
        if params:
            payload["params"] = params

        # Log outgoing request
        logRPC("send", payload)

        # Send HTTP POST request with JSON body
        resp = self.session.post(self.base_url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Log incoming response
        logRPC("recv", data)

        # Raise error if JSON-RPC returned an "error" object
        if "error" in data:
            raise RuntimeError(data["error"])
        return data["result"]

    def start(self):
        """
        Start the client session (no-op for HTTP).
        Calls 'initialize' RPC on the server.
        """
        self.rpc("initialize")

    def stop(self):
        """
        Stop the client session (no-op for HTTP).
        """
        pass

    def listTools(self) -> dict:
        """
        Fetch the list of available tools from the MCP server.
        Results are cached after the first call.

        Returns:
            dict: {"result": <tools list>}
        """
        if not self.tools_cache:
            self.tools_cache = self.rpc("tools/list")
        return {"result": self.tools_cache}

    def callTool(self, name: str, args: dict) -> dict:
        """
        Call a tool exposed by the MCP server.

        Args:
            name (str): Tool name.
            args (dict): Arguments for the tool.

        Returns:
            dict: Standardized result in the same format as stdio backend.
        """
        result = self.rpc("tools/call", {"name": name, "arguments": args})

        # The server response usually looks like:
        # {"content": [{"type": "text","text": "..."}]}
        if "content" in result and result["content"]:
            text = result["content"][0].get("text", "")
        else:
            text = json.dumps(result, ensure_ascii=False)

        # Wrap response to match stdio envelope
        return {"result": {"content": [{"type": "text", "text": text}]}}
