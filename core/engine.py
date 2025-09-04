import json
from typing import Any
from anthropic import Anthropic
from .mcp_stdio import McpStdioClient, parseTextBlock


def usageDict(resp: Any) -> dict[str, int]:
    """
    Best-effort extraction of token usage from an Anthropic SDK response.

    Returns a compact dict (safe to log):
      {
        "input_tokens": int,
        "output_tokens": int,
        "cache_creation_input_tokens": int,
        "cache_read_input_tokens": int
      }
    """
    u = getattr(resp, "usage", None)
    if not u:
        return {}
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }


def serializeBlocks(blocks: list[Any]) -> list[dict[str, Any]]:
    """
    Convert typed SDK blocks (TextBlock, ToolUseBlock, ToolResultBlock) into a
    JSON-serializable summary, suitable for debug output and logs.
    """
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
    """
    Convert MCP tools into Anthropic tool descriptors.
    Reuses the MCP JSON Schemas directly in 'input_schema'.
    """
    tools: list[dict] = []
    for t in toolsCatalog["result"]["tools"]:
        tools.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "input_schema": t["inputSchema"],
        })
    return tools


def isPathAllowed(pathStr: str, allowedRoots: list[str]) -> bool:
    """
    Basic path sandbox: allow only files within any of the given roots.
    Use absolute paths to avoid traversal tricks.
    """
    import os
    ap = os.path.abspath(pathStr)
    for root in allowedRoots:
        base = os.path.abspath(root)
        if ap == base or ap.startswith(base + os.sep):
            return True
    return False


def sanitizeMcpArgs(args: dict, allowedRoots: list[str]) -> dict:
    """
    Validate/sanitize file path arguments for MCP calls.
    Raises ValueError on disallowed paths.
    """
    if not isinstance(args, dict):
        return {}
    for key in ["xml_path", "logo_path", "out_path", "dir_xml", "out_dir"]:
        if key in args and args[key]:
            if not isPathAllowed(str(args[key]), allowedRoots):
                raise ValueError(f"Blocked path: {args[key]}")
    return args


def contentBlocksToParams(blocks: list[Any]) -> list[dict]:
    """
    Convert typed SDK blocks to ContentBlockParam dicts that can be sent
    back to the Messages API. We only forward 'text' and 'tool_use' blocks.
    """
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
    UI-agnostic orchestration layer for Anthropic + MCP.

    Responsibilities
    ----------------
    • Hold both Anthropic client and an MCP stdio client.
    • Expose listTools(), callTool(), and chatTurn() to any frontend (CLI/Web).
    • Return debug bundles (router trace, tool calls) so the UI can render diagnostics.

    Typical usage
    -------------
        engine = ChatEngine(apiKey, model, mcpCmd, systemPrompt, allowedRoots, routerDebug=True)
        engine.start()
        result = engine.chatTurn(history, "generate pdf ...")
        engine.stop()

    chatTurn() returns:
        {
          "finalText": str,
          "router": { "trace": [ {decision, blocks, usage}, ... ] },
          "tools":  { "calls": [ {tool, arguments, result|error}, ... ] }
        }
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

    # ---------- lifecycle ----------

    def start(self) -> None:
        """Launch MCP server and cache its tools catalog."""
        self.mcp.start()
        self.toolsCatalog = self.mcp.listTools()

    def stop(self) -> None:
        """Terminate MCP server process."""
        self.mcp.stop()

    # ---------- utilities ----------

    def listTools(self) -> dict:
        """Return the cached MCP tools catalog."""
        return self.toolsCatalog

    def callTool(self, name: str, args: dict[str, Any]) -> Any:
        """
        Invoke an MCP tool manually.
        Returns a parsed Python object when the tool returns JSON text;
        otherwise returns the raw string.
        """
        safe = sanitizeMcpArgs(args or {}, self.allowedRoots)
        return parseTextBlock(self.mcp.callTool(name, safe))

    # ---------- main chat turn with native tool-use ----------

    def chatTurn(self, history: list[dict], userText: str, maxHops: int = 3) -> dict[str, Any]:
        """
        One conversational turn with tool-use enabled.

        Flow
        ----
        1) Send user message + available tools. Model may emit 'tool_use' blocks.
        2) If 'tool_use' appears, call MCP, append 'tool_result' blocks, and loop.
        3) When no more tools are requested, return the final assistant text.

        Returns a dict with final text plus optional traces/tool-call summaries
        (useful for CLI/Web UIs to render debug info).
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
                tool_choice={"type": "auto"},  # let the model decide
                messages=messages,
                temperature=0,
                system=self.systemPrompt,
            )
            blocks = list(resp.content or [])
            usage = usageDict(resp)

            toolUses = [b for b in blocks if getattr(b, "type", None) == "tool_use"]
            textBlocks = [getattr(b, "text", "") for b in blocks if getattr(b, "type", None) == "text"]

            # record router hop (only if debugging)
            if self.routerDebug:
                trace.append({
                    "decision": "tool_use" if toolUses else "no_tool",
                    "blocks": serializeBlocks(blocks),
                    "usage": usage,
                })

            if toolUses:
                # Execute all requested tools and feed results back
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

                        # Serialize tool result as a single text block
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

                messages.append({"role": "assistant", "content": assistantParams})
                messages.append({"role": "user", "content": resultsForModel})
                # Small nudge: concise answer in user's language, no raw JSON
                messages.append({"role": "user", "content": "Return one concise answer in the user's language; do not show raw JSON."})
                continue

            # No tool request: finalize with aggregated text
            finalText = "\n".join([t for t in textBlocks if t]).strip() or "(no answer)"
            return {"finalText": finalText, "router": {"trace": trace}, "tools": {"calls": toolCalls}}

        # Safety if too many hops
        return {"finalText": "(no answer)", "router": {"trace": trace}, "tools": {"calls": toolCalls}}
