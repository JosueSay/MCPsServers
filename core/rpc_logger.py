import os, json
from datetime import datetime
from .settings import LOG_RPC

session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
SESSION_FILE = f"mcp_rpc_{session_id}.jsonl"

os.makedirs(LOG_RPC, exist_ok=True)

def logRPC(direction: str, data: dict, filename: str = SESSION_FILE):
    """
    Save JSON-RPC messages into a JSONL file.

    Args:
        direction (str): "send", "recv" or "recv_raw".
        data (dict): JSON-RPC payload.
        filename (str): File name inside LOG_RPC (default = session file).
    """
    ts = datetime.utcnow().isoformat()
    with open(os.path.join(LOG_RPC, filename), "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "time": ts,
            "direction": direction,
            "data": data
        }, ensure_ascii=False) + "\n")