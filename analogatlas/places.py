"""Human place names for Earth tiles ("Catamarca, Argentina"), so the app can
say where a candidate is instead of printing raw coordinates.

Names come from OpenStreetMap's Nominatim reverse geocoder and are cached in
`place_names.json` next to this file, which is committed: the export and the
deploy read the cache only and never touch the network. Fill it with

    python scripts/03_export.py --geocode

which looks up only the tiles not cached yet, at most one request a second
(Nominatim's usage policy). A tile with no name (open ocean, a geocoder miss)
is cached as null and the app falls back to its coordinates.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(__file__).with_name("place_names.json")
URL = "https://nominatim.openstreetmap.org/reverse"
# Generic on purpose: no personal or project contact details leave the machine.
USER_AGENT = "AnalogAtlas-export"
MIN_INTERVAL_S = 1.1

_cache: dict[str, str | None] | None = None
_last_call = 0.0


def key(lat: float, lon: float) -> str:
    return f"{lat:.2f},{lon:.2f}"


def _load() -> dict[str, str | None]:
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    return _cache


def _save() -> None:
    CACHE.write_text(json.dumps(dict(sorted(_load().items())), indent=1, ensure_ascii=False) + "\n",
                     encoding="utf-8")


def name(lat: float, lon: float) -> str | None:
    """The cached name, or None. Never calls the network."""
    return _load().get(key(lat, lon))


def _format(address: dict) -> str | None:
    """State-level name plus country: specific enough to place it, short enough for a list."""
    country = address.get("country")
    local = next((address[k] for k in ("state", "region", "state_district", "county", "archipelago")
                  if address.get(k)), None)
    parts = [p for p in (local, country) if p]
    return ", ".join(dict.fromkeys(parts)) or None


def _reverse(lat: float, lon: float, zoom: int) -> dict | None:
    global _last_call
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    q = urllib.parse.urlencode(dict(format="jsonv2", lat=f"{lat:.4f}", lon=f"{lon:.4f}",
                                    zoom=zoom, **{"accept-language": "en"}))
    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    finally:
        _last_call = time.monotonic()
    return None if "error" in body else body


def lookup(lat: float, lon: float) -> str | None:
    """Reverse-geocode one point (state level, then country level)."""
    for zoom in (8, 3):
        hit = _reverse(lat, lon, zoom)
        if hit and (label := _format(hit.get("address") or {})):
            return label
    # Nominatim has no admin areas on the ice sheet.
    return "Antarctica" if lat <= -60 else None


def fill(points: list[tuple[float, float]]) -> int:
    """Look up every point not cached yet and save. Returns how many were fetched."""
    cache = _load()
    todo = list(dict.fromkeys(key(la, lo) for la, lo in points if key(la, lo) not in cache))
    for n, k in enumerate(todo, 1):
        la, lo = map(float, k.split(","))
        try:
            cache[k] = lookup(la, lo)
        except OSError as e:          # network trouble: leave it uncached, try next run
            print(f"  ! place name failed for {k}: {e}")
            continue
        if n % 20 == 0:
            print(f"  place names: {n}/{len(todo)}")
            _save()
    if todo:
        _save()
    return len(todo)
