"""A synthetic index, so the API can be tested anywhere.

`data/` is gitignored and each machine rebuilds it, so the tests must not need
it. These fixtures write a small index with the exact shape of the real one
(ARCHITECTURE.md §4.1) into a tmp dir and point `config` at it. CLIP is stubbed
out, so the tests never import torch or download weights.
"""
from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd
import pytest

from analogatlas import config as C
from analogatlas.analog import write_order_stamp

DIM = 512
MOON_TILES = 48
EARTH_TILES = 36
# An Earth tile right on a well-studied analog site, so known_analog is exercised.
MCMURDO = (-77.5, 162.0)


def _unit(rng: np.random.Generator, n: int) -> np.ndarray:
    v = rng.normal(size=(n, DIM))
    return (v / np.linalg.norm(v, axis=1, keepdims=True)).astype(np.float16)


def _moon_meta(rng: np.random.Generator) -> pd.DataFrame:
    lat = rng.uniform(-60, 60, MOON_TILES)
    lon = rng.uniform(-180, 180, MOON_TILES)
    return pd.DataFrame(dict(
        tile_id=[f"moon_6_{i}_{i * 2}" for i in range(MOON_TILES)],
        body="moon", z=6, y=range(MOON_TILES), x=range(0, MOON_TILES * 2, 2),
        lat=lat, lon=lon,
        lat_min=lat - 1.4, lat_max=lat + 1.4, lon_min=lon - 1.4, lon_max=lon + 1.4,
        elev_km=rng.uniform(-3, 5, MOON_TILES),
        relief_km=rng.uniform(0.1, 4, MOON_TILES),
        slope_med=rng.uniform(0.2, 12, MOON_TILES),
        slope_p90=rng.uniform(1, 25, MOON_TILES),
        rock_abundance=rng.uniform(0, 0.02, MOON_TILES),
        regolith_t_anom=rng.uniform(-5, 15, MOON_TILES),
        t_max_k=rng.uniform(330, 390, MOON_TILES),
        t_min_k=rng.uniform(40, 110, MOON_TILES),
    ))


def _moon_polar_meta(rng: np.random.Generator) -> pd.DataFrame:
    """The south polar body: polar stereographic x/y, plus the polar-only
    dimensions (illumination, permanent shadow, Earth visibility)."""
    from analogatlas.tiles import sp_inverse

    step = C.TILE_KM * 1000
    coords = (np.arange(6) - 2.5) * step
    xs, ys = (a.ravel() for a in np.meshgrid(coords, coords))
    lat, lon = sp_inverse(xs, ys)
    n = len(xs)
    psr = rng.uniform(0, 0.25, n)
    return pd.DataFrame(dict(
        tile_id=[f"moonsp_{i}_{j}" for i in range(6) for j in range(6)],
        body="moon_polar", x_m=xs, y_m=ys, size_m=step, lat=lat, lon=lon,
        lat_min=lat - 1.4, lat_max=lat + 1.4, lon_min=lon - 1.4, lon_max=lon + 1.4,
        elev_km=rng.uniform(-5, 3, n),
        relief_km=rng.uniform(1.5, 9, n),
        slope_med=rng.uniform(1, 10, n),
        slope_p90=rng.uniform(2, 25, n),
        psr_frac=psr,
        avg_illum=rng.uniform(0.1, 0.45, n),
        illum_max=rng.uniform(0.45, 0.92, n),
        earth_vis=rng.uniform(0, 0.95, n),
        t_max_k=(1 - psr) * 200.0 + psr * 40.0,
        t_min_k=(1 - psr) * 50.0 + psr * 30.0,
        has_img=rng.random(n) < 0.3,
    ))


def _mars_meta(rng: np.random.Generator) -> pd.DataFrame:
    """Mars tiles with every column in the contract (docs/MARS-PLAN.md).
    The first tile is ice-rich (high latitude, high hydrogen); the rest are not."""
    n = 40
    lat = np.concatenate([[48.0], rng.uniform(-30, 30, n - 1)])
    lon = rng.uniform(-180, 180, n)
    return pd.DataFrame(dict(
        tile_id=[f"mars_7_{i}_{i * 2}" for i in range(n)],
        body="mars", z=7, y=range(n), x=range(0, n * 2, 2),
        lat=lat, lon=lon,
        lat_min=lat - 0.7, lat_max=lat + 0.7, lon_min=lon - 0.7, lon_max=lon + 0.7,
        elev_km=rng.uniform(-6, 8, n),
        relief_km=rng.uniform(0.1, 5, n),
        slope_med=rng.uniform(0.2, 10, n),
        slope_p90=rng.uniform(1, 25, n),
        thermal_inertia=rng.uniform(40, 600, n),
        albedo=rng.uniform(0.1, 0.3, n),
        dust_index=rng.uniform(0.93, 0.98, n),
        weh_pct=np.concatenate([[9.0], rng.uniform(2, 5, n - 1)]),
        hydrous_count=np.concatenate([[0, 3], np.zeros(n - 2, dtype=int)]),
        t_max_k=rng.uniform(250, 290, n),
        t_min_k=rng.uniform(150, 190, n),
    ))


def _earth_meta(rng: np.random.Generator) -> pd.DataFrame:
    # Spread the rest over open ocean-free longitudes far from any known site.
    lat = np.concatenate([[MCMURDO[0]], rng.uniform(-50, 50, EARTH_TILES - 1)])
    lon = np.concatenate([[MCMURDO[1]], rng.uniform(60, 120, EARTH_TILES - 1)])
    return pd.DataFrame(dict(
        tile_id=[f"earth_{a:+.2f}_{o:+.2f}" for a, o in zip(lat, lon)],
        body="earth", lat=lat, lon=lon,
        lat_min=lat - 0.38, lat_max=lat + 0.38, lon_min=lon - 0.38, lon_max=lon + 0.38,
        elev_km=rng.uniform(-0.2, 4, EARTH_TILES),
        relief_km=rng.uniform(0.05, 3, EARTH_TILES),
        slope_med=rng.uniform(0.1, 10, EARTH_TILES),
        slope_p90=rng.uniform(0.5, 20, EARTH_TILES),
        greenness=rng.uniform(-0.1, 0.3, EARTH_TILES),
        brightness=rng.uniform(0.1, 0.8, EARTH_TILES),
    ))


BUILDERS = {"moon": _moon_meta, "moon_polar": _moon_polar_meta, "earth": _earth_meta,
            "mars": _mars_meta}


def write_index(directory, bodies=("moon", "moon_polar", "earth"),
                seed: int = 7) -> dict[str, pd.DataFrame]:
    """Write `{body}_meta.parquet` + the two embedding matrices, row-aligned."""
    rng = np.random.default_rng(seed)
    directory.mkdir(parents=True, exist_ok=True)
    out = {}
    for body in bodies:
        meta = BUILDERS[body](rng)
        meta.to_parquet(directory / f"{body}_meta.parquet")
        np.save(directory / f"{body}_shade.npy", _unit(rng, len(meta)))
        np.save(directory / f"{body}_img.npy", _unit(rng, len(meta)))
        write_order_stamp(body, meta, directory)
        out[body] = meta
    return out


@pytest.fixture
def stub_clip(monkeypatch):
    """Replace `analogatlas.embed` with a stub: no torch, no model download."""
    rng = np.random.default_rng(99)

    def _vec(*_args, **_kwargs):
        v = rng.normal(size=DIM)
        return (v / np.linalg.norm(v)).astype(np.float32)

    mod = types.ModuleType("analogatlas.embed")
    mod.embed_text = _vec
    mod.embed_images = lambda images, rotations=False: np.stack([_vec() for _ in images])
    monkeypatch.setitem(sys.modules, "analogatlas.embed", mod)
    return mod


@pytest.fixture
def index_dir(tmp_path, monkeypatch):
    """A full two-body index, with config pointed at it."""
    d = tmp_path / "index"
    meta = write_index(d)
    monkeypatch.setattr(C, "INDEX", d)
    monkeypatch.setattr(C, "TILES", tmp_path / "tiles")
    return types.SimpleNamespace(path=d, tiles=tmp_path / "tiles", meta=meta)


@pytest.fixture
def client(index_dir, stub_clip, monkeypatch):
    from fastapi.testclient import TestClient

    from api import main as api_main
    from api.routers import twins as twins_router

    # NASA POWER is a live HTTP call; the report card must not depend on it here.
    monkeypatch.setattr(twins_router, "earth_climate", lambda lat, lon: {
        "TS_MIN": -55.2, "TS_MAX": 8.1, "T2M_RANGE": 12.0, "PRECTOTCORR": 0.02,
        "RH2M": 41.0, "WS10M": 5.2, "ALLSKY_SFC_SW_DWN": 3.1,
    })
    with TestClient(api_main.create_app()) as c:
        yield c
