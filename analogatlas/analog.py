"""Search index + analog scoring.

Similarity has two parts:
  * a learned part: CLIP embeddings of terrain-shape (hillshade) and imagery tiles
  * a physical part: slope, relief, temperature, atmosphere, gravity, water...
The physical breakdown is what explains *where the analogy holds and where it
breaks down*, which the challenge asks for explicitly.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
import requests

from . import config as C
from .sites import KNOWN_EARTH_ANALOGS


# ------------------------------------------------------------- index -------
@dataclass
class BodyIndex:
    meta: pd.DataFrame
    shade: np.ndarray   # (N, D) rotation-averaged hillshade embeddings
    img: np.ndarray     # (N, D) imagery embeddings

    def nearest_tile(self, lat: float, lon: float) -> int:
        d = haversine_deg(self.meta.lat.values, self.meta.lon.values, lat, lon)
        return int(np.argmin(d))


def load_index(body: str) -> BodyIndex:
    meta = pd.read_parquet(C.INDEX / f"{body}_meta.parquet")
    shade = np.load(C.INDEX / f"{body}_shade.npy").astype(np.float32)
    img = np.load(C.INDEX / f"{body}_img.npy").astype(np.float32)
    return BodyIndex(meta, shade, img)


def haversine_deg(lat1, lon1, lat2, lon2):
    """Great-circle angle in degrees (body-independent)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(a, 0, 1))))


def known_analog_name(lat: float, lon: float, radius_km: float = 150) -> str | None:
    for name, (la, lo) in KNOWN_EARTH_ANALOGS.items():
        if haversine_deg(lat, lon, la, lo) * C.EARTH_KM_PER_DEG < radius_km:
            return name
    return None


# ------------------------------------------------------------ search -------
def search(index: BodyIndex, query_vec: np.ndarray, k: int = 12,
           w_shade: float = 0.6, mask: np.ndarray | None = None) -> pd.DataFrame:
    """Rank tiles by a weighted mix of shade- and imagery-embedding cosine."""
    s = w_shade * (index.shade @ query_vec) + (1 - w_shade) * (index.img @ query_vec)
    if mask is not None:
        s = np.where(mask, s, -np.inf)
    top = np.argsort(-s)[:k]
    out = index.meta.iloc[top].copy()
    out["score"] = s[top]
    out["row"] = top
    return out


def cross_body(src: BodyIndex, i: int, dst: BodyIndex, k: int = 12,
               mask: np.ndarray | None = None, w_phys: float = 0.3) -> pd.DataFrame:
    """Tiles on `dst` most similar to tile i on `src`.

    Visual: cosine between rotation-averaged hillshade embeddings (terrain shape,
    independent of colour and sun direction).
    Physical: closeness of slope and relief, measured on 1.9 km DEMs on both bodies.
    """
    visual = dst.shade @ src.shade[i]
    s_row = src.meta.iloc[i]
    phys = np.nan_to_num(np.mean([
        _closeness(dst.meta.slope_med.values, s_row.slope_med, 1.0),
        _closeness(dst.meta.relief_km.values, s_row.relief_km, 1.0),
    ], axis=0), nan=0.0)
    # standardise the visual score so the two parts mix on comparable scales
    v = (visual - visual.mean()) / (visual.std() + 1e-9)
    score = (1 - w_phys) * v + w_phys * (phys - 0.5) * 4
    if mask is not None:
        score = np.where(mask, score, -np.inf)
    top = np.argsort(-score)[:k]
    out = dst.meta.iloc[top].copy()
    out["score"], out["visual_cos"], out["physical"], out["row"] = score[top], visual[top], phys[top], top
    # percentile of the visual similarity among all candidate tiles -> 0..1
    out["visual_cos_scaled"] = [(visual < v).mean() for v in visual[top]]
    return out


def _closeness(a, b, scale):
    """1 when equal, decays with log-ratio distance (relief/slope span decades)."""
    a = np.asarray(a, dtype=float)
    return np.exp(-np.abs(np.log1p(a) - np.log1p(b)) / scale)


# ---------------------------------------------------- NASA POWER climate ----
@lru_cache(maxsize=512)
def earth_climate(lat: float, lon: float) -> dict:
    """NASA POWER climatology (2001-2025) for one point. Cached; ~1 s per call."""
    params = "TS_MIN,TS_MAX,T2M_RANGE,PRECTOTCORR,RH2M,WS10M,ALLSKY_SFC_SW_DWN"
    r = requests.get(C.POWER_URL, timeout=60, params=dict(
        parameters=params, community="RE", latitude=round(lat, 2),
        longitude=round(lon, 2), format="JSON"))
    r.raise_for_status()
    p = r.json()["properties"]["parameter"]
    return {k: v.get("ANN") for k, v in p.items()}


# -------------------------------------------------------- breakdown --------
def breakdown(moon: pd.Series, earth: pd.Series, climate: dict | None) -> pd.DataFrame:
    """Dimension-by-dimension comparison of a lunar tile and an Earth tile.
    Returns rows of (dimension, moon value, earth value, match 0-1, note)."""
    rows = []

    def add(dim, mv, ev, match, note):
        rows.append(dict(dimension=dim, moon=mv, earth=ev,
                         match=None if match is None else float(np.clip(match, 0, 1)), note=note))

    add("Terrain shape (ML)", "-", "-", earth.get("visual_cos_scaled"),
        "CLIP similarity of hillshade tiles, sun-direction invariant")
    add("Median slope", f"{moon.slope_med:.1f}°", f"{earth.slope_med:.1f}°",
        float(_closeness(earth.slope_med, moon.slope_med, 1.0)),
        "LOLA vs ETOPO, both ~1.9 km/px")
    add("Local relief", f"{moon.relief_km:.2f} km", f"{earth.relief_km:.2f} km",
        float(_closeness(earth.relief_km, moon.relief_km, 1.0)),
        "98th-2nd percentile elevation within ~85 km")
    if climate:
        ts_min, ts_max = climate["TS_MIN"], climate["TS_MAX"]
        swing_e, swing_m = ts_max - ts_min, moon.t_max_k - moon.t_min_k
        add("Surface temperature swing", f"{swing_m:.0f} K", f"{swing_e:.0f} K",
            swing_e / swing_m, "Moon: Diviner-consistent model; Earth: NASA POWER skin temp.")
        add("Coldest surface", f"{moon.t_min_k - 273.15:.0f} °C", f"{ts_min:.0f} °C",
            math.exp(-abs((ts_min + 273.15) - moon.t_min_k) / 60), "")
        precip = climate["PRECTOTCORR"]
        add("Dryness", "no liquid water", f"{precip:.2f} mm/day", math.exp(-precip / 0.5),
            "NASA POWER precipitation; hyper-arid < 0.1 mm/day")
        add("Solar exposure", "unfiltered", f"{climate['ALLSKY_SFC_SW_DWN']:.1f} kWh/m²/day",
            climate["ALLSKY_SFC_SW_DWN"] / 8.0, "Higher = closer to airless illumination")
    if "rock_abundance" in moon and not pd.isna(moon.rock_abundance):
        add("Surface rock cover", f"{moon.rock_abundance * 100:.1f}%", "no global Earth equivalent",
            None, "Diviner rock abundance - landing-hazard proxy")
    add("Atmosphere", "vacuum", "1 bar (less at altitude)", 0.0,
        "Cannot be reproduced on Earth - dust, thermal and EVA tests differ")
    add("Gravity", "1.62 m/s²", "9.81 m/s²", 0.0, "Mobility & construction tests overestimate traction")
    return pd.DataFrame(rows)
