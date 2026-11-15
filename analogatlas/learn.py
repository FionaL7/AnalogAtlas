"""Learn what known Earth analog sites have in common; find new ones (#29).

Positive-unlabeled (PU) learning. The tiles holding a known analog site are
positives. Every other tile is *unlabeled*, not negative: most were simply never
studied, and some are exactly the new analogs we want to find. The usual PU
recipe (Elkan & Noto 2008) is to train a classifier "positive vs unlabeled" with
balanced class weights and use its score for *ranking*; we only ever rank.

Features per tile (all standardised):
  * terrain shape: CLIP hillshade vector, reduced to 16 numbers with PCA
  * surface look:  CLIP image vector, reduced the same way
  * physical:      slope, relief (same 1.85 km baseline as the Moon)
  * environment:   surface temperature, rainfall, aridity, sunlight,
                   vegetation, ice, bare ground, ...
Not used: lat/lon, elevation, travel time (the model would learn *where*
known sites are, or how reachable they are, instead of what they are like).

Validation: hold-one-out. Hide one site, train on the rest, and see where the
hidden site ranks among all unlabeled tiles. Random guessing averages 50%.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .analog import BodyIndex, haversine_deg, known_analog_name
from .sites import ANALOG_INFO, KNOWN_EARTH_ANALOGS

N_PCA = 16
SITE_MAX_DEG = 1.0          # a site counts for a tile only if its centre is within ~110 km
# Strong regularisation: ~15-30 positives vs ~50 features. 0.01 was the best
# setting in a hold-one-out sweep over {0.003 .. 0.3} (a small optimistic bias,
# noted in validation.json).
C_REG = 0.01
MAX_ICE = 0.5               # candidates must be mostly rock/soil, not ice sheet

# column -> readable name (used for the "why it scored high" reasons)
TABULAR = {
    "slope_med": "median slope",
    "slope_p90": "steep slopes (p90)",
    "relief_km": "local relief",
    "lst_day_c": "daytime surface temperature",
    "lst_night_c": "night surface temperature",
    "lst_hot_c": "hottest days",
    "lst_cold_c": "coldest nights",
    "lst_swing_c": "day-night temperature swing",
    "log_precip": "rainfall",
    "aridity": "moisture (precip / evaporation)",
    "solar_wm2": "sunlight",
    "ndvi": "vegetation (NDVI)",
    "ice_frac": "ice cover",
    "barren_frac": "bare ground",
    "sparse_frac": "sparse scrub / grass",
    "veg_frac": "dense vegetation",
    "water_frac": "water / wetland",
    "urban_frac": "urban",
    "brightness": "surface brightness",
    "greenness": "greenness",
    # A3 Earth counterpart columns (#39), so Mars-facing dimensions can pull
    # their weight: albedo matches TES, dust matches the TES dust index, mean
    # temperature matches the modelled Mars extremes. A4 measures their worth.
    "albedo": "albedo (sunlight reflected)",
    "dust_aod": "atmospheric dust (MERRA-2)",
    "lst_mean_c": "mean surface temperature",
}
A3_COLUMNS = ("albedo", "dust_aod", "lst_mean_c")
GROUPS = {"shape": "terrain shape (CLIP)", "look": "surface look (CLIP)"}


@dataclass
class Features:
    X: np.ndarray            # (n_tiles, n_features), standardised
    names: list[str]         # column names; "shape_3" / "look_7" for PCA parts
    group: list[str]         # "shape", "look", "phys", "env"


def build_features(earth: BodyIndex, parts=("shape", "look", "phys", "env"),
                   exclude: tuple[str, ...] = ()) -> Features:
    """`exclude` drops named tabular columns -- used to measure what the A3
    columns add by training once without them."""
    m = earth.meta.copy()
    m["log_precip"] = np.log1p(m.precip_mm)
    blocks, names, group = [], [], []
    if "shape" in parts:
        blocks.append(PCA(N_PCA, random_state=0).fit_transform(earth.shade))
        names += [f"shape_{i}" for i in range(N_PCA)]
        group += ["shape"] * N_PCA
    if "look" in parts:
        blocks.append(PCA(N_PCA, random_state=0).fit_transform(earth.img))
        names += [f"look_{i}" for i in range(N_PCA)]
        group += ["look"] * N_PCA
    for part, cols in (("phys", ["slope_med", "slope_p90", "relief_km"]),
                       ("env", [c for c in TABULAR
                                if c not in ("slope_med", "slope_p90", "relief_km")
                                and c not in exclude])):
        if part in parts:
            t = m[cols].astype(float)
            blocks.append(t.fillna(t.median()).values)
            names += cols
            group += [part] * len(cols)
    X = StandardScaler().fit_transform(np.concatenate(blocks, axis=1))
    return Features(X, names, group)


def site_tiles(earth: BodyIndex, target: str | None = None, surface_only: bool = True) -> dict[str, int]:
    """Known site name -> row of the Earth tile it falls in (sites without a
    land tile, e.g. small islands, are skipped)."""
    meta = earth.meta
    out = {}
    for name, (la, lo) in KNOWN_EARTH_ANALOGS.items():
        info = ANALOG_INFO[name]
        if surface_only and not info["surface"]:
            continue
        if target and target not in info["target"]:
            continue
        d = haversine_deg(la, lo, meta.lat.values, meta.lon.values)
        if d.min() <= SITE_MAX_DEG:
            out[name] = int(d.argmin())
    return out


def fit(X: np.ndarray, pos_rows) -> LogisticRegression:
    y = np.zeros(len(X), dtype=int)
    y[list(pos_rows)] = 1
    return LogisticRegression(C=C_REG, class_weight="balanced", max_iter=5000).fit(X, y)


def percentile_rank(scores: np.ndarray) -> np.ndarray:
    """0..1, 1 = best tile on Earth."""
    return pd.Series(scores).rank(pct=True).values


def holdout(F: Features, sites: dict[str, int]) -> pd.DataFrame:
    """Hide each site in turn; where does its tile rank among unlabeled tiles?
    `top_pct` = % of unlabeled tiles scoring higher (lower is better; random ~ 50)."""
    pos = set(sites.values())
    unlabeled = np.array([i for i in range(len(F.X)) if i not in pos])
    rows = []
    for name, row in sites.items():
        train = pos - {row}
        s = fit(F.X, train).decision_function(F.X)
        rows.append({"site": name, "tile_row": row,
                     "top_pct": 100 * float((s[unlabeled] > s[row]).mean())})
    return pd.DataFrame(rows)


def holdout_region(F: Features, sites: dict[str, int], meta: pd.DataFrame,
                   radius_km: float = 1500.0) -> pd.DataFrame:
    """Like `holdout`, but also hides every other known site within `radius_km`.
    Known sites cluster (US Southwest, Australian craters), so plain hold-one-out
    can score well by learning *where* sites are. This is the closer proxy for a
    region the model has never seen."""
    pos = set(sites.values())
    unlabeled = np.array([i for i in range(len(F.X)) if i not in pos])
    lat, lon = meta.lat.values, meta.lon.values
    rows = []
    for name, row in sites.items():
        near = {q for q in pos if haversine_deg(lat[row], lon[row], lat[q], lon[q]) * 111.2 < radius_km}
        train = pos - near
        s = fit(F.X, train).decision_function(F.X)
        rows.append({"site": name, "tile_row": row, "n_hidden": len(near),
                     "top_pct": 100 * float((s[unlabeled] > s[row]).mean())})
    return pd.DataFrame(rows)


def holdout_single_column(meta: pd.DataFrame, sites: dict[str, int], col: str,
                          higher_is_better: bool = True) -> pd.DataFrame:
    """No-learning baseline: rank tiles by one column (e.g. bare ground). The
    model must beat this to claim it learned more than 'barren and dry'."""
    pos = set(sites.values())
    unlabeled = np.array([i for i in range(len(meta)) if i not in pos])
    v = meta[col].astype(float)
    s = v.fillna(v.median()).values * (1 if higher_is_better else -1)
    return pd.DataFrame([{"site": name, "tile_row": row,
                          "top_pct": 100 * float((s[unlabeled] > s[row]).mean())}
                         for name, row in sites.items()])


def random_sites_control(F: Features, n_sites: int, runs: int = 5, seed: int = 0) -> list[float]:
    """Sanity check: random tiles posing as 'known sites'. Hold-one-out medians
    should hover around 50; if they don't, the method is finding signal in noise."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(runs):
        fake = {f"random_{i}": int(r) for i, r in enumerate(rng.choice(len(F.X), n_sites, replace=False))}
        out.append(round(float(holdout(F, fake).top_pct.median()), 1))
    return out


def holdout_visual_baseline(earth: BodyIndex, sites: dict[str, int], w_shade: float = 0.6) -> pd.DataFrame:
    """What an image-only approach does: rank tiles by CLIP similarity to the
    other known sites (best match), no physics, no learning."""
    pos = set(sites.values())
    unlabeled = np.array([i for i in range(len(earth.meta)) if i not in pos])
    rows = []
    for name, row in sites.items():
        others = list(pos - {row})
        sim = w_shade * (earth.shade @ earth.shade[others].T) + (1 - w_shade) * (earth.img @ earth.img[others].T)
        s = sim.max(axis=1)
        rows.append({"site": name, "tile_row": row,
                     "top_pct": 100 * float((s[unlabeled] > s[row]).mean())})
    return pd.DataFrame(rows)


def reasons(model: LogisticRegression, F: Features, row: int, n: int = 3) -> list[str]:
    """The features pushing this tile's score up the most, in plain words."""
    contrib = model.coef_[0] * F.X[row]
    by = {}
    for c, x, name, g in zip(contrib, F.X[row], F.names, F.group):
        key = GROUPS.get(g) or f"{'high' if x > 0 else 'low'} {TABULAR.get(name, name)}"
        by[key] = by.get(key, 0.0) + float(c)
    top = sorted(by.items(), key=lambda kv: -kv[1])[:n]
    return [k for k, v in top if v > 0]


def weights(model: LogisticRegression, F: Features) -> pd.DataFrame:
    """Learned weight per readable feature (CLIP parts summed by magnitude)."""
    rows = {}
    for w, name, g in zip(model.coef_[0], F.names, F.group):
        key = GROUPS.get(g, TABULAR.get(name, name))
        if g in GROUPS:
            rows[key] = rows.get(key, 0.0) + abs(float(w))
        else:
            rows[key] = float(w)
    return (pd.DataFrame({"feature": list(rows), "weight": list(rows.values())})
            .assign(abs=lambda d: d.weight.abs()).sort_values("abs", ascending=False)
            .drop(columns="abs").reset_index(drop=True))


def new_candidates(earth: BodyIndex, scores: np.ndarray, model, F: Features,
                   n: int = 25, min_sep_deg: float = 3.0) -> pd.DataFrame:
    """Top-scoring tiles that are NOT near a known analog (and not ice sheet),
    spread out so the list isn't 25 neighbouring tiles of the same desert."""
    meta = earth.meta
    picked = []
    for row in np.argsort(-scores):
        t = meta.iloc[row]
        if known_analog_name(t.lat, t.lon) is not None or t.ice_frac > MAX_ICE:
            continue
        if any(haversine_deg(t.lat, t.lon, meta.lat.values[p], meta.lon.values[p]) < min_sep_deg for p in picked):
            continue
        picked.append(int(row))
        if len(picked) == n:
            break
    pr = percentile_rank(scores)
    return pd.DataFrame([{
        "tile_id": meta.tile_id.iloc[r], "lat": round(float(meta.lat.iloc[r]), 2),
        "lon": round(float(meta.lon.iloc[r]), 2), "score_pct": round(100 * float(pr[r]), 2),
        "why": reasons(model, F, r),
        "slope_med": round(float(meta.slope_med.iloc[r]), 2),
        "barren_frac": round(float(meta.barren_frac.iloc[r]), 2),
        "precip_mm": round(float(meta.precip_mm.iloc[r]), 0),
        "access_min": None if pd.isna(meta.access_min.iloc[r]) else round(float(meta.access_min.iloc[r])),
    } for r in picked])
