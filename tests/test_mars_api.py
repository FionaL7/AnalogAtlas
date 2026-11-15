"""Mars through the API and the static export (#42), on the synthetic index.

The real Mars index comes from #38; these run on `tests/conftest.py`'s
synthetic one, so the wiring is checked before the data exists.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from analogatlas import config as C
from analogatlas.sites import MARS_SITES

from .conftest import write_index

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "03_export.py"


@pytest.fixture
def mars_dir(index_dir):
    """The usual synthetic index plus a Mars body, and #29 scores for both targets."""
    write_index(index_dir.path, bodies=("mars",))
    earth = pd.read_parquet(index_dir.path / "earth_meta.parquet")
    pd.DataFrame({"tile_id": earth.tile_id, "analog_score_moon": 0.25,
                  "analog_score_mars": 0.75}).to_parquet(index_dir.path / "earth_scores.parquet")
    index_dir.mars = pd.read_parquet(index_dir.path / "mars_meta.parquet")
    return index_dir


@pytest.fixture
def mars_client(mars_dir, stub_clip, monkeypatch):
    from fastapi.testclient import TestClient

    from api import main as api_main
    from api.routers import twins as twins_router

    monkeypatch.setattr(twins_router, "earth_climate", lambda lat, lon: {
        "TS_MIN": -20.0, "TS_MAX": 45.0, "T2M_RANGE": 15.0, "PRECTOTCORR": 0.02,
        "RH2M": 20.0, "WS10M": 5.0, "ALLSKY_SFC_SW_DWN": 6.5,
    })
    with TestClient(api_main.create_app()) as c:
        yield c


# --------------------------------------------------------------------- API ---
def test_health_lists_mars(mars_client, mars_dir):
    bodies = mars_client.get("/health").json()["bodies"]
    assert bodies["mars"] == len(mars_dir.mars)


def test_search_on_mars(mars_client):
    r = mars_client.post("/search", json={"body": "mars", "query": "layered canyon", "k": 4})
    assert r.status_code == 200
    assert all(h["tile_id"].startswith("mars_") for h in r.json()["results"])


def test_analogs_for_a_mars_tile_are_on_earth_with_the_mars_model_score(mars_client, mars_dir):
    row = mars_dir.mars.iloc[1]
    r = mars_client.post("/analogs", json={"src_body": "mars", "lat": float(row.lat),
                                           "lon": float(row.lon), "k": 5})
    assert r.status_code == 200
    out = r.json()
    assert out["src_tile"]["tile_id"] == row.tile_id
    assert all(h["tile_id"].startswith("earth_") for h in out["results"])
    assert {h["model_score"] for h in out["results"]} == {0.75}      # Mars column, not Moon


def test_moon_analogs_still_use_the_moon_model_score(mars_client, mars_dir):
    moon = mars_dir.meta["moon"].iloc[0]
    r = mars_client.post("/analogs", json={"src_body": "moon", "lat": float(moon.lat),
                                           "lon": float(moon.lon), "k": 3})
    assert {h["model_score"] for h in r.json()["results"]} == {0.25}


def test_earth_to_mars_with_dst_body(mars_client):
    r = mars_client.post("/analogs", json={"src_body": "earth", "lat": -24.1, "lon": -69.9,
                                           "k": 4, "dst_body": "mars"})
    assert r.status_code == 200
    hits = r.json()["results"]
    assert hits and all(h["tile_id"].startswith("mars_") for h in hits)
    assert all(h["model_score"] is None for h in hits)       # no model scores Mars tiles
    # without dst_body an Earth source still finds Moon terrain
    r = mars_client.post("/analogs", json={"src_body": "earth", "lat": -24.1, "lon": -69.9, "k": 2})
    assert all(h["tile_id"].startswith("moon_") for h in r.json()["results"])


@pytest.mark.parametrize("body", [
    {"src_body": "mars", "lat": 0, "lon": 0, "dst_body": "moon"},      # Mars always pairs with Earth
    {"src_body": "earth", "lat": 0, "lon": 0, "dst_body": "moon_polar"},  # too small to search from Earth
    {"src_body": "earth", "lat": 0, "lon": 0, "dst_body": "earth"},
])
def test_dst_body_is_validated(mars_client, body):
    assert mars_client.post("/analogs", json=body).status_code == 422


def test_mars_report_card(mars_client, mars_dir):
    row = mars_dir.mars.iloc[1]
    hits = mars_client.post("/analogs", json={"src_body": "mars", "lat": float(row.lat),
                                              "lon": float(row.lon), "k": 1}).json()["results"]
    out = mars_client.get("/twins", params={"src_tile_id": row.tile_id,
                                            "earth_tile_id": hits[0]["tile_id"],
                                            "src_body": "mars"}).json()
    rows = {r["dimension"]: r for r in out["breakdown"]}
    assert "Soil chemistry" in rows and "Regolith dust" not in rows      # Mars limits
    assert rows["Median slope"]["basis"] == "measured"
    assert rows["Coldest surface"]["basis"] == "modelled"
    # the synthetic Earth tiles have no lst_swing_c, so the stand-in row is left out, not faked
    assert "Surface material" not in rows
    assert all(r["basis"] in {"measured", "modelled", "proxy"} for r in out["breakdown"])
    assert out["model_score"] == 0.75
    assert out["moon"]["body"] == "mars"
    # Mars field-test rules: avoid notes name Mars, not the Moon
    assert all("(Moon " not in a["reason"] for a in out["field_tests"]["avoid"])


def test_twins_refuses_earth_as_the_source(mars_client, mars_dir):
    earth_id = mars_dir.meta["earth"].tile_id.iloc[0]
    r = mars_client.get("/twins", params={"src_tile_id": earth_id, "earth_tile_id": earth_id,
                                          "src_body": "earth"})
    assert r.status_code == 400


# ------------------------------------------------------------------ export ---
def _export(out: Path):
    spec = importlib.util.spec_from_file_location("export_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import sys
    argv = sys.argv
    sys.argv = ["03_export.py", "--out", str(out), "--no-climate", "--k", "12", "--pairs", "2"]
    try:
        assert module.main() == 0
    finally:
        sys.argv = argv


def read(path: Path):
    return json.loads(path.read_text())


@pytest.fixture
def exported_mars(mars_dir, tmp_path):
    out = tmp_path / "out"
    _export(out)
    return out


def test_export_writes_every_mars_site_with_analogs(exported_mars):
    sites = [s for s in read(exported_mars / "sites.json") if s["body"] == "mars"]
    assert [s["name"] for s in sites] == list(MARS_SITES)
    assert all(s["in_index"] and s["blurb"] for s in sites)
    for s in sites:
        payload = read(exported_mars / "analogs" / f"{s['id']}.json")
        assert payload["src_tile"]["tile_id"].startswith("mars_")
        assert {r["model_score"] for r in payload["results"]} == {0.75}


def test_export_mars_tiles_carry_the_mars_columns(exported_mars, mars_dir):
    tiles = read(exported_mars / "tiles" / "mars.json")
    assert len(tiles) == len(mars_dir.mars)
    for col in ("thermal_inertia", "albedo", "dust_index", "weh_pct", "hydrous_count"):
        assert col in tiles[0]


def test_export_mars_report_cards_have_basis_and_mars_tests(exported_mars):
    cards = list((exported_mars / "twins").glob("jezero-crater__*.json"))
    assert cards
    card = read(cards[0])
    assert card["moon"]["body"] == "mars"
    assert all(r["basis"] in {"measured", "modelled", "proxy"} for r in card["breakdown"])
    dims = {r["dimension"] for r in card["breakdown"]}
    assert "Global dust storms" in dims and "Magnetic field" not in dims
    # Moon cards carry a basis too
    moon_card = read(next((exported_mars / "twins").glob("tycho-crater__*.json")))
    assert all(r["basis"] for r in moon_card["breakdown"])


def test_export_mars_traps_portfolio_and_dimensions(exported_mars):
    traps = read(exported_mars / "traps.json")
    assert "mars" in {s["src_body"] for s in traps["stats"]}
    assert "jezero-crater" in traps["by_site"]
    mars_traps = [t for t in traps["by_site"]["jezero-crater"]]
    assert all(t["model_score_pct"] == 0.75 for t in mars_traps)

    p = read(exported_mars / "portfolio" / "jezero-crater.json")
    assert p["body"] == "mars"
    assert "material" in {d["id"] for d in p["dimensions"]}

    dims = {d["label"]: d for d in read(exported_mars / "dimensions.json")}
    assert dims["Soil chemistry"]["bodies"] == ["mars"]
    assert dims["Regolith dust"]["bodies"] == ["moon"]
    assert dims["Atmosphere"]["bodies"] == ["mars", "moon"]


def test_export_without_a_mars_index_lists_mars_sites_off_index(index_dir, tmp_path):
    out = tmp_path / "out"
    _export(out)
    sites = [s for s in read(out / "sites.json") if s["body"] == "mars"]
    assert len(sites) == len(MARS_SITES) and not any(s["in_index"] for s in sites)
    assert not (out / "tiles" / "mars.json").exists()
    assert not list((out / "analogs").glob("jezero-crater*"))
