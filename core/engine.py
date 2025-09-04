import json
from typing import Any
from anthropic import Anthropic
from mcp_stdio import McpStdioClient, parseTextBlock


def usageDict(resp: Any) -> dict[str, int]:
    """Best-effort extraction of token usage from Anthropic response."""
    u = getattr(resp, "usage", None)
    if not u:
        return {}
    # SDK objects expose attributes; convert to dict shape we print in debug
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }


def serializeBlocks(blocks: list[Any]) -> list[dict[str, Any]]:
    """Convert typed SDK blocks into a JSON-serializable summary for debug."""
    out: list[dict[str, Any]] = []
    for b in blocks or []:
        t = getattr(b, "type", None)
        if t == "text":
            out.append({"type": "text", "text": getattr(b, "text", "")})
        elif t == "tool_use":
            out.append({
                "type": "tool_use",
                "id": getattr(b, "id", ""),
                "name": getattr(b, "name", ""),
                "input": getattr(b, "input", {}) or {},
            })
        elif t == "tool_result":
            out.append({
                "type": "tool_result",
                "tool_use_id": getattr(b, "tool_use_id", ""),
                "content": getattr(b, "content", None),
                "is_error": getattr(b, "is_error", False),
            })
    return out


def buildAnthropicTools(toolsCatalog: dict) -> list[dict]:
    """Convert MCP tools to Anthropic tool descriptors (reuse the same JSON Schemas)."""
    tools: list[dict] = []
    for t in toolsCatalog["result"]["tools"]:
        tools.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "input_schema": t["inputSchema"],
        })
    return tools


def isPathAllowed(pathStr: str, allowedRoots: list[str]) -> bool:
    """Allow only paths under allowedRoots (minimal hardening)."""
    import os
    ap = os.path.abspath(pathStr)
    for root in allowedRoots:
        base = os.path.abspath(root)
        if ap == base or ap.startswith(base + os.sep):
            return True
    return False


def sanitizeMcpArgs(args: dict, allowedRoots: list[str]) -> dict:
    """Validate/sanitize MCP tool arguments (paths)."""
    if not isinstance(args, dict):
        return {}
    for key in ["xml_path", "logo_path", "out_path", "dir_xml", "out_dir"]:
        if key in args and args[key]:
            if not isPathAllowed(str(args[key]), allowedRoots):
                raise ValueError(f"Blocked path: {args[key]}")
    return args


def contentBlocksToParams(blocks: list[Any]) -> list[dict]:
    """Convert typed SDK blocks to ContentBlockParam dicts for messages.create."""
    out: list[dict] = []
    for b in blocks or []:
        t = getattr(b, "type", None)
        if t == "text":
            out.append({"type": "text", "text": getattr(b, "text", "")})
        elif t == "tool_use":
            out.append({
                "type": "tool_use",
                "id": getattr(b, "id", ""),
                "name": getattr(b, "name", ""),
                "input": getattr(b, "input", {}) or {},
            })
    return out


class ChatEngine:
    """
    UI-agnostic orchestration layer:
      - Holds Anthropic client + MCP client
      - Exposes listTools(), callTool(), chatTurn() for any frontend (CLI/Web)
      - Returns debug bundles to let the UI render traces

    Usage:
      engine = ChatEngine(apiKey, model, mcpCmd, systemPrompt, allowedRoots, routerDebug=True)
      engine.start()
      res = engine.chatTurn(history, "generate pdf ...")
      engine.stop()
    """

    def __init__(
        self,
        apiKey: str,
        model: str,
        mcpCmd: str,
        systemPrompt: str,
        allowedRoots: list[str] | None = None,
        routerDebug: bool = True,
    ):
        self.client = Anthropic(api_key=apiKey)
        self.model = model
        self.systemPrompt = systemPrompt
        self.routerDebug = routerDebug
        self.allowedRoots = allowedRoots or ["data/xml", "data/out", "data/logos"]

        self.mcp = McpStdioClient(mcpCmd)
        self.toolsCatalog: dict = {}

    # lifecycle
    def start(self) -> None:
        self.mcp.start()
        self.toolsCatalog = self.mcp.listTools()

    def stop(self) -> None:
        self.mcp.stop()

    # utilities
    def listTools(self) -> dict:
        return self.toolsCatalog

    def callTool(self, name: str, args: dict[str, Any]) -> Any:
        safe = sanitizeMcpArgs(args or {}, self.allowedRoots)
        return parseTextBlock(self.mcp.callTool(name, safe))

    # main chat turn with auto-tools
    def chatTurn(self, history: list[dict], userText: str, maxHops: int = 3) -> dict[str, Any]:
        """
        Returns:
          {
            "finalText": str,
            "router": { "trace": [ {decision, blocks, usage}, ... ] },
            "tools":  { "calls": [ {tool, arguments, result|error}, ... ] }
          }
        """
        tools = buildAnthropicTools(self.toolsCatalog)
        messages = history + [{"role": "user", "content": userText}]
        trace: list[dict[str, Any]] = []
        toolCalls: list[dict[str, Any]] = []

        for _ in range(maxHops):
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=800,
                tools=tools,
                tool_choice={"type": "auto"},
                messages=messages,
                temperature=0,
                system=self.systemPrompt,
            )
            blocks = list(resp.content or [])
            usage = usageDict(resp)

            toolUses = [b for b in blocks if getattr(b, "type", None) == "tool_use"]
            textBlocks = [getattr(b, "text", "") for b in blocks if getattr(b, "type", None) == "text"]

            # trace this hop
            decision = "tool_use" if toolUses else "no_tool"
            if self.routerDebug:
                trace.append({
                    "decision": decision,
                    "blocks": serializeBlocks(blocks),
                    "usage": usage
                })

            if toolUses:
                # execute all requested tools
                assistantParams = contentBlocksToParams(blocks)
                resultsForModel: list[dict] = []

                for tu in toolUses:
                    toolName = getattr(tu, "name", "")
                    toolArgs = getattr(tu, "input", {}) or {}
                    toolUseId = getattr(tu, "id", "")

                    try:
                        safeArgs = sanitizeMcpArgs(toolArgs, self.allowedRoots)
                        rawResp = self.mcp.callTool(toolName, safeArgs)
                        parsed = parseTextBlock(rawResp)

                        resultsForModel.append({
                            "type": "tool_result",
                            "tool_use_id": toolUseId,
                            "content": [{"type": "text", "text": json.dumps(parsed, ensure_ascii=False)}],
                        })
                        toolCalls.append({"tool": toolName, "arguments": safeArgs, "result": parsed})
                    except Exception as e:
                        resultsForModel.append({
                            "type": "tool_result",
                            "tool_use_id": toolUseId,
                            "content": [{"type": "text", "text": json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)}],
                            "is_error": True,
                        })
                        toolCalls.append({"tool": toolName, "arguments": toolArgs, "error": str(e)})

                # feed results back and continue
                messages.append({"role": "assistant", "content": assistantParams})
                messages.append({"role": "user", "content": resultsForModel})
                # Small nudge to keep answers short & in user's language
                messages.append({"role": "user", "content": "Return one concise answer in the user's language; do not show raw JSON."})
                continue

            # finalize with the text we have
            finalText = "\n".join([t for t in textBlocks if t]).strip() or "(no answer)"
            return {"finalText": finalText, "router": {"trace": trace}, "tools": {"calls": toolCalls}}

        # safeguard
        return {"finalText": "(no answer)", "router": {"trace": trace}, "tools": {"calls": toolCalls}}
