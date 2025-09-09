from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Any, Optional
from .ow_api import getPlayerSummary, getPlayerStats

app = FastAPI()

class RpcReq(BaseModel):
    jsonrpc: str
    id: Optional[Any] = None
    method: str
    params: Optional[dict[str, Any]] = None

def result(id_, payload):
    return {"jsonrpc": "2.0", "id": id_, "result": payload}

def error(id_, code, msg):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}

@app.post("/mcp")
async def mcp(req: RpcReq, _: Request):
    mid = req.id
    try:
        if req.method == "initialize":
            return result(mid, {
                "protocolVersion": "2025-06-18",
                "serverInfo": {"name": "overwatch-http", "version": "0.3.0"},
                "capabilities": {"tools": {"listChanged": True}},
            })

        if req.method == "tools/list":
            return result(mid, {
                "tools": [
                    {
                        "name": "ow_get_player_summary",
                        "description": "Get player stats summary (winrate, kda, damage, healing). platform/gamemode optional.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "playerId": {"type": "string"},
                                "platform": {"type": ["string", "null"], "enum": [None, "pc","xbl","psn","nintendo"]},
                                "gamemode": {"type": ["string", "null"], "enum": [None, "quickplay","competitive"]},
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
                                "playerId": {"type": "string"},
                                "platform": {"type": "string", "enum": ["pc","xbl","psn","nintendo"]},
                                "gamemode": {"type": "string", "enum": ["quickplay","competitive"]},
                                "hero": {"type": ["string", "null"]},
                            },
                            "required": ["playerId","platform","gamemode"]
                        },
                    },
                ]
            })

        if req.method == "tools/call":
            p = req.params or {}
            name = p.get("name"); args = p.get("arguments") or {}
            if name == "ow_get_player_summary":
                data = getPlayerSummary(
                    playerId=args.get("playerId"),
                    platform=args.get("platform"),
                    gamemode=args.get("gamemode"),
                )
                return result(mid, {"content":[{"type":"text","text":__import__("json").dumps(
                    {"ok": True, "endpoint":"summary","playerId":args.get("playerId"),"data":data},
                    ensure_ascii=False
                )}]})
            if name == "ow_get_player_stats":
                data = getPlayerStats(
                    playerId=args.get("playerId"),
                    platform=args.get("platform"),
                    gamemode=args.get("gamemode"),
                    hero=args.get("hero"),
                )
                return result(mid, {"content":[{"type":"text","text":__import__("json").dumps(
                    {"ok": True, "endpoint":"stats","playerId":args.get("playerId"),
                     "platform":args.get("platform"),"gamemode":args.get("gamemode"),
                     "hero":args.get("hero"),"data":data},
                    ensure_ascii=False
                )}]})
            return error(mid, -32601, f"Unknown tool {name}")

        return error(mid, -32601, f"Method not found: {req.method}")
    except Exception as e:
        return error(mid, -32001, str(e))
