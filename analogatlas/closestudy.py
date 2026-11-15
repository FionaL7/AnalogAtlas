"""The close study (#19): 2-3 new Earth analogs, measured up close.

Global screening (85 km tiles) finds candidates; this looks at three of them
the way a field team would, in a 30 x 30 km box at the tile centre:

- radar roughness on both bodies (`radar.py`): Mini-RF CPR on the Moon; on
  Earth, RCM CPR where it exists (Canada) and the Sentinel-1 VH/VV indicator
  everywhere, so the one pair with both shows how the two Earth measures relate
- slope at 30 m from Copernicus GLO-30, ~60x finer than the 1.85 km index
- a cloud-free Sentinel-2 picture of the box

How the pairs were picked (re-checked on the trap-aware ranking, 636b102):
1. Only tiles with `known_analog` null, i.e. >150 km from every site in
   `sites.KNOWN_EARTH_ANALOGS`.
2. Strongest for the permanent-base sites: each Earth tile below is #1 for its
   Moon site among the new results, and in the top 10 for several other
   Artemis regions too.
3. One pair inside RCM coverage, so at least one roughness comparison is CPR on
   both sides. Canada's strongest new tile is #5 for Apollo 11, not a polar
   site: vegetated Canadian tiles fell out of the polar top 10 once #33 pushed
   plants down.

Data access is anonymous: Microsoft Planetary Computer (Sentinel-1, Sentinel-2,
Copernicus DEM) and Canada's RCM archive on AWS.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from . import config as C
from . import radar

HALF_KM = 15.0                  # the 30 km box, same as the Moon sites' radar.json
OUT_DIR = C.INDEX / "close_study"
OUT_JSON = C.INDEX / "close_study.json"

PAIRS: list[dict] = [
    dict(
        id="de-gerlache-puna",
        site="de Gerlache Rim 2",
        earth_tile_id="earth_-26.50_-68.82",
        earth_name="Puna de Atacama, Chile-Argentina border",
        headline="A bare, frozen volcanic high plateau for a sunlit crater rim",
        why_picked=("#1 new Earth analog for de Gerlache Rim 2, Slater Plain and the Peak near "
                    "Cabeus B, and top 10 for all ten Artemis regions. The analog model puts it "
                    "in the top 0.03% of Earth tiles. Caveat: it is ~290 km from the Atacama "
                    "(Yungay) site, in the same wider Atacama-Puna region that Mars studies use; "
                    "new by our 150 km rule, and new as a lunar analog."),
        s1_dates="2025-03-01/2025-05-31",    # austral autumn: dry, before winter snow
        s2_dates="2025-03-01/2025-05-31",
    ),
    dict(
        id="shackleton-ogaden",
        site="Shackleton rim (classic base concept)",
        earth_tile_id="earth_+6.50_+44.95",
        earth_name="Ogaden plateau, Somali Region, Ethiopia",
        headline="A flat, almost featureless plateau for the classic base site",
        why_picked=("#1 new Earth analog for Shackleton rim, Haworth, Malapert Massif, both "
                    "Mons Mouton sites and both Nobile Rims: the most consistent pick across "
                    "the base regions, and top 10 for all ten. Analog model: top 0.3%."),
        s1_dates="2026-01-01/2026-03-15",    # jilal dry season: least green
        s2_dates="2026-01-01/2026-03-15",
    ),
    dict(
        id="apollo11-kivalliq",
        site="Apollo 11 - Mare Tranquillitatis",
        earth_tile_id="earth_+63.50_-98.20",
        earth_name="Kivalliq Region, Nunavut, Canada",
        headline="Low, lake-dotted Arctic shield for a flat mare plain, with true CPR on both sides",
        why_picked=("#5 new Earth analog for Apollo 11 and top 10 for the Mare Tranquillitatis pit. "
                    "The strongest new tile inside free RCM coverage, so its radar comparison "
                    "is CPR against CPR. Analog model: top 5%."),
        rcm_scenes=["kivalliq_20260725", "kivalliq_20260810"],   # snow-free, lakes open
        s1_dates="2026-07-15/2026-08-31",
        s2_dates="2026-07-01/2026-08-31",
    ),
]

# ---- Microsoft Planetary Computer (anonymous) --------------------------------
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_DATA = "https://planetarycomputer.microsoft.com/api/data/v1"
PC_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"
_tokens: dict[str, str] = {}


def _json(url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def pc_search(collection: str, box: tuple[float, float, float, float], dates: str,
              limit: int = 100, **extra) -> list[dict]:
    """STAC items intersecting a (lat_min, lat_max, lon_min, lon_max) box."""
    lat_min, lat_max, lon_min, lon_max = box
    return _json(PC_STAC, dict(collections=[collection], bbox=[lon_min, lat_min, lon_max, lat_max],
                               datetime=dates, limit=limit, **extra))["features"]


def pc_sign(href: str, collection: str) -> str:
    """Append a read token to a blob URL. Tokens are anonymous and cached per run."""
    if collection not in _tokens:
        _tokens[collection] = _json(PC_TOKEN.format(collection=collection))["token"]
    return f"{href}?{_tokens[collection]}"


def contains(item_bbox: list[float], box: tuple[float, float, float, float]) -> bool:
    """Does a STAC [w, s, e, n] bbox contain the whole (lat_min, lat_max, lon_min, lon_max) box?"""
    lat_min, lat_max, lon_min, lon_max = box
    w, s, e, n = item_bbox
    return w <= lon_min and e >= lon_max and s <= lat_min and n >= lat_max


def spread(items: list, n: int) -> list:
    """Up to n items, evenly spaced through the list (dates sorted)."""
    if len(items) <= n:
        return items
    return [items[int(i)] for i in np.linspace(0, len(items) - 1, n)]


# ---- measurements ------------------------------------------------------------
def earth_box(tile: dict) -> tuple[float, float, float, float]:
    return radar.box_around(tile["lat"], tile["lon"], HALF_KM, C.EARTH_KM_PER_DEG)


def s1_roughness(box, dates: str, max_scenes: int = 6) -> radar.RoughnessStat:
    """Sentinel-1 VH/VV over the box: median over up to `max_scenes` dates."""
    items = sorted(pc_search("sentinel-1-rtc", box, dates),
                   key=lambda f: f["properties"]["datetime"])
    items = [f for f in items if {"vv", "vh"} <= set(f["assets"])]
    scenes = [(pc_sign(f["assets"]["vv"]["href"], "sentinel-1-rtc"),
               pc_sign(f["assets"]["vh"]["href"], "sentinel-1-rtc"))
              for f in spread(items, max_scenes)]
    return radar.s1_box(scenes, *box)


def rcm_roughness(box, scene_dirs: list[str]) -> radar.RoughnessStat:
    stats = [radar.rcm_box(C.RAW / "rcm" / d, *box) for d in scene_dirs]
    return radar.combine_scenes(stats, radar.RCM_SOURCE, "cpr")


def slope_deg(z: np.ndarray, dx_m: float, dy_m: float) -> np.ndarray:
    """Slope in degrees from an elevation grid with the given pixel spacing."""
    gy, gx = np.gradient(z, dy_m, dx_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def dem_slope(box) -> dict:
    """Slope at 30 m (Copernicus GLO-30) in the box. The DEM comes in 1x1 deg
    tiles; each is read and sloped separately (edges lose one pixel)."""
    import rasterio
    from rasterio.windows import from_bounds

    lat_min, lat_max, lon_min, lon_max = box
    slopes = []
    for f in pc_search("cop-dem-glo-30", box, "2000-01-01/2030-01-01"):
        with rasterio.open(pc_sign(f["assets"]["data"]["href"], "cop-dem-glo-30")) as src:
            win = from_bounds(lon_min, lat_min, lon_max, lat_max, src.transform)
            win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
            z = src.read(1, window=win).astype(np.float64)
            if src.nodata is not None:
                z[z == src.nodata] = np.nan
            a, e = src.transform.a, src.transform.e
        if min(z.shape) < 3:
            continue
        mid = np.radians((lat_min + lat_max) / 2)
        m_per_deg = C.EARTH_KM_PER_DEG * 1000
        s = slope_deg(z, a * m_per_deg * np.cos(mid), abs(e) * m_per_deg)
        slopes.append(s[np.isfinite(s)])
    v = np.concatenate(slopes) if slopes else np.array([])
    if v.size == 0:
        return dict(slope_med=None, slope_p90=None, n_pixels=0, source="Copernicus GLO-30")
    return dict(slope_med=round(float(np.median(v)), 2), slope_p90=round(float(np.percentile(v, 90)), 2),
                n_pixels=int(v.size), source="Copernicus DEM GLO-30, 30 m")


def s2_picture(box, dates: str, dest: Path, px: int = 768) -> dict | None:
    """The clearest Sentinel-2 scene covering the whole box, rendered as JPEG."""
    items = pc_search("sentinel-2-l2a", box, dates, limit=50,
                      query={"eo:cloud_cover": {"lt": 10}},
                      sortby=[{"field": "eo:cloud_cover", "direction": "asc"}])
    item = next((f for f in items if contains(f["bbox"], box)), None)
    if item is None:
        return None
    lat_min, lat_max, lon_min, lon_max = box   # square on the ground, so px x px
    q = urllib.parse.urlencode(dict(collection="sentinel-2-l2a", item=item["id"], assets="visual",
                                    asset_bidx="visual|1,2,3", nodata=0))
    url = f"{PC_DATA}/item/bbox/{lon_min},{lat_min},{lon_max},{lat_max}/{px}x{px}.jpg?{q}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as r:
        dest.write_bytes(r.read())
    return dict(file=dest.name, date=item["properties"]["datetime"][:10], item=item["id"],
                cloud_pct=round(float(item["properties"]["eo:cloud_cover"]), 2),
                source="Copernicus Sentinel-2 L2A, 10 m true colour")


def moon_roughness(site: tuple[float, float]) -> radar.RoughnessStat:
    lat, lon = site
    return radar.minirf_box(*radar.box_around(lat, lon, HALF_KM, C.MOON_KM_PER_DEG))
