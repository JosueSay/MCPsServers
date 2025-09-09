import requests
from typing import Any, Dict, List, Optional

BASE_URL = "https://overfast-api.tekrop.fr"

def get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Generic GET request to Overfast API.
    """
    url = f"{BASE_URL}{path}"
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()

def listGameModes(locale: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch all available game modes.
    Docs: https://overfast-api.tekrop.fr/#tag/Game-Modes/operation/list_gamemodes
    """
    params: Dict[str, Any] = {}
    if locale:
        params["locale"] = locale
    data = get("/gamemodes", params=params)

    return [
        {
            "key": g.get("key"),
            "name": g.get("name"),
            "description": g.get("description"),
        }
        for g in data
    ]

def listRegions(locale: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return static Battle.net API regions (not provided by OverFast).
    Source: Blizzard regionality guide.
    """
    # Minimal, stable set
    data = [
        {"key": "us",   "name": "North America", "locales": ["en_US", "es_MX", "pt_BR", "fr_CA"]},
        {"key": "eu",   "name": "Europe",        "locales": ["en_GB", "es_ES", "fr_FR", "de_DE", "it_IT", "pt_PT", "ru_RU"]},
        {"key": "asia", "name": "Asia",          "locales": ["ko_KR", "zh_TW", "zh_CN", "ja_JP", "en_GB"]},
    ]
    # Optional: filter by locale if provided
    if locale:
        return [r for r in data if locale in r["locales"]]
    return [{ "key": r["key"], "name": r["name"] } for r in data]

def listRoles(locale: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch all available roles.
    Docs: https://overfast-api.tekrop.fr/#tag/Roles/operation/list_roles
    """
    params: Dict[str, Any] = {}
    if locale:
        params["locale"] = locale
    data = get("/roles", params=params)

    return [
        {
            "key": r.get("key"),
            "name": r.get("name"),
            "description": r.get("description"),
        }
        for r in data
    ]

def listMaps(locale: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch all available maps.
    Docs: https://overfast-api.tekrop.fr/#tag/Maps/operation/list_maps
    """
    params: Dict[str, Any] = {}
    if locale:
        params["locale"] = locale
    data = get("/maps", params=params)

    return [
        {
            "key": m.get("key"),
            "name": m.get("name"),
            "location": m.get("location"),
            "gamemodes": m.get("gamemodes"),
            "screenshot": m.get("screenshot"),
        }
        for m in data
    ]
