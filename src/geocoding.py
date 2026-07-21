"""Address-to-coordinate geocoding via Nominatim (OpenStreetMap)."""

from __future__ import annotations

import requests

from src.geo_analysis import Coordinate

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GeoProfiler/1.0 (local investigative tool)"


def geocode_address(address: str, timeout: float = 5.0) -> Coordinate | None:
    """Look up an address's coordinates via Nominatim. Never raises."""
    if not address.strip():
        return None

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError):
        return None

    if not results:
        return None

    try:
        return Coordinate(latitude=float(results[0]["lat"]), longitude=float(results[0]["lon"]))
    except (KeyError, TypeError, ValueError):
        return None
