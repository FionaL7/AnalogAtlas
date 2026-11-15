"""Analog portfolio (#31) on a small hand-built world with known answers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analogatlas.analog import BodyIndex
from analogatlas.portfolio import (
    DIMENSION_IDS, build_portfolio, dimension_scores, greedy_cover, noon_sun_deg,
)

DIM = 8


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


A = _unit([1, 0, 0, 0, 0, 0, 0, 0])


def _world(polar: bool = False):
    """Three specialists, each good at a different part of the target, plus
    filler. No one site covers everything; together they do."""
    moon_meta = pd.DataFrame(dict(
        tile_id=["m"], lat=[-85.0 if polar else 10.0], lon=[20.0],
        slope_med=[3.0], relief_km=[1.5], t_max_k=[200.0 if polar else 390.0],
        t_min_k=[50.0 if polar else 100.0]))
    if polar:
        moon_meta["psr_frac"] = [0.1]
    moon = BodyIndex(moon_meta, np.stack([A]), np.stack([A]))

    rng = np.random.default_rng(3)
    names = ["e_terrain", "e_desert", "e_arctic", "e_ice", "e_town"] + [f"e_{k}" for k in range(15)]
    n = len(names)
    shade = [A, _unit(0.2 * A + rng.normal(size=DIM)), _unit(0.2 * A + rng.normal(size=DIM)),
             _unit(0.99 * A + 0.01 * rng.normal(size=DIM)),   # ice sheet: a lookalike
             _unit(rng.normal(size=DIM))]
    shade += [_unit(rng.normal(size=DIM)) for _ in range(15)]
    meta = pd.DataFrame(dict(
        tile_id=names,
        lat=[10.0, 12.0, 78.0, 80.0, 40.0] + [30.0] * 15,
        lon=np.linspace(-170, 170, n),
        # e_terrain: right slopes and shape, but wet, mild and remote
        slope_med=[3.0, 0.3, 0.3, 3.0, 0.2] + [0.1] * 15,
        relief_km=[1.5, 0.1, 0.1, 1.5, 0.05] + [0.02] * 15,
        lst_hot_c=[30.0, 60.0, 10.0, 0.0, 30.0] + [25.0] * 15,
        lst_cold_c=[20.0, 5.0, -45.0, -50.0, 0.0] + [10.0] * 15,
        # e_desert: dry, bare and a big temperature swing
        precip_mm=[1500.0, 10.0, 600.0, 100.0, 900.0] + [1000.0] * 15,
        barren_frac=[0.0, 0.95, 0.6, 0.0, 0.0] + [0.0] * 15,
        sparse_frac=[0.0, 0.0, 0.3, 0.0, 0.1] + [0.0] * 15,
        ice_frac=[0.0, 0.0, 0.0, 0.95, 0.0] + [0.0] * 15,
        veg_frac=[0.8, 0.0, 0.0, 0.0, 0.0] + [0.0] * 15,
        water_frac=[0.0] * n, ndvi=[0.2, 0.0, 0.0, 0.0, 0.2] + [0.2] * 15,
        # e_town: an hour from a city
        access_min=[3000.0, 3000.0, 5000.0, np.nan, 60.0] + [2000.0] * 15,
        known_analog=[None] * n,
    ))
    meta.loc[0, "veg_frac"] = 0.0      # keep e_terrain eligible
    return moon, BodyIndex(meta, np.stack(shade), np.stack(shade))


def test_scores_are_zero_to_one_for_every_dimension():
    moon, earth = _world()
    s = dimension_scores(moon, 0, earth)
    assert list(s.columns) == DIMENSION_IDS
    assert ((s >= 0) & (s <= 1)).all().all()
    assert s.loc[0, "shape"] == s["shape"].max()          # e_terrain looks most alike
    assert s.loc[1, "dryness"] > 0.9 and s.loc[0, "dryness"] < 0.01
    assert s.loc[4, "access"] > 0.9
    assert s.loc[3, "access"] == 0.0                       # no data: can't cover


def test_portfolio_covers_every_dimension_with_specialists():
    moon, earth = _world()
    p = build_portfolio(moon, 0, earth)
    picked = [s["tile_id"] for s in p["sites"]]
    assert p["uncovered"] == []
    assert len(picked) <= 4
    # no one site covers everything, so a portfolio beats the best single site
    assert p["best_single_site"]["covers"] < len(DIMENSION_IDS)
    assert {"e_terrain", "e_desert", "e_town"} <= set(picked)
    # each dimension is credited to the site that first covered it
    by_dim = {d["id"]: d["covered_by"] for d in p["dimensions"]}
    assert by_dim["access"] == "e_town" and by_dim["dryness"] == "e_desert"


def test_ice_sheets_are_never_picked():
    moon, earth = _world(polar=True)
    p = build_portfolio(moon, 0, earth)
    assert "e_ice" not in [s["tile_id"] for s in p["sites"]]
    assert p["candidates"] == len(earth.meta) - 1


def test_swing_earth_cannot_reach_is_flagged_not_dropped():
    """No Earth site swings 290 K, so thermal swing is covered by Earth's best."""
    moon, earth = _world()
    dims = {d["id"]: d for d in build_portfolio(moon, 0, earth)["dimensions"]}
    swing = dims["thermal_swing"]
    assert swing["earth_best_only"] and swing["covered_by"] == "e_desert"
    assert swing["threshold"] < 0.6
    assert not dims["slope"]["earth_best_only"]


def test_polar_target_wants_low_sun_and_frozen_ground():
    moon, earth = _world(polar=True)
    p = build_portfolio(moon, 0, earth)
    by_dim = {d["id"]: d["covered_by"] for d in p["dimensions"]}
    assert p["polar"]
    assert by_dim["sun_angle"] == "e_arctic"     # 78 N: sun as low as near the lunar pole
    assert by_dim["rock_ice"] == "e_arctic"      # the hot desert's ground never freezes


def test_noon_sun_is_low_at_the_poles():
    assert noon_sun_deg(0) == 90 and noon_sun_deg(-85) == 5


def test_greedy_cover_picks_the_fewest_on_a_textbook_case():
    # c alone covers x and y; a+b would need two picks for the same
    s = pd.DataFrame(dict(x=[1.0, 0.0, 1.0, 0.0], y=[0.0, 1.0, 1.0, 0.0],
                          z=[0.0, 0.0, 0.0, 1.0]), index=["a", "b", "c", "d"])
    picked, left = greedy_cover(s, dict(x=0.5, y=0.5, z=0.5))
    assert picked == ["c", "d"] and not left


def test_greedy_cover_reports_what_no_site_covers():
    s = pd.DataFrame(dict(x=[1.0], y=[0.0]), index=["a"])
    picked, left = greedy_cover(s, dict(x=0.5, y=0.0))
    assert picked == ["a"] and left == {"y"}
