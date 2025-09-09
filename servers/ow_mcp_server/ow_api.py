import requests
from typing import Any, Optional
from .config import ALLOWED_GAMEMODES, ALLOWED_PLATFORMS, BASE_URL


def get(path: str, params: Optional[dict[str, Any]] = None) -> Any:
    """Generic GET to Overfast API."""
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()

def normalizePlayerId(playerId: str) -> str:
    """
    Overwatch battletag uses '#' but Overfast expects '-'.
    Example: 'Foo#1234' -> 'Foo-1234'.
    """
    return playerId.strip().replace("#", "-")

# ---- public API ----
def getPlayerSummary(playerId: str,platform: Optional[str] = None, gamemode: Optional[str] = None) -> Any:
    """
    GET /players/{player_id}/stats/summary
    Player statistics summary (winrate, kda, damage, healing, etc.).
    Platform & gamemode are OPTIONAL (by default it merges all).
    Docs: https://overfast-api.tekrop.fr/docs#/Players/get_player_summary_players__player_id__stats_summary_get
    Cache TTL: ~10 minutes (per API docs).
    """
    pid = normalizePlayerId(playerId)
    params: dict[str, Any] = {}

    if platform is not None:
        if platform not in ALLOWED_PLATFORMS:
            raise ValueError(f"Invalid platform '{platform}'. Allowed: {sorted(ALLOWED_PLATFORMS)}")
        params["platform"] = platform

    if gamemode is not None:
        if gamemode not in ALLOWED_GAMEMODES:
            raise ValueError(f"Invalid gamemode '{gamemode}'. Allowed: {sorted(ALLOWED_GAMEMODES)}")
        params["gamemode"] = gamemode

    return get(f"/players/{pid}/stats/summary", params=params)

def getPlayerStats(
    playerId: str, platform: str, gamemode: str, hero: Optional[str] = None) -> Any:
    """
    GET /players/{player_id}/stats
    Career-like stats WITH labels (best for chat explanations).
    Platform & gamemode are REQUIRED. Optional: hero filter.
    Docs: https://overfast-api.tekrop.fr/docs#/Players/get_player_stats_players__player_id__stats_get
    Cache TTL: ~10 minutes (per API docs).
    """
    pid = normalizePlayerId(playerId)

    if platform not in ALLOWED_PLATFORMS:
        raise ValueError(f"Invalid platform '{platform}'. Allowed: {sorted(ALLOWED_PLATFORMS)}")
    if gamemode not in ALLOWED_GAMEMODES:
        raise ValueError(f"Invalid gamemode '{gamemode}'. Allowed: {sorted(ALLOWED_GAMEMODES)}")

    params: dict[str, Any] = {"platform": platform, "gamemode": gamemode}
    if hero:
        params["hero"] = hero  # expects hero key as per API

    return get(f"/players/{pid}/stats", params=params)
