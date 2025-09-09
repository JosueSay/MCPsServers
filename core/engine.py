import json
from typing import Any, Optional
from anthropic import Anthropic, RateLimitError, APIStatusError
from .mcp_stdio import McpStdioClient, parseTextBlock
from .mcp_http import McpHttpClient

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
    • Hold both Anthropic client and one or more MCP stdio clients.
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
        mcpCmd: str | None,
        systemPrompt: str,
        allowedRoots: list[str] | None = None,
        routerDebug: bool = True,
        mcpCmds: list[str] | None = None,
        mcpUrl: str | None = None,
    ):
        self.client = Anthropic(api_key=apiKey)
        self.model = model
        self.systemPrompt = systemPrompt
        self.routerDebug = routerDebug
        self.allowedRoots = allowedRoots or ["data/xml", "data/out", "data/logos"]

        # STDIO clients
        cmds = mcpCmds or ([mcpCmd] if mcpCmd else [])
        self.stdioClients: list[McpStdioClient] = [McpStdioClient(c) for c in cmds]
        
        # HTTP client
        self.httpClient: Optional[McpHttpClient] = McpHttpClient(mcpUrl) if mcpUrl else None
        
        # Catalog
        self.toolsCatalog: dict = {}               # merged catalog across all MCPs
        self._toolIndex: dict[str, McpStdioClient] = {}  # tool name -> client

    # ---------- lifecycle ----------

    def start(self) -> None:
        """Launch all MCP servers and merge their tools into one catalog."""
        merged = {"tools": []}

        # 1) STDIO
        for cli in self.stdioClients:
            cli.start()
            tc = cli.listTools()
            for t in tc.get("result", {}).get("tools", []):
                name = t["name"]
                merged["tools"].append(t)
                self._toolIndex[name] = cli

        # 2) HTTP (no requiere start)
        if self.httpClient:
            tc = self.httpClient.listTools()
            for t in tc.get("result", {}).get("tools", []):
                name = t["name"]
                merged["tools"].append(t)
                self._toolIndex[name] = self.httpClient

        self.toolsCatalog = {"result": merged}

    def stop(self) -> None:
        """Terminate all MCP server processes."""
        for cli in self.stdioClients:
            cli.stop()

    # ---------- utilities ----------

    def listTools(self) -> dict:
        """Return the cached merged MCP tools catalog."""
        return self.toolsCatalog

    def callTool(self, name: str, args: dict[str, Any]) -> Any:
        """
        Invoke an MCP tool manually.
        Returns a parsed Python object when the tool returns JSON text;
        otherwise returns the raw string.
        """
        cli = self._toolIndex.get(name)
        if not cli:
            raise ValueError(f"Unknown tool: {name}")
        safe = sanitizeMcpArgs(args or {}, self.allowedRoots)
        return parseTextBlock(cli.callTool(name, safe))

    # ---------- main chat turn with native tool-use ----------

    def chatTurn(self, history: list[dict], userText: str, maxHops: int = 3) -> dict[str, Any]:
        """
        Perform one conversational turn with tool-use enabled.

        Flow
        ----
        1) Send user message + available tools. Model may emit 'tool_use' blocks.
        2) If 'tool_use' appears, call MCP, append 'tool_result' blocks, and loop.
        3) When no more tools are requested, return the final assistant text.

        Returns
        -------
        dict with:
          • finalText (assistant's reply without raw JSON)
          • router.trace (list of decision hops and usage)
          • tools.calls (tool invocations with arguments/results)
        """
        tools = buildAnthropicTools(self.toolsCatalog)
        messages = history + [{"role": "user", "content": userText}]
        trace: list[dict[str, Any]] = []
        toolCalls: list[dict[str, Any]] = []

        for _ in range(maxHops):
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=800,
                    tools=tools,
                    tool_choice={"type": "auto"},
                    messages=messages,
                    temperature=0,
                    system=self.systemPrompt,
                )

            except RateLimitError as e:
                friendly = ("⚠️ The request exceeded a limit (tokens/minute or size). "
                            "Ask something more specific or reduce the context.")
                # Return a 'final' result so the CLI displays it cleanly
                trace.append({"decision": "error", "error": "rate_limit", "detail": str(e)[:200]})
                return {"finalText": friendly, "router": {"trace": trace}, "tools": {"calls": []}}

            except APIStatusError as e:
                # Other API HTTP status errors
                code = getattr(e, "status_code", "API")
                friendly = f"⚠️ The model could not respond (status {code}). Please try again later."
                trace.append({"decision": "error", "error": "api_status", "detail": str(e)[:200]})
                return {"finalText": friendly, "router": {"trace": trace}, "tools": {"calls": []}}

            except Exception as e:
                # Catch-all final
                friendly = "⚠️ There was a problem generating the response. Please try again."
                trace.append({"decision": "error", "error": "unknown", "detail": str(e)[:200]})
                return {"finalText": friendly, "router": {"trace": trace}, "tools": {"calls": []}}

            blocks = list(resp.content or [])
            usage = usageDict(resp)

            toolUses = [b for b in blocks if getattr(b, "type", None) == "tool_use"]
            textBlocks = [getattr(b, "text", "") for b in blocks if getattr(b, "type", None) == "text"]

            # record router hop (only if debugging enabled)
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
                        cli = self._toolIndex.get(toolName)
                        if not cli:
                            raise ValueError(f"Unknown tool: {toolName}")
                        rawResp = cli.callTool(toolName, safeArgs)
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

                messages.append({"role": "assistant", "content": assistantParams})
                messages.append({"role": "user", "content": resultsForModel})
                # Small nudge: concise answer in user's language, no raw JSON
                messages.append({"role": "user", "content": "Return one concise answer in the user's language; do not show raw JSON."})
                continue

            # No tool request: finalize with aggregated text
            finalText = "\n".join([t for t in textBlocks if t]).strip() or "(no answer)"
            return {"finalText": finalText, "router": {"trace": trace}, "tools": {"calls": toolCalls}}

        # Safety exit if too many hops
        return {"finalText": "(no answer)", "router": {"trace": trace}, "tools": {"calls": toolCalls}}
