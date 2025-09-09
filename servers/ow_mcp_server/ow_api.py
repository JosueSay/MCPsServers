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
    Fetch all available regions.
    Docs: https://overfast-api.tekrop.fr/#tag/Regions/operation/list_regions
    """
    params: Dict[str, Any] = {}
    if locale:
        params["locale"] = locale
    data = get("/regions", params=params)

    return [
        {
            "key": r.get("key"),
            "name": r.get("name"),
        }
        for r in data
    ]

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
