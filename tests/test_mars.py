"""Mars scoring, report card, field tests, traps and portfolio (#44) on a small
hand-built world with known answers."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analogatlas import config as C
from analogatlas.analog import (
    MARS_LIMITS, BodyIndex, breakdown, cross_body, load_index, mars_ice_rich,
)
from analogatlas.fieldtest import what_to_test
from analogatlas.portfolio import MARS_DIMENSIONS, build_portfolio, dimension_scores
from analogatlas.traps import check

from .conftest import write_index

DIM = 8
CLIMATE = {"TS_MIN": -40.0, "TS_MAX": 20.0, "T2M_RANGE": 20.0, "PRECTOTCORR": 0.02,
           "RH2M": 20.0, "WS10M": 5.0, "ALLSKY_SFC_SW_DWN": 6.0}


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


A = _unit([1, 0, 0, 0, 0, 0, 0, 0])


def _mars(lat=10.0, weh=3.0, **extra) -> BodyIndex:
    meta = pd.DataFrame(dict(
        tile_id=["mars_7_1_1"], body=["mars"], lat=[lat], lon=[20.0],
        slope_med=[2.0], relief_km=[1.0], thermal_inertia=[80.0], albedo=[0.28],
        dust_index=[0.9], weh_pct=[weh], hydrous_count=[2],
        t_max_k=[280.0], t_min_k=[180.0]))
    for k, v in extra.items():
        meta[k] = [v]
    return BodyIndex(meta, np.stack([A]), np.stack([A]))


def _earth(full: bool = True) -> BodyIndex:
    """Four tiles that all look exactly like the Mars tile and share its slope
    and relief, so only the Mars-specific terms can tell them apart."""
    names = ["e_dusty", "e_dark_rock", "e_glacier", "e_forest"]
    meta = pd.DataFrame(dict(
        tile_id=names, body="earth", lat=[25.0, 20.0, 70.0, 5.0], lon=[10.0, 30.0, 50.0, 70.0],
        slope_med=2.0, relief_km=1.0,
        ice_frac=[0.0, 0.0, 0.9, 0.0], veg_frac=[0.0, 0.0, 0.0, 0.8], water_frac=0.0,
        ndvi=[0.05, 0.05, 0.0, 0.7], aridity=[0.02, 0.05, 0.3, 1.5],
        barren_frac=[0.95, 0.9, 0.05, 0.0], sparse_frac=0.0,
        precip_mm=[10.0, 30.0, 300.0, 2500.0], access_min=[300.0, 200.0, 2000.0, 60.0],
        lst_hot_c=[55.0, 45.0, 2.0, 32.0], lst_cold_c=[-5.0, 5.0, -45.0, 20.0],
        lst_day_c=[42.0, 38.0, -12.0, 28.0], lst_night_c=[8.0, 22.0, -24.0, 22.0]))
    if full:
        meta["albedo"] = [0.30, 0.10, 0.80, 0.14]
        meta["lst_swing_c"] = [34.0, 16.0, 12.0, 6.0]
        meta["dust_aod"] = [0.30, 0.05, 0.01, 0.02]
        meta["lst_mean_c"] = [25.0, 30.0, -18.0, 25.0]
    shade = np.stack([A] * len(names))
    return BodyIndex(meta, shade, shade)


def _rows(mars: BodyIndex, earth: BodyIndex, name: str, climate=CLIMATE) -> dict[str, dict]:
    e = earth.meta.set_index("tile_id", drop=False).loc[name].copy()
    e["visual_cos_scaled"] = 0.95
    return {r["dimension"]: r for r in breakdown(mars.meta.iloc[0], e, climate).to_dict("records")}


# ---------------------------------------------------------------- scoring ----
def test_albedo_breaks_a_tie_on_looks_slope_and_relief():
    out = cross_body(_mars(), 0, _earth(), k=4)
    assert list(out.tile_id[:2]) == ["e_dusty", "e_dark_rock"]
    assert out.physical.iloc[0] > out.physical.iloc[1]


def test_ice_is_pushed_down_for_a_dry_mars_tile_but_not_an_icy_one():
    dry = cross_body(_mars(), 0, _earth(), k=4).set_index("tile_id")
    assert dry.loc["e_glacier", "env_pushed"] and dry.loc["e_forest", "env_pushed"]

    icy_mars = _mars(lat=48.0, weh=9.0)
    assert mars_ice_rich(icy_mars.meta.iloc[0])
    icy = cross_body(icy_mars, 0, _earth(), k=4).set_index("tile_id")
    assert not icy.loc["e_glacier", "env_pushed"]
    assert icy.loc["e_forest", "env_pushed"]          # plants are never an analog


def test_hydrogen_near_the_equator_is_not_ice():
    assert not mars_ice_rich(_mars(lat=5.0, weh=9.0).meta.iloc[0])


def test_scoring_works_before_the_new_columns_exist():
    """A2 and A3 may land later: no Mars albedo, no Earth albedo, no crash."""
    mars = _mars()
    mars.meta = mars.meta.drop(columns=["albedo", "thermal_inertia", "dust_index", "weh_pct"])
    out = cross_body(mars, 0, _earth(full=False), k=4)
    assert len(out) == 4 and out.physical.notna().all()
    # no albedo on either side: slope and relief (identical, 1.0) and dryness (rainfall has always been in the index) are what score
    first = _earth(full=False).meta.set_index("tile_id").loc[out.tile_id.iloc[0]]
    assert out.physical.iloc[0] == pytest.approx((2.0 + np.exp(-first.precip_mm / 182.5)) / 3)


# ------------------------------------------------------------ report card ----
def test_report_card_rows_and_their_basis():
    rows = _rows(_mars(), _earth(), "e_dusty")
    assert rows["Median slope"]["basis"] == "measured"
    assert rows["Surface brightness (albedo)"]["basis"] == "measured"
    assert rows["Surface material"]["basis"] == "proxy"
    assert rows["Dust"]["basis"] == "proxy"
    assert rows["Coldest surface"]["basis"] == "modelled"
    assert rows["Water-altered minerals"]["kind"] == "no_equivalent"
    assert rows["Near-surface water"]["kind"] == "no_equivalent"
    assert "Ground ice" not in rows                       # dry tile
    assert rows["Day length"]["match"] > 0.9
    # loose dust on Mars, big day-night swing and dusty air on Earth: both hold
    assert rows["Surface material"]["match"] > 0.8
    assert rows["Dust"]["match"] > 0.8
    assert rows["Surface brightness (albedo)"]["match"] > 0.8


def test_mars_limits_are_fixed_rows_and_not_the_moon_ones():
    rows = _rows(_mars(), _earth(), "e_dusty")
    limits = [r for r in rows.values() if r["kind"] == "earth_limit"]
    assert [r["dimension"] for r in limits] == [lim["dimension"] for lim in MARS_LIMITS]
    assert all(r["match"] == 0 for r in limits)
    assert "CO₂" in rows["Atmosphere"]["moon"]
    assert "Regolith dust" not in rows and "Day/night cycle" not in rows


def test_ground_ice_row_only_for_an_icy_tile_and_matches_frozen_ground():
    icy = _mars(lat=48.0, weh=9.0)
    assert _rows(icy, _earth(), "e_glacier")["Ground ice"]["match"] == pytest.approx(1.0)
    assert _rows(icy, _earth(), "e_dusty")["Ground ice"]["match"] < 0.2
    # without lst_mean_c the mean of the day and night means stands in
    assert _rows(icy, _earth(full=False), "e_glacier")["Ground ice"]["match"] == pytest.approx(1.0)


def test_report_card_survives_missing_columns_and_no_climate():
    mars = _mars()
    mars.meta = mars.meta[["tile_id", "body", "lat", "lon", "slope_med", "relief_km"]]
    rows = _rows(mars, _earth(full=False), "e_dusty", climate=None)
    assert {"Median slope", "Local relief", "Day length", "Atmosphere"} <= set(rows)
    for absent in ("Surface material", "Dust", "Surface brightness (albedo)",
                   "Coldest surface", "Near-surface water", "Water-altered minerals"):
        assert absent not in rows


def test_nan_values_drop_the_row_instead_of_faking_it():
    rows = _rows(_mars(dust_index=float("nan"), albedo=float("nan")), _earth(), "e_dusty")
    assert "Dust" not in rows and "Surface brightness (albedo)" not in rows


def test_moon_rows_now_carry_a_basis_too():
    moon = pd.Series(dict(tile_id="m", slope_med=2.0, relief_km=1.0, t_max_k=390.0,
                          t_min_k=100.0, rock_abundance=0.01))
    e = _earth().meta.iloc[0].copy()
    rows = {r["dimension"]: r for r in breakdown(moon, e, CLIMATE).to_dict("records")}
    assert rows["Median slope"]["basis"] == "measured"
    assert rows["Coldest surface"]["basis"] == "modelled"
    assert "Regolith dust" in rows and "Day length" not in rows


# ------------------------------------------------------------ field tests ----
def test_field_tests_use_the_mars_rules():
    rows = list(_rows(_mars(), _earth(), "e_dusty").values())
    out = what_to_test(rows, body="mars")
    titles = [t["title"] for t in out["tests"]]
    assert "Wheel and soil mechanics" in titles and "Dust on hardware" in titles
    assert "Surviving long darkness" not in titles                     # a Moon rule
    mobility = next(t for t in out["tests"] if t["title"].startswith("Rover mobility"))
    assert "2.6x Mars" in mobility["detail"]
    assert any(a["dimension"] == "Water-altered minerals" for a in out["avoid"])


def test_ice_drilling_is_suggested_only_on_frozen_ground():
    icy = _mars(lat=48.0, weh=9.0)
    def titles(name):
        return [t["title"] for t in what_to_test(list(_rows(icy, _earth(), name).values()), "mars")["tests"]]
    assert "Drilling for ground ice (ISRU)" in titles("e_glacier")
    assert "Drilling for ground ice (ISRU)" not in titles("e_dusty")


def test_avoid_notes_name_mars_not_the_moon():
    rows = list(_rows(_mars(), _earth(), "e_forest").values())
    reasons = " ".join(a["reason"] for a in what_to_test(rows, body="mars")["avoid"])
    assert "(Mars " in reasons and "(Moon " not in reasons


# ------------------------------------------------------------------ traps ----
def test_ice_is_a_trap_for_dry_mars_but_not_for_icy_mars():
    glacier = _earth().meta.iloc[2]
    dry_hits = {h["id"]: h for h in check(_mars().meta.iloc[0], glacier)}
    assert "ice" in dry_hits and "Mars" in dry_hits["ice"]["reason"]
    assert "Moon" not in dry_hits["ice"]["reason"]
    icy_hits = {h["id"] for h in check(_mars(lat=48.0, weh=9.0).meta.iloc[0], glacier)}
    assert "ice" not in icy_hits


def test_plants_are_a_trap_for_any_mars_tile():
    forest = _earth().meta.iloc[3]
    for mars in (_mars(), _mars(lat=48.0, weh=9.0)):
        assert "vegetation" in {h["id"] for h in check(mars.meta.iloc[0], forest)}


# -------------------------------------------------------------- portfolio ----
def test_portfolio_uses_the_mars_dimensions():
    p = build_portfolio(_mars(), 0, _earth())
    ids = [d["id"] for d in p["dimensions"]]
    assert ids == [d.id for d in MARS_DIMENSIONS]
    assert "sun_angle" not in ids and {"material", "brightness"} <= set(ids)
    picked = [s["tile_id"] for s in p["sites"]]
    assert picked[0] == "e_dusty"
    assert "e_forest" not in picked and "e_glacier" not in picked      # traps for a dry tile
    words = {d["id"]: d["moon"] for d in p["dimensions"]}
    assert "loose dust" in words["material"] and words["rock_ice"] == "bare rock and dust"


def test_portfolio_for_an_icy_tile_can_pick_frozen_ground():
    icy = _mars(lat=48.0, weh=9.0)
    s = dimension_scores(icy, 0, _earth()).set_index(_earth().meta.tile_id)
    assert s.loc["e_glacier", "rock_ice"] > 0.8        # ice counts, and it is frozen
    assert s.loc["e_dusty", "rock_ice"] < 0.2          # bare, but far too warm
    p = build_portfolio(icy, 0, _earth())
    assert "e_glacier" in [x["tile_id"] for x in p["sites"]]


def test_portfolio_before_the_new_columns_exist():
    mars = _mars()
    mars.meta = mars.meta.drop(columns=["albedo", "thermal_inertia"])
    p = build_portfolio(mars, 0, _earth(full=False))
    assert {"material", "brightness"} <= set(p["uncovered"])
    assert p["sites"]                                    # the rest is still covered


# -------------------------------------------------------- synthetic index ----
def test_synthetic_mars_index_runs_end_to_end(tmp_path, monkeypatch):
    """The conftest Mars index has every contract column and loads like the Moon's."""
    write_index(tmp_path, bodies=("mars", "earth"))
    monkeypatch.setattr(C, "INDEX", tmp_path)
    mars, earth = load_index("mars"), load_index("earth")
    for col in ("thermal_inertia", "albedo", "dust_index", "weh_pct", "hydrous_count",
                "t_max_k", "t_min_k"):
        assert col in mars.meta
    assert mars_ice_rich(mars.meta.iloc[0]) and not mars_ice_rich(mars.meta.iloc[1])
    out = cross_body(mars, 1, earth, k=5)
    assert len(out) == 5 and np.isfinite(out.score).all()
    e = out.iloc[0].copy()
    rows = breakdown(mars.meta.iloc[1], e, CLIMATE)
    assert {"compare", "no_equivalent", "earth_limit"} == set(rows.kind)
    assert set(rows.basis) <= {"measured", "modelled", "proxy"}
    assert build_portfolio(mars, 1, earth)["sites"]


def test_mid_latitude_ice_sites_are_ice_rich_without_hydrogen():
    """GRS hydrogen is missing or under 6% at Arcadia, Deuteronilus and Utopia,
    yet those are the ice landing sites: latitude decides (#42)."""
    from analogatlas.sites import MARS_SITES
    for name in ("Arcadia Planitia", "Deuteronilus Mensae", "Utopia Planitia"):
        lat, _ = MARS_SITES[name]
        assert mars_ice_rich(_mars(lat=lat, weh=float("nan")).meta.iloc[0]), name
    for name in ("Jezero crater", "Gale crater", "Oxia Planum", "Medusae Fossae"):
        lat, _ = MARS_SITES[name]
        assert not mars_ice_rich(_mars(lat=lat, weh=9.0).meta.iloc[0]), name


def test_ground_ice_row_is_modelled_and_hydrogen_stays_as_context():
    rows = _rows(_mars(lat=48.0, weh=4.0), _earth(), "e_glacier")
    assert rows["Ground ice"]["basis"] == "modelled"
    assert "not measured in this tile" in rows["Ground ice"]["note"]
    assert rows["Near-surface water"]["kind"] == "no_equivalent"


def test_dust_index_is_relative_dustiness():
    dusty = _rows(_mars(dust_index=0.95), _earth(), "e_dusty")["Dust"]
    clear = _rows(_mars(dust_index=0.05), _earth(), "e_dusty")["Dust"]
    assert dusty["match"] > 0.9 > clear["match"]
    assert dusty["moon"].startswith("dust-covered") and clear["moon"].startswith("mostly dust-free")


# ---------------------------------------------- dryness and frozen ground ----
def test_a_wet_earth_tile_scores_lower_for_any_mars_tile():
    """Mars has no liquid water, so rainfall now counts against a tile (#42)."""
    earth = _earth()
    earth.meta = earth.meta.copy()
    earth.meta["precip_mm"] = [10.0, 10.0, 10.0, 10.0]
    earth.meta.loc[1, "precip_mm"] = 2500.0           # e_dark_rock gets very wet
    phys = dict(zip(earth.meta.tile_id, cross_body(_mars(), 0, earth, k=4).physical))
    dry = dict(zip(earth.meta.tile_id, cross_body(_mars(), 0, _earth(), k=4).physical))
    assert phys["e_dark_rock"] < dry["e_dark_rock"]
    assert phys["e_dusty"] == pytest.approx(dry["e_dusty"])


def test_frozen_ground_counts_only_for_an_ice_rich_mars_tile():
    earth = _earth()
    dry = {r.tile_id: r.physical for r in cross_body(_mars(lat=10.0), 0, earth, k=4).itertuples()}
    icy = {r.tile_id: r.physical for r in cross_body(_mars(lat=48.0), 0, earth, k=4).itertuples()}
    # e_glacier is frozen (-18 C mean) and e_dusty is warm (25 C)
    assert icy["e_glacier"] - icy["e_dusty"] > dry["e_glacier"] - dry["e_dusty"] + 0.2
    # a warm tile is unaffected by which kind of Mars tile asks
    assert icy["e_dusty"] < dry["e_dusty"]


def test_ice_site_top_analog_is_frozen_ground_not_a_warm_plain():
    earth = _earth()
    earth.meta = earth.meta.copy()
    earth.meta["ice_frac"] = 0.0                       # so the push-down is not the reason
    top = cross_body(_mars(lat=48.0), 0, earth, k=4, w_phys=1.0).tile_id.iloc[0]
    assert top == "e_glacier"


def test_moon_physical_score_is_still_just_slope_and_relief():
    """The Mars terms must not leak into the Moon: its physical score is the
    original mean of slope and relief closeness, with no rainfall or albedo."""
    import analogatlas.analog as A
    moon = pd.Series(dict(tile_id="m", lat=10.0, slope_med=2.0, relief_km=1.0))
    earth = _earth()
    earth.meta = earth.meta.copy()
    earth.meta["precip_mm"] = 5000.0                   # would crush a Mars score
    expected = np.mean([A._closeness(earth.meta.slope_med.values, 2.0, 1.0),
                        A._closeness(earth.meta.relief_km.values, 1.0, 1.0)], axis=0)
    assert np.allclose(A._physical(moon, earth.meta), expected)
