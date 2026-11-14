"""Build tile grids for the Moon and Earth and download their image tiles.

Every tile covers roughly the same ground area (~85 x 85 km) on both bodies so
that terrain features are compared at the same physical scale.
"""
from __future__ import annotations

import io
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests
from PIL import Image
from requests.adapters import HTTPAdapter, Retry
from tqdm import tqdm

from . import config as C


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=32))
    s.headers["User-Agent"] = "terramap-hackathon/0.1"
    return s


# ---------------------------------------------------------------- grids ----
def moon_grid() -> pd.DataFrame:
    """Trek WMTS zoom-6 tiles whose centre lies within +/-MOON_MAX_ABS_LAT."""
    z, d = C.MOON_ZOOM, C.MOON_TILE_DEG
    rows = []
    for y in range(2 ** z):
        lat = 90 - (y + 0.5) * d
        if abs(lat) > C.MOON_MAX_ABS_LAT:
            continue
        for x in range(2 ** (z + 1)):
            lon = -180 + (x + 0.5) * d
            rows.append(dict(tile_id=f"moon_{z}_{y}_{x}", body="moon", z=z, y=y, x=x,
                             lat=lat, lon=lon,
                             lat_min=lat - d / 2, lat_max=lat + d / 2,
                             lon_min=lon - d / 2, lon_max=lon + d / 2))
    return pd.DataFrame(rows)


def earth_grid() -> pd.DataFrame:
    """Land-only sample points, ~1 deg apart, each with an ~85 km square box."""
    from global_land_mask import globe

    step, half_lat = C.EARTH_GRID_STEP_DEG, C.EARTH_TILE_DEG_LAT / 2
    rows = []
    for lat in np.arange(-C.EARTH_MAX_ABS_LAT + step / 2, C.EARTH_MAX_ABS_LAT, step):
        coslat = max(math.cos(math.radians(lat)), 0.05)
        lon_step, half_lon = step / coslat, half_lat / coslat
        for lon in np.arange(-180 + lon_step / 2, 180, lon_step):
            # keep the tile if at least half of a 5x5 sub-grid is land
            la = np.linspace(lat - half_lat, lat + half_lat, 5)
            lo = np.linspace(lon - half_lon, lon + half_lon, 5)
            LA, LO = np.meshgrid(la, ((lo + 180) % 360) - 180)
            if globe.is_land(LA, LO).mean() < 0.5:
                continue
            rows.append(dict(tile_id=f"earth_{lat:+.2f}_{lon:+.2f}", body="earth",
                             lat=float(lat), lon=float(lon),
                             lat_min=lat - half_lat, lat_max=lat + half_lat,
                             lon_min=lon - half_lon, lon_max=lon + half_lon))
    return pd.DataFrame(rows)


# --------------------------------------------------------------- fetch -----
def _square_crop(img: Image.Image, lat: float) -> Image.Image:
    """Equirectangular tiles are stretched E-W by 1/cos(lat); crop the centre so
    the tile is square in kilometres, then resize back to TILE_PX."""
    w, h = img.size
    keep = max(int(round(w * math.cos(math.radians(lat)))), 8)
    left = (w - keep) // 2
    return img.crop((left, 0, left + keep, h)).resize((C.TILE_PX, C.TILE_PX), Image.BILINEAR)


def tile_path(body: str, layer: str, tile_id: str):
    ext = "png" if layer == "shade" else "jpg"
    return C.TILES / body / layer / f"{tile_id}.{ext}"


def _fetch_moon(s, row, layer):
    url = C.MOON_LAYERS[layer].format(z=row.z, y=row.y, x=row.x)
    r = s.get(url, timeout=30)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("L")
    return _square_crop(img, row.lat)


def _fetch_earth(s, row, layer):
    params = dict(SERVICE="WMS", REQUEST="GetMap", VERSION="1.3.0", STYLES="",
                  LAYERS=C.EARTH_LAYERS[layer], CRS="EPSG:4326",
                  BBOX=f"{row.lat_min},{row.lon_min},{row.lat_max},{row.lon_max}",
                  WIDTH=C.TILE_PX, HEIGHT=C.TILE_PX, FORMAT="image/jpeg")
    r = s.get(C.GIBS_WMS, params=params, timeout=30)
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image"):
        raise RuntimeError(r.text[:200])
    img = Image.open(io.BytesIO(r.content))
    return img.convert("L" if layer == "shade" else "RGB")


def fetch_tiles(grid: pd.DataFrame, layers=("img", "shade"), workers: int = 12) -> list[str]:
    """Download every (tile, layer) that is not on disk yet. Returns failures."""
    s = _session()
    jobs = []
    for layer in layers:
        (C.TILES / grid.body.iloc[0] / layer).mkdir(parents=True, exist_ok=True)
        for row in grid.itertuples():
            p = tile_path(row.body, layer, row.tile_id)
            if not p.exists():
                jobs.append((row, layer, p))

    def work(job):
        row, layer, p = job
        fn = _fetch_moon if row.body == "moon" else _fetch_earth
        fn(s, row, layer).save(p)

    failed = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(work, j): j for j in jobs}
        for f in tqdm(as_completed(futs), total=len(futs), desc=f"{grid.body.iloc[0]} tiles"):
            if f.exception() is not None:
                row, layer, _ = futs[f]
                failed.append(f"{row.tile_id}/{layer}: {f.exception()}")
    return failed
