import requests
import json
import uuid

class McpHttpClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.tools_cache = {}

    def rpc(self, method: str, params: dict | None = None) -> dict:
        """Enviar JSON-RPC sobre HTTP POST"""
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
        }
        if params:
            payload["params"] = params
        resp = self.session.post(self.base_url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data["result"]

    def start(self):
        # no-op para HTTP
        self.rpc("initialize")

    def stop(self):
        # no-op
        pass

    def listTools(self) -> dict:
        if not self.tools_cache:
            self.tools_cache = self.rpc("tools/list")
        return {"result": self.tools_cache}

    def callTool(self, name: str, args: dict) -> dict:
        result = self.rpc("tools/call", {"name": name, "arguments": args})
        # el server devuelve {"content": [{"type": "text","text": "..."}]}
        if "content" in result and result["content"]:
            text = result["content"][0].get("text", "")
        else:
            text = json.dumps(result, ensure_ascii=False)
        # Devolver con el mismo envelope que stdio:
        return {"result": {"content": [{"type": "text", "text": text}]}}
