"""
MCP server over stdio (no SDK).
Implements:
  - initialize
  - tools/list
  - tools/call for: { ow_get_player_summary, ow_get_player_stats }
"""

import sys, json
from typing import Any, Dict
from ow_api import getPlayerSummary, getPlayerStats
from config import ALLOWED_GAMEMODES, ALLOWED_PLATFORMS

# ---------------------------
# JSON-RPC / MCP primitives
# ---------------------------
def sendResponse(msgId: Any, result: Any = None, error: Dict[str, Any] | None = None) -> None:
    """Write a single JSON-RPC response to STDOUT."""
    payload = {"jsonrpc": "2.0", "id": msgId}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def getCapabilities() -> Dict[str, Any]:
    """Return minimal MCP capabilities (tools only)."""
    return {
        "protocolVersion": "2025-06-18",
        "serverInfo": {"name": "overwatch-stdio", "version": "0.3.0"},
        "capabilities": {"tools": {"listChanged": True}},
    }


def listTools() -> Dict[str, Any]:
    """Describe available tools and their JSON Schemas."""
    return {
        "tools": [
            {
                "name": "ow_get_player_summary",
                "description": "Get player stats summary (winrate, kda, damage, healing). platform/gamemode are optional.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "playerId": {"type": "string", "description": "Battletag (Foo#1234 or Foo-1234)"},
                        "platform": {"type": ["string", "null"], "enum": [None] + ALLOWED_PLATFORMS},
                        "gamemode": {"type": ["string", "null"], "enum": [None] + ALLOWED_GAMEMODES},
                    },
                    "required": ["playerId"]
                },
            },
            {
                "name": "ow_get_player_stats",
                "description": "Get player career-like stats WITH labels. Requires platform and gamemode. Optional hero.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "playerId": {"type": "string", "description": "Battletag (Foo#1234 or Foo-1234)"},
                        "platform": {"type": "string", "enum": ALLOWED_PLATFORMS},
                        "gamemode": {"type": "string", "enum": ALLOWED_GAMEMODES},
                        "hero": {"type": ["string", "null"], "description": "Optional hero key"},
                    },
                    "required": ["playerId", "platform", "gamemode"]
                },
            },
        ]
    }


# ---------------------------
# Business logic wrappers
# ---------------------------
def callTool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a tools/call to the correct Overwatch operation."""
    if name == "ow_get_player_summary":
        playerId = args.get("playerId")
        platform = args.get("platform")
        gamemode = args.get("gamemode")
        if not playerId:
            raise ValueError("playerId is required")

        data = getPlayerSummary(playerId=playerId, platform=platform, gamemode=gamemode)
        return {"ok": True, "endpoint": "summary", "playerId": playerId, "data": data}

    if name == "ow_get_player_stats":
        playerId = args.get("playerId")
        platform = args.get("platform")
        gamemode = args.get("gamemode")
        hero = args.get("hero") or None
        if not playerId:
            raise ValueError("playerId is required")
        if platform not in ALLOWED_PLATFORMS:
            raise ValueError(f"platform must be one of {ALLOWED_PLATFORMS}")
        if gamemode not in ALLOWED_GAMEMODES:
            raise ValueError(f"gamemode must be one of {ALLOWED_GAMEMODES}")

        data = getPlayerStats(playerId=playerId, platform=platform, gamemode=gamemode, hero=hero)
        return {
            "ok": True,
            "endpoint": "stats",
            "playerId": playerId,
            "platform": platform,
            "gamemode": gamemode,
            "hero": hero,
            "data": data,
        }

    raise ValueError(f"Unknown tool {name}")


# ---------------------------
# Main JSON-RPC loop (stdio)
# ---------------------------
def main() -> None:
    """
    Main stdio loop:
      - parse one JSON-RPC request per line
      - route to MCP methods
      - write JSON-RPC response
      - ignore notifications (messages without "id")
    """
    for line in sys.stdin:
        try:
            req = json.loads(line)
            method = req.get("method")
            msgId = req.get("id", None)

            if msgId is None:
                # notifications: do not respond
                continue

            if method == "initialize":
                sendResponse(msgId, getCapabilities()); continue

            if method == "tools/list":
                sendResponse(msgId, listTools()); continue

            if method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                arguments = params.get("arguments", {}) or {}
                try:
                    result = callTool(name, arguments)
                    sendResponse(
                        msgId,
                        {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
                    )
                except Exception as e:
                    sendResponse(msgId, error={"code": -32001, "message": str(e)})
                continue

            sendResponse(msgId, error={"code": -32601, "message": f"Method not found: {method}"})

        except Exception as e:
            # Only respond if request had an id
            try:
                _id = req.get("id", None) if isinstance(req, dict) else None
            except Exception:
                _id = None
            if _id is not None:
                sendResponse(_id, error={"code": -32000, "message": str(e)})


if __name__ == "__main__":
    main()
