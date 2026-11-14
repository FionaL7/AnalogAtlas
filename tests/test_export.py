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


def test_moon_base_regions_are_flagged_as_outside_the_index(exported):
    """The index stops at 60°S; every Artemis region is past 80°S. Publishing
    analogs for them would mean publishing a tile 25° from the named place."""
    sites = read(exported / "sites.json")
    regions = [s for s in sites if s.get("is_base_region")]
    assert regions, "the Artemis candidate regions must be exported"
    assert all(s["in_index"] is False for s in regions)
    for site in regions:
        assert not (exported / "analogs" / f"{site['id']}.json").exists()


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
