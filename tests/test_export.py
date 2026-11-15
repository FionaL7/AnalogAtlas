"""The static export contract in ARCHITECTURE.md §4.2.

Runs the real script against the synthetic index, with NASA POWER switched off.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from analogatlas import config as C

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "03_export.py"


def load_script():
    """The filename starts with a digit, so import it by path."""
    spec = importlib.util.spec_from_file_location("export_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def exported(index_dir, tmp_path, monkeypatch):
    out = tmp_path / "out"
    module = load_script()
    monkeypatch.setattr("sys.argv", ["03_export.py", "--out", str(out), "--no-climate",
                                     "--k", "12", "--pairs", "2"])
    assert module.main() == 0
    return out


def read(path: Path):
    return json.loads(path.read_text())


def test_writes_every_file_in_the_contract(exported):
    assert (exported / "sites.json").exists()
    assert (exported / "dimensions.json").exists()
    assert (exported / "tiles" / "moon.json").exists()
    assert (exported / "tiles" / "earth.json").exists()
    assert list((exported / "analogs").glob("*.json"))
    assert list((exported / "twins").glob("*.json"))
    # #16 has not produced it, so it must be skipped rather than faked.
    assert not (exported / "validation.json").exists()


def test_moon_base_regions_are_served_by_the_polar_index(exported):
    """The whole point of #26: every Artemis region is past 80°S, so it belongs
    to `moon_polar`, and each one must come back with real Earth analogs."""
    sites = read(exported / "sites.json")
    regions = [s for s in sites if s.get("is_base_region")]
    assert regions, "the Artemis candidate regions must be exported"
    assert all(s["body"] == "moon_polar" for s in regions)
    assert all(s["in_index"] is True for s in regions)
    for site in regions:
        payload = read(exported / "analogs" / f"{site['id']}.json")
        assert payload["results"], f"{site['id']} got no analogs"
        assert all(h["tile_id"].startswith("earth_") for h in payload["results"])


def test_base_regions_stay_off_index_without_a_polar_index(index_dir, tmp_path, monkeypatch):
    """Falling back must mean 'say nothing', never 'clamp to the index edge'
    and publish analogs for a place 25° from the one named."""
    for suffix in ("meta.parquet", "shade.npy", "img.npy", "order.json"):
        (index_dir.path / f"moon_polar_{suffix}").unlink()
    out = tmp_path / "nopolar"
    module = load_script()
    monkeypatch.setattr("sys.argv", ["03_export.py", "--out", str(out), "--no-climate",
                                     "--k", "12", "--pairs", "2"])
    assert module.main() == 0
    regions = [s for s in read(out / "sites.json") if s.get("is_base_region")]
    assert regions and all(s["in_index"] is False for s in regions)
    for site in regions:
        assert not (out / "analogs" / f"{site['id']}.json").exists()


def test_polar_tiles_carry_their_projected_geometry_and_dimensions(exported):
    """The polar pane positions tiles in metres from the pole, and the polar
    dimensions are what a base is actually sited on."""
    tiles = read(exported / "tiles" / "moon_polar.json")
    assert tiles
    for t in tiles:
        x, y, size = t["xy"]
        assert size > 0 and abs(x) < 1e6 and abs(y) < 1e6
        assert 0.0 <= t["psr_frac"] <= 1.0
        assert 0.0 <= t["avg_illum"] <= t["illum_max"] <= 1.0
    ids = {d["id"] for d in read(exported / "dimensions.json")}
    assert {"sunlight-availability", "permanent-shadow", "direct-to-earth-comms"} <= ids


def test_in_index_moon_sites_do_get_analogs(exported):
    sites = read(exported / "sites.json")
    inside = [s for s in sites if s["body"] == "moon" and s["in_index"]]
    assert inside
    payload = read(exported / "analogs" / f"{inside[0]['id']}.json")
    assert payload["results"]
    for hit in payload["results"]:
        assert hit["tile_id"].startswith("earth_")
        assert 0.0 <= hit["visual_cos_scaled"] <= 1.0
        assert "known_analog" in hit


def test_site_ids_are_unique_and_url_safe(exported):
    sites = read(exported / "sites.json")
    ids = [s["id"] for s in sites]
    assert len(ids) == len(set(ids))
    assert all(id_.replace("-", "").isalnum() for id_ in ids)


def test_moon_tile_url_points_at_the_covering_trek_tile(exported):
    sites = read(exported / "sites.json")
    apollo = next(s for s in sites if s["id"].startswith("apollo-11"))
    # Apollo 11 is just north of the equator at ~23.5E -> y is the tile above
    # the equator, x the tile right of 180W + 23.5E.
    z, d = C.MOON_ZOOM, C.MOON_TILE_DEG
    assert f"/{z}/{int((90 - apollo['lat']) // d)}/{int((apollo['lon'] + 180) // d)}.jpg" \
        in apollo["tile_url"]


def test_tiles_layer_has_geometry_and_features(exported):
    tiles = read(exported / "tiles" / "earth.json")
    assert tiles
    for tile in tiles:
        assert len(tile["bbox"]) == 4
        assert tile["bbox"][0] <= tile["lon"] <= tile["bbox"][2]
        assert tile["bbox"][1] <= tile["lat"] <= tile["bbox"][3]
        assert "known_analog" in tile
    assert any(t["known_analog"] for t in tiles), "McMurdo must be tagged"
    # Moon tiles have no known_analog column at all.
    assert all("known_analog" not in t for t in read(exported / "tiles" / "moon.json"))


def test_dimensions_are_derived_from_breakdown(exported):
    dims = read(exported / "dimensions.json")
    by_id = {d["id"]: d for d in dims}
    assert by_id["atmosphere"]["earth_cannot_reproduce"] is True
    assert by_id["gravity"]["earth_cannot_reproduce"] is True
    assert by_id["surface-rock-cover"]["no_earth_equivalent"] is True
    assert by_id["median-slope"]["earth_cannot_reproduce"] is False
    assert by_id["median-slope"]["note"]
    # #20: every Earth's-limits row is marked by kind, not inferred from match.
    limits = {d["label"] for d in dims if d["kind"] == "earth_limit"}
    assert limits == {"Atmosphere", "Gravity", "Radiation", "Magnetic field",
                      "Day/night cycle", "Regolith dust"}
    assert all(d["earth_cannot_reproduce"] == (d["kind"] == "earth_limit") for d in dims)


def test_report_cards_are_complete_and_json_safe(exported):
    cards = list((exported / "twins").glob("*.json"))
    assert cards
    for path in cards:
        card = read(path)
        assert "__" in path.name
        assert card["climate"] is None          # --no-climate
        assert card["moon"]["tile_id"]
        assert card["earth"]["tile_id"]
        dims = {row["dimension"] for row in card["breakdown"]}
        assert {"Median slope", "Atmosphere", "Gravity"} <= dims
        for row in card["breakdown"]:
            assert row["match"] is None or 0.0 <= row["match"] <= 1.0
            assert row["id"]
            assert row["kind"] in ("compare", "no_equivalent", "earth_limit")


def test_report_cards_lead_with_new_candidates(exported):
    """The demo must open on candidates that are not already-known analogs."""
    sites = read(exported / "sites.json")
    site = next(s for s in sites if s["body"] == "moon" and s["in_index"])
    results = read(exported / "analogs" / f"{site['id']}.json")["results"]
    new_ones = {r["tile_id"] for r in results if r["known_analog"] is None}
    cards = [p.name for p in (exported / "twins").glob(f"{site['id']}__*.json")]
    if new_ones and len(new_ones) >= 2:
        assert all(any(n in name for n in new_ones) for name in cards)


def test_refuses_to_export_an_inconsistent_index(index_dir, tmp_path, monkeypatch):
    import numpy as np
    truncated = np.load(index_dir.path / "earth_shade.npy")[:-3]
    np.save(index_dir.path / "earth_shade.npy", truncated)
    module = load_script()
    monkeypatch.setattr("sys.argv", ["03_export.py", "--out", str(tmp_path / "o"), "--no-climate"])
    with pytest.raises(SystemExit, match="inconsistent"):
        module.main()


def test_missing_index_fails_with_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "INDEX", tmp_path / "empty")
    module = load_script()
    monkeypatch.setattr("sys.argv", ["03_export.py", "--out", str(tmp_path / "o")])
    with pytest.raises(SystemExit, match="No index for moon, earth"):
        module.main()


def test_traps_json_is_exported(exported):
    """#30: lookalike traps for the app's Traps panel, with the headline rate."""
    data = read(exported / "traps.json")
    assert set(data) == {"stats", "traps", "by_site"}
    (moon_stats, *_) = data["stats"]
    assert moon_stats["src_body"] == "moon"
    assert moon_stats["lookalikes_checked"] > 0
    assert 0.0 <= moon_stats["trap_rate"] <= 1.0
    for t in data["traps"]:
        assert t["breakers"] and all(b["reason"] for b in t["breakers"])
        assert t["visual_rank"] >= 1 and t["physics_rank"] >= 1
    earth_ids = [t["earth_tile_id"] for t in data["traps"]]
    assert len(earth_ids) == len(set(earth_ids))


def test_report_cards_say_what_to_test(exported):
    """C6: each exported report card carries field tests."""
    for path in (exported / "twins").glob("*.json"):
        card = read(path)
        assert set(card["field_tests"]) == {"tests", "avoid"}


def test_candidates_and_radar_are_exported_when_present(index_dir, tmp_path, monkeypatch):
    (index_dir.path / "candidates_moon.json").write_text(json.dumps(
        [{"tile_id": "earth_x", "lat": 1.0, "lon": 2.0, "score_pct": 99.0, "why": ["low rainfall"]}]))
    (index_dir.path / "moon_site_cpr.json").write_text(json.dumps(
        {"Haworth": {"lat": -87.45, "lon": -5.17, "cpr_median": 0.49887, "source": "Mini-RF"},
         "Nowhere": {"lat": 0, "lon": 0, "cpr_median": 0.1, "source": "Mini-RF"}}))
    out = tmp_path / "o"
    module = load_script()
    monkeypatch.setattr("sys.argv", ["03_export.py", "--out", str(out), "--no-climate",
                                     "--k", "12", "--pairs", "1"])
    assert module.main() == 0
    assert read(out / "candidates.json")["moon"][0]["tile_id"] == "earth_x"
    radar = read(out / "radar.json")
    assert set(radar) == {"haworth"}          # keyed by site id; unknown names dropped
    assert radar["haworth"]["cpr_median"] == 0.4989


def test_portfolios_are_exported_for_lunar_targets(exported):
    """#31: one portfolio per in-index lunar target, none for Earth sites."""
    files = {p.stem: read(p) for p in (exported / "portfolio").glob("*.json")}
    sites = read(exported / "sites.json")
    lunar = {s["id"] for s in sites if s["body"] != "earth" and s["in_index"]}
    assert set(files) == lunar and len(files) >= 3
    for p in files.values():
        assert {d["id"] for d in p["dimensions"]} >= {"shape", "slope", "access"}
        assert p["sites"] and all(s["covers"] for s in p["sites"])
