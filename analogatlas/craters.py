"""Independent crater labels from the Robbins (2019) lunar crater database (#16).

The database enters nothing else: no feature in `02_features.py`, no training
label in `learn.py`. That is the point. It is held-out ground truth, so
retrieval measured against it says something about the embeddings instead of
restating what they were built from -- crater density correlates only rho=0.35
with `slope_med` across our Moon tiles.

Download the CSV first; see the raw-data table in README.md. 227 MB,
1,296,796 craters with D >= 1 km, of which three columns are read.

A crater belongs to a tile when its *centre* falls inside the tile's chip --
the 85 km square the embeddings actually saw, which in longitude is wider than
the grid cell by 1/cos(lat) (tiles._square_chip, #27). So a tile sitting inside
a huge basin is not labelled by that basin unless it holds its centre; the
labels describe what is visible in the chip, not what the tile is part of.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config as C
from .tiles import sp_forward

CATALOG = C.RAW / "robbins" / "lunar_crater_database_robbins_2018.csv"

# Diameter cuts. The catalog is complete to 1-2 km, so 1 km is its floor.
CUTS_KM = (1, 5, 20)
# "Dominated by a big crater": half the width of an 85 km chip, so the crater
# is the subject of the image rather than one of hundreds of specks in it.
BIG_KM = 40.0

LABEL_COLUMNS = ("n_ge_1km", "n_ge_5km", "n_ge_20km", "largest_km", "per_1e4km2")


def load_catalog(path=None) -> pd.DataFrame:
    """Robbins craters as lat, lon (-180..180) and diam_km. ~1.3 M rows."""
    path = path or CATALOG
    if not path.exists():
        raise FileNotFoundError(
            f"No Robbins crater catalog at {path}. Download it into data/raw/robbins/ "
            "-- see the raw-data table in README.md.")
    raw = pd.read_csv(path, usecols=["LAT_CIRC_IMG", "LON_CIRC_IMG", "DIAM_CIRC_IMG"])
    return pd.DataFrame({
        "lat": raw.LAT_CIRC_IMG.to_numpy(float),
        # the catalog is 0..360 east; our grids are -180..180
        "lon": ((raw.LON_CIRC_IMG.to_numpy(float) + 180) % 360) - 180,
        "diam_km": raw.DIAM_CIRC_IMG.to_numpy(float),
    })


def _summarise(diams: np.ndarray, area_km2: float) -> dict:
    return {
        **{f"n_ge_{cut}km": int((diams >= cut).sum()) for cut in CUTS_KM},
        "largest_km": float(diams.max()) if len(diams) else 0.0,
        "per_1e4km2": float(len(diams)) * 1e4 / area_km2,
    }


def _label_equirect(meta: pd.DataFrame, craters: pd.DataFrame) -> list[dict]:
    """Chips on the equirectangular grid: TILE_KM tall, TILE_KM/cos(lat) wide."""
    order = np.argsort(craters.lat.to_numpy())
    lat_s = craters.lat.to_numpy()[order]
    lon_s = craters.lon.to_numpy()[order]
    diam_s = craters.diam_km.to_numpy()[order]

    half_lat = C.MOON_TILE_DEG / 2
    area = C.TILE_KM ** 2
    out = []
    for lat, lon in zip(meta.lat.to_numpy(float), meta.lon.to_numpy(float)):
        half_lon = half_lat / max(math.cos(math.radians(lat)), 1e-6)
        lo, hi = np.searchsorted(lat_s, [lat - half_lat, lat + half_lat])
        # signed shortest longitude separation, so the +/-180 seam is not a wall
        dlon = np.abs(((lon_s[lo:hi] - lon + 180) % 360) - 180)
        out.append(_summarise(diam_s[lo:hi][dlon <= half_lon], area))
    return out


def _label_polar(meta: pd.DataFrame, craters: pd.DataFrame) -> list[dict]:
    """Chips on the south polar grid: square in metres, so the cut is exact."""
    near = craters[craters.lat <= C.MOON_POLAR_MAX_LAT + 5]
    cx, cy = sp_forward(near.lat.to_numpy(), near.lon.to_numpy())
    diam = near.diam_km.to_numpy()
    out = []
    for x, y, size in zip(meta.x_m.to_numpy(float), meta.y_m.to_numpy(float),
                          meta.size_m.to_numpy(float)):
        half = size / 2
        sel = (np.abs(cx - x) <= half) & (np.abs(cy - y) <= half)
        out.append(_summarise(diam[sel], (size / 1000) ** 2))
    return out


def per_tile(meta: pd.DataFrame, body: str, craters: pd.DataFrame | None = None
             ) -> pd.DataFrame:
    """Crater labels per tile: tile_id + LABEL_COLUMNS, in `meta`'s row order."""
    if body not in ("moon", "moon_polar"):
        raise ValueError(f"the Robbins catalog is lunar; no labels for {body!r}")
    craters = load_catalog() if craters is None else craters
    rows = (_label_polar if body == "moon_polar" else _label_equirect)(meta, craters)
    return pd.DataFrame(rows, index=meta.index).assign(
        tile_id=meta.tile_id.to_numpy())[["tile_id", *LABEL_COLUMNS]]


def density_class(labels: pd.DataFrame) -> pd.Series:
    """Tercile of crater density: 0 smooth, 1 middling, 2 heavily cratered.

    Terciles of this index rather than absolute counts, because what the test
    asks is whether retrieval separates smooth mare from saturated highlands,
    and where that split falls is a property of the tiling.
    """
    n = labels.n_ge_1km.to_numpy(float)
    edges = np.quantile(n, [1 / 3, 2 / 3])
    return pd.Series(np.searchsorted(edges, n, side="right"), index=labels.index)


def big_crater(labels: pd.DataFrame) -> pd.Series:
    """True where one crater is big enough to be the subject of the chip."""
    return labels.largest_km >= BIG_KM
