"""Build tile grids for the Moon and Earth and download their image tiles.

Every tile covers roughly the same ground area (~85 x 85 km) on both bodies so
that terrain features are compared at the same physical scale.
"""
from __future__ import annotations

import io
import math
import threading
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
    s.headers["User-Agent"] = "analogatlas-hackathon/0.1"
    return s


# ---------------------------------------------------------------- grids ----
def _eq_grid(body: str, z: int, max_abs_lat: float) -> pd.DataFrame:
    """Trek WMTS equirectangular tiles whose centre lies within +/-max_abs_lat."""
    d = 180.0 / 2 ** z
    rows = []
    for y in range(2 ** z):
        lat = 90 - (y + 0.5) * d
        if abs(lat) > max_abs_lat:
            continue
        for x in range(2 ** (z + 1)):
            lon = -180 + (x + 0.5) * d
            rows.append(dict(tile_id=f"{body}_{z}_{y}_{x}", body=body, z=z, y=y, x=x,
                             lat=lat, lon=lon,
                             lat_min=lat - d / 2, lat_max=lat + d / 2,
                             lon_min=lon - d / 2, lon_max=lon + d / 2))
    return pd.DataFrame(rows)


def moon_grid() -> pd.DataFrame:
    """Trek WMTS zoom-6 tiles whose centre lies within +/-MOON_MAX_ABS_LAT."""
    return _eq_grid("moon", C.MOON_ZOOM, C.MOON_MAX_ABS_LAT)


def mars_grid() -> pd.DataFrame:
    """Trek zoom-7 tiles within +/-MARS_MAX_ABS_LAT: the same tile matrix as
    the Moon, one zoom level down, so the ground size stays ~83 km (#37)."""
    return _eq_grid("mars", C.MARS_ZOOM, C.MARS_MAX_ABS_LAT)


# ------------------------------------------------ south polar projection ----
# Spherical polar stereographic, centred on -90, scale true at the pole. The
# LOLA/PGDA polar products and Trek's Moon/SP tile tree share this grid, which
# is checked in tests/test_polar.py against known features (Shackleton reads
# ~2.5 km below its surroundings, Mons Malapert ~3.9 km above).
def sp_forward(lat, lon):
    """Lat/lon in degrees -> (x, y) in metres from the south pole."""
    rho = 2 * C.MOON_RADIUS_M * np.tan(np.radians(45 + np.asarray(lat, float) / 2))
    lam = np.radians(np.asarray(lon, float))
    return rho * np.sin(lam), rho * np.cos(lam)


def sp_inverse(x, y):
    """(x, y) in metres from the south pole -> lat/lon in degrees."""
    rho = np.hypot(np.asarray(x, float), np.asarray(y, float))
    lat = np.degrees(2 * np.arctan(rho / (2 * C.MOON_RADIUS_M))) - 90
    return lat, np.degrees(np.arctan2(x, y))


def moon_polar_grid() -> pd.DataFrame:
    """~85 km square cells on the south polar stereographic grid.

    Square in kilometres everywhere, which is the whole point of the polar
    grid: the equirectangular grid cannot do this past ~60 deg.
    """
    step = C.TILE_KM * 1000
    r_max = float(sp_forward(C.MOON_POLAR_MAX_LAT, 0.0)[1])
    n = int(math.ceil(2 * r_max / step))
    coords = (np.arange(n) - (n - 1) / 2) * step
    rows = []
    for yi, y in enumerate(coords):
        for xi, x in enumerate(coords):
            # keep the cell if at least half of a 5x5 sub-grid is inside the
            # product's edge -- the same rule earth_grid uses for land
            sx = np.linspace(x - step / 2, x + step / 2, 5)
            sy = np.linspace(y - step / 2, y + step / 2, 5)
            SX, SY = np.meshgrid(sx, sy)
            if (np.hypot(SX, SY) <= r_max).mean() < 0.5:
                continue
            lat, lon = sp_inverse(x, y)
            # A lat/lon bbox from the four corners, for callers that still want
            # one. It is informational: the polar pane positions cells from
            # x_m/y_m. A cell containing the pole spans every longitude, and
            # reaches -90 even though none of its corners do.
            cx, cy = np.meshgrid([x - step / 2, x + step / 2], [y - step / 2, y + step / 2])
            clat, clon = sp_inverse(cx.ravel(), cy.ravel())
            spans_pole = bool(np.hypot(cx, cy).min() <= 0 or (cx.min() < 0 < cx.max()
                                                              and cy.min() < 0 < cy.max()))
            rows.append(dict(
                tile_id=f"moonsp_{xi}_{yi}", body="moon_polar",
                x_m=float(x), y_m=float(y), size_m=float(step),
                lat=float(lat), lon=float(lon),
                lat_min=-90.0 if spans_pole else float(clat.min()),
                lat_max=float(clat.max()),
                lon_min=-180.0 if spans_pole else float(clon.min()),
                lon_max=180.0 if spans_pole else float(clon.max())))
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
def _lon_window_px(lat: float) -> int:
    """Width, in source pixels, of a TILE_KM-wide window at this latitude.

    An equirectangular tile is TILE_KM tall but only TILE_KM*cos(lat) wide, so
    a chip that is square in kilometres spans 1/cos(lat) tiles of longitude.
    """
    return int(round(C.TILE_PX / max(math.cos(math.radians(lat)), 1e-6)))


def _square_chip(strip: Image.Image, lat: float) -> Image.Image:
    """Cut a chip that is TILE_KM on a side in kilometres from a tile strip.

    The strip is a row of whole tiles centred on the chip's own tile. Taking
    `_lon_window_px(lat)` pixels of it and resizing to a square *removes* the
    E-W stretch; cropping to `cos(lat)` of one tile and resizing back up (what
    this used to do) applies the stretch a second time instead, leaving a
    ground aspect of cos^2(lat) -- 4x off by 60 deg. See issue #27.
    """
    w, h = strip.size
    keep = min(_lon_window_px(lat), w)
    left = (w - keep) // 2
    return strip.crop((left, 0, left + keep, h)).resize((C.TILE_PX, C.TILE_PX), Image.BILINEAR)


def tile_path(body: str, layer: str, tile_id: str):
    # polar imagery is PNG at source; don't round-trip dark NAC tiles via JPEG
    ext = "png" if layer == "shade" or body == "moon_polar" else "jpg"
    return C.TILES / body / layer / f"{tile_id}.{ext}"


EQ_LAYERS = {"moon": C.MOON_LAYERS, "mars": C.MARS_LAYERS}


def _fetch_eq(s, row, layer):
    """One chip, mosaicked across longitude so it is square in kilometres."""
    n = int(math.ceil(_lon_window_px(row.lat) / C.TILE_PX))
    n += 1 - n % 2                       # odd, so row.x stays in the middle
    across = 2 ** (row.z + 1)
    # The Viking mosaic is colour, like Blue Marble on Earth's look channel.
    mode = "RGB" if row.body == "mars" and layer == "img" else "L"
    strip = Image.new(mode, (n * C.TILE_PX, C.TILE_PX))
    for i in range(n):
        url = EQ_LAYERS[row.body][layer].format(z=row.z, y=row.y, x=(row.x + i - n // 2) % across)
        r = s.get(url, timeout=30)
        r.raise_for_status()
        strip.paste(Image.open(io.BytesIO(r.content)).convert(mode), (i * C.TILE_PX, 0))
    return _square_chip(strip, row.lat)


# Trek's Moon/SP tiles are reused by neighbouring chips, so cache them.
_SP_CACHE: dict = {}
_SP_LOCK = threading.Lock()


def _sp_px(x_m, y_m, z):
    """(x, y) in metres -> pixel coordinates in the full Moon/SP mosaic."""
    mpp = C.MOON_SP_EXTENT_M / 2 ** z / C.TILE_PX
    ox, oy = C.MOON_SP_ORIGIN_M
    return (x_m - ox) / mpp, (oy - y_m) / mpp


def _sp_tile(s, layer, z, row_i, col_i):
    """One Moon/SP tile, or None outside the product's footprint."""
    key = (layer, z, row_i, col_i)
    with _SP_LOCK:
        if key in _SP_CACHE:
            return _SP_CACHE[key]
    r = s.get(C.MOON_SP_LAYERS[layer].format(z=z, y=row_i, x=col_i), timeout=30)
    img = Image.open(io.BytesIO(r.content)).convert("L") if r.status_code == 200 else None
    with _SP_LOCK:
        _SP_CACHE[key] = img
    return img


def _fetch_moon_polar(s, row, layer):
    """One polar chip, cut from the Moon/SP tile tree.

    No cos(lat) correction anywhere: the cell is already square in metres on
    the polar stereographic grid, which is the whole reason the pole has its
    own projection. Tiles missing at the edge of the product stay black.
    """
    z, half = C.MOON_SP_ZOOM, row.size_m / 2
    px0, py0 = _sp_px(row.x_m - half, row.y_m + half, z)
    px1, py1 = _sp_px(row.x_m + half, row.y_m - half, z)
    c0, c1 = int(px0 // C.TILE_PX), int(px1 // C.TILE_PX)
    r0, r1 = int(py0 // C.TILE_PX), int(py1 // C.TILE_PX)
    mosaic = Image.new("L", ((c1 - c0 + 1) * C.TILE_PX, (r1 - r0 + 1) * C.TILE_PX))
    for rr in range(r0, r1 + 1):
        for cc in range(c0, c1 + 1):
            t = _sp_tile(s, layer, z, rr, cc)
            if t is not None:
                mosaic.paste(t, ((cc - c0) * C.TILE_PX, (rr - r0) * C.TILE_PX))
    box = (round(px0 - c0 * C.TILE_PX), round(py0 - r0 * C.TILE_PX),
           round(px1 - c0 * C.TILE_PX), round(py1 - r0 * C.TILE_PX))
    return mosaic.crop(box).resize((C.TILE_PX, C.TILE_PX), Image.BILINEAR)


def _fetch_earth(s, row, layer):
    if layer == "shade":                       # hillshade from Earth Engine
        from . import earth_ee
        return earth_ee.shade_tile(row, s)
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


FETCHERS = {"moon": _fetch_eq, "mars": _fetch_eq, "moon_polar": _fetch_moon_polar,
            "earth": _fetch_earth}


def fetch_tiles(grid: pd.DataFrame, layers=("img", "shade"), workers: int = 12) -> list[str]:
    """Download every (tile, layer) that is not on disk yet. Returns failures."""
    s = _session()
    body = grid.body.iloc[0]
    if body == "earth" and "shade" in layers:
        from . import earth_ee
        earth_ee._shade_image()                # initialise EE once, before the threads
    if body == "moon_polar":
        workers = min(workers, 4)              # each chip is up to 16 tile requests
    jobs = []
    for layer in layers:
        (C.TILES / body / layer).mkdir(parents=True, exist_ok=True)
        for row in grid.itertuples():
            p = tile_path(row.body, layer, row.tile_id)
            if not p.exists():
                jobs.append((row, layer, p))

    def work(job):
        row, layer, p = job
        FETCHERS[row.body](s, row, layer).save(p)

    failed = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(work, j): j for j in jobs}
        for f in tqdm(as_completed(futs), total=len(futs), desc=f"{body} tiles"):
            if f.exception() is not None:
                row, layer, _ = futs[f]
                failed.append(f"{row.tile_id}/{layer}: {f.exception()}")
    return failed
