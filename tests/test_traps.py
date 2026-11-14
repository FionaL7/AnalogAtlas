"""Lookalike traps (#30) on a small hand-built world with known answers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analogatlas.analog import BodyIndex, cross_body
from analogatlas.traps import check, find_traps, traps_for_tile

DIM = 8


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


A = _unit([1, 0, 0, 0, 0, 0, 0, 0])      # "flat plain" look
B = _unit([0, 1, 0, 0, 0, 0, 0, 0])      # "rough highland" look


def _world(with_env: bool = True):
    moon_meta = pd.DataFrame(dict(
        tile_id=["m_plain", "m_rough"], lat=[10.0, -30.0], lon=[20.0, 40.0],
        slope_med=[0.5, 8.0], relief_km=[0.3, 3.0]))
    moon = BodyIndex(moon_meta, np.stack([A, B]), np.stack([A, B]))

    rng = np.random.default_rng(1)
    shade = [A,                                   # e_ice: looks exactly like the plain
             _unit(0.97 * A + 0.03 * B),          # e_good: looks like it, and is a real analog
             _unit(0.95 * A + 0.05 * B),          # e_forest: looks like it, but plants
             B]                                   # e_flat: looks like the highland, but flat
    shade += [_unit(rng.normal(size=DIM)) for _ in range(6)]   # unrelated tiles
    n = len(shade)
    earth_meta = pd.DataFrame(dict(
        tile_id=["e_ice", "e_good", "e_forest", "e_flat"] + [f"e_{k}" for k in range(6)],
        lat=np.linspace(-70, 70, n), lon=np.linspace(-170, 170, n),
        slope_med=[0.4, 0.6, 0.5, 0.3] + [3.0] * 6,
        relief_km=[0.25, 0.35, 0.3, 0.2] + [1.0] * 6,
        known_analog=[None] * n))
    if with_env:
        earth_meta["ice_frac"] = [0.9, 0.0, 0.0, 0.0] + [0.0] * 6
        earth_meta["veg_frac"] = [0.0, 0.0, 0.8, 0.0] + [0.0] * 6
        earth_meta["water_frac"] = [0.0] * n
        earth_meta["ndvi"] = [0.0, 0.05, 0.7, 0.05] + [0.1] * 6
        earth_meta["aridity"] = [5.0, 0.1, 1.2, 0.1] + [0.1] * 6   # ice: PET -> 0, capped high
    earth = BodyIndex(earth_meta, np.stack(shade), np.stack(shade))
    return moon, earth


def _by_earth(traps):
    return {t["earth_tile_id"]: t for t in traps}


def test_lookalikes_that_break_physically_are_traps():
    moon, earth = _world()
    traps = _by_earth(traps_for_tile(moon, 0, earth, "moon", top_n=4))
    assert {b["id"] for b in traps["e_ice"]["breakers"]} == {"ice"}
    assert "vegetation" in {b["id"] for b in traps["e_forest"]["breakers"]}
    assert "wet_climate" in {b["id"] for b in traps["e_forest"]["breakers"]}
    # the genuine analog is not a trap
    assert "e_good" not in traps
    # the ice sheet is the image-only AI's top pick
    assert traps["e_ice"]["visual_rank"] == 1
    assert traps["e_ice"]["visual_pct"] > 0.8


def test_ice_is_not_also_called_a_wet_climate():
    moon, earth = _world()
    ice = _by_earth(traps_for_tile(moon, 0, earth, "moon", top_n=4))["e_ice"]
    assert "wet_climate" not in {b["id"] for b in ice["breakers"]}


def test_shape_mismatch_is_a_trap_even_without_environment_data():
    moon, earth = _world(with_env=False)
    traps = _by_earth(traps_for_tile(moon, 1, earth, "moon", top_n=1))
    flat = traps["e_flat"]
    assert {b["id"] for b in flat["breakers"]} >= {"slope", "relief"}
    assert "8.0°" in next(b["reason"] for b in flat["breakers"] if b["id"] == "slope")
    # no environment columns: no environment breakers anywhere, and no crash
    for t in traps_for_tile(moon, 0, earth, "moon", top_n=4):
        assert not any(b["environment"] for b in t["breakers"])


def test_our_search_ranks_the_ice_trap_far_below_its_looks():
    """The ice sheet is the #1 lookalike, but our search pushes it down (#33)."""
    moon, earth = _world()
    ice = _by_earth(traps_for_tile(moon, 0, earth, "moon", top_n=4))["e_ice"]
    assert ice["visual_rank"] == 1
    assert ice["physics_rank"] > 3


def test_search_puts_the_genuine_analog_above_ice_and_forest():
    moon, earth = _world()
    hits = cross_body(moon, 0, earth, k=len(earth.meta))
    order = list(hits.tile_id)
    assert order[0] == "e_good"
    assert order.index("e_ice") > 3 and order.index("e_forest") > 3
    assert bool(hits.set_index("tile_id").env_pushed["e_ice"])


def test_no_physical_weight_is_the_image_only_ranking():
    moon, earth = _world()
    assert cross_body(moon, 0, earth, k=1, w_phys=0.0).tile_id.iloc[0] == "e_ice"


def test_no_environment_data_means_no_push_down():
    moon, earth = _world(with_env=False)
    hits = cross_body(moon, 0, earth, k=3)
    assert "e_ice" in set(hits.tile_id) and not hits.env_pushed.any()


def test_model_score_is_passed_through_when_available():
    moon, earth = _world()
    t = _by_earth(traps_for_tile(moon, 0, earth, "moon", top_n=4,
                                 model_scores={"e_ice": 0.03}))
    assert t["e_ice"]["model_score_pct"] == 0.03
    assert t["e_forest"]["model_score_pct"] is None


def test_find_traps_dedupes_and_leads_with_environment_reasons():
    moon, earth = _world()
    traps = find_traps(moon, earth, "moon", top_n=4, limit=10)
    earth_ids = [t["earth_tile_id"] for t in traps]
    src_ids = [t["src_tile_id"] for t in traps]
    assert len(earth_ids) == len(set(earth_ids)) and len(src_ids) == len(set(src_ids))
    assert any(b["environment"] for b in traps[0]["breakers"])


def test_check_reasons_are_plain_words_with_numbers():
    moon = pd.Series(dict(slope_med=0.5, relief_km=0.3))
    earth = pd.Series(dict(slope_med=0.4, relief_km=0.25, ice_frac=0.82, veg_frac=0.0,
                           water_frac=0.0, ndvi=0.0, aridity=10.0))
    (ice,) = check(moon, earth)
    assert ice["label"] == "Ice sheet, not rock" and "82%" in ice["reason"]
