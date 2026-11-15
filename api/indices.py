"""Index loading and lookup for the API.

The service holds one `BodyIndex` per body in memory for its whole life (~35 MB
for Moon + Earth, see ARCHITECTURE.md §4.1). A body whose index files are not on
disk is simply absent, and requests for it return 503 rather than crashing the
app — this device may only have the Moon index, and the static export (§4.2)
covers the demo path either way.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from fastapi import HTTPException, Request

from analogatlas import config as C
from analogatlas.analog import BodyIndex, haversine_deg, load_index
from analogatlas.sites import KNOWN_EARTH_ANALOGS

log = logging.getLogger("analogatlas.api")

BODIES = ("moon", "moon_polar", "mars", "earth")
# Every Moon or Mars body pairs with Earth. An Earth source pairs with the
# equatorial Moon unless the request asks for Mars (`dst_body`). `moon_polar`
# is the south pole on its own polar stereographic grid (#26), not a subset
# of `moon`.
EARTH_ANALOG_OF = {"moon": "earth", "moon_polar": "earth", "mars": "earth", "earth": "moon"}
# The #29 model scores Earth tiles per target; a source body picks its column.
MODEL_SCORE_COLUMN = {"moon": "model_score", "moon_polar": "model_score",
                      "mars": "model_score_mars"}
KNOWN_RADIUS_KM = 150.0


def annotate_known(meta: pd.DataFrame) -> pd.DataFrame:
    """Tag Earth tiles that sit on a well-studied analog site.

    Same 150 km rule as `analog.known_analog_name`, but vectorised over the
    whole grid: tiles left as None are the *new* candidates the challenge asks
    for, and `/analogs?new_only=true` filters on this column.

    `scripts/03_export.py` imports this so the static export and the API agree
    on which tiles count as "known". It belongs in `analogatlas/` proper once
    `analog.py` is free (#12, #20).
    """
    names = np.full(len(meta), None, dtype=object)
    best = np.full(len(meta), np.inf)
    lat, lon = meta.lat.values, meta.lon.values
    for name, (la, lo) in KNOWN_EARTH_ANALOGS.items():
        d_km = haversine_deg(lat, lon, la, lo) * C.EARTH_KM_PER_DEG
        closer = (d_km < KNOWN_RADIUS_KM) & (d_km < best)
        best = np.where(closer, d_km, best)
        names[closer] = name
    meta = meta.copy()
    meta["known_analog"] = names
    return meta


def attach_model_scores(meta: pd.DataFrame) -> pd.DataFrame:
    """Add the #29 analog model's 0-1 percentiles from earth_scores.parquet:
    `model_score` for the Moon target, `model_score_mars` for Mars. NaN
    everywhere until 04_train.py runs."""
    path = C.INDEX / "earth_scores.parquet"
    meta = meta.copy()
    sc = pd.read_parquet(path) if path.exists() else None
    for out, col in (("model_score", "analog_score_moon"), ("model_score_mars", "analog_score_mars")):
        meta[out] = np.nan
        if sc is not None and col in sc:
            lookup = dict(zip(sc.tile_id.astype(str), sc[col].astype(float)))
            meta[out] = meta.tile_id.astype(str).map(lookup).astype(float)
    return meta


def load_all() -> dict[str, BodyIndex]:
    out: dict[str, BodyIndex] = {}
    for body in BODIES:
        if not (C.INDEX / f"{body}_meta.parquet").exists():
            log.warning("no index for %s in %s - its endpoints will return 503", body, C.INDEX)
            continue
        # load_index refuses a mismatched index (row counts, tile_id order stamp),
        # so a silently misaligned index can never be served (issue #12).
        idx = load_index(body)
        if body == "earth":
            idx.meta = attach_model_scores(annotate_known(idx.meta))
        elif "known_analog" not in idx.meta:
            idx.meta = idx.meta.assign(known_analog=None)
        out[body] = idx
        log.info("loaded %s index: %d tiles", body, len(idx.meta))
    return out


def get_index(request: Request, body: str) -> BodyIndex:
    if body not in BODIES:
        raise HTTPException(400, f"unknown body {body!r}; expected one of {list(BODIES)}")
    idx = request.app.state.indices.get(body)
    if idx is None:
        raise HTTPException(503, f"the {body} index is not loaded on this server")
    return idx


def other_body(body: str, dst_body: str | None = None) -> str:
    """The body the analogs are on. `dst_body` only applies to an Earth source."""
    return dst_body if body == "earth" and dst_body else EARTH_ANALOG_OF[body]


def row_by_tile_id(idx: BodyIndex, tile_id: str) -> int:
    hit = np.flatnonzero(idx.meta.tile_id.values == tile_id)
    if not len(hit):
        raise HTTPException(404, f"unknown tile_id {tile_id!r}")
    return int(hit[0])


def json_scalar(v):
    """NumPy/pandas scalar -> something JSON can hold."""
    if v is None or (np.isscalar(v) and pd.isna(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v if isinstance(v, (str, int, bool)) else str(v)


def row_dict(idx: BodyIndex, i: int, columns: list[str] | None = None) -> dict:
    row = idx.meta.iloc[i]
    keys = columns or [c for c in idx.meta.columns if c not in ("z", "y", "x")]
    return {k: json_scalar(row[k]) for k in keys if k in row}
