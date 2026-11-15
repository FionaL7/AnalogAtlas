"""The validation contract (#16): what `scripts/05_validate.py` must write.

Runs the real script against the synthetic index and a hand-built crater
catalog, so the numbers are arbitrary but the shape and the invariants are not.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analogatlas import config as C, craters

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "05_validate.py"


def load_script():
    """The filename starts with a digit, so import it by path."""
    spec = importlib.util.spec_from_file_location("validate_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def validated(index_dir, tmp_path, monkeypatch):
    """Run the script over the synthetic index; return validation.json."""
    # One crater per tile for the first third, more for the rest, so the density
    # terciles are not all the same class.
    moon = index_dir.meta["moon"]
    rows = []
    for i, t in enumerate(moon.itertuples()):
        for j in range(1 + i % 7):
            rows.append((t.lat, t.lon % 360, 2.0 + 10 * (j == 0) + 40 * (i % 5 == 0)))
    path = tmp_path / "robbins" / "catalog.csv"
    from tests.test_craters import write_catalog
    write_catalog(path, rows)
    monkeypatch.setattr(craters, "CATALOG", path)

    module = load_script()
    monkeypatch.setattr("sys.argv", ["05_validate.py", "--ks", "5", "10", "--no-chart"])
    assert module.main() == 0
    return json.loads((C.INDEX / "validation.json").read_text())


def test_writes_both_keys_and_keeps_the_others(index_dir, validated):
    assert "crater_retrieval" in validated
    assert "known_analog_ranking" in validated


def test_does_not_clobber_the_model_key(index_dir, tmp_path, monkeypatch):
    """#29 writes `analog_model` into the same file; #16 must merge, not replace."""
    (C.INDEX / "validation.json").write_text(json.dumps({"analog_model": {"keep": "me"}}))
    moon = index_dir.meta["moon"]
    path = tmp_path / "robbins" / "catalog.csv"
    from tests.test_craters import write_catalog
    write_catalog(path, [(t.lat, t.lon % 360, 5.0) for t in moon.itertuples()])
    monkeypatch.setattr(craters, "CATALOG", path)

    module = load_script()
    monkeypatch.setattr("sys.argv", ["05_validate.py", "--ks", "5", "--no-chart"])
    assert module.main() == 0
    out = json.loads((C.INDEX / "validation.json").read_text())
    assert out["analog_model"] == {"keep": "me"}
    assert "crater_retrieval" in out


def test_json_has_no_nan_tokens(index_dir, validated):
    """`json.dumps` writes bare NaN, which `JSON.parse` in the browser rejects.
    The Methodology page fetches this file, so it has to be strict JSON."""
    text = (C.INDEX / "validation.json").read_text()
    assert "NaN" not in text and "Infinity" not in text
    json.loads(text, parse_constant=lambda c: pytest.fail(f"non-JSON constant {c!r}"))


def test_crater_labels_are_saved_for_other_devices(index_dir, validated):
    """The 227 MB catalog is downloaded once; the labels travel with the index."""
    labels = pd.read_parquet(C.INDEX / "moon_craters.parquet")
    assert list(labels.tile_id) == list(index_dir.meta["moon"].tile_id)
    assert set(craters.LABEL_COLUMNS) <= set(labels.columns)


def test_precision_is_a_fraction_and_has_a_baseline(index_dir, validated):
    crater = validated["crater_retrieval"]
    groups = [crater["density_class"]["overall"], crater["big_crater"],
              *crater["density_class"]["by_class"].values()]
    for g in groups:
        assert 0.0 <= g["random_baseline"] <= 1.0
        for k in (5, 10):
            assert 0.0 <= g[f"p_at_{k}"] <= 1.0


def test_known_analogs_are_ranked_against_the_whole_earth_index(index_dir, validated):
    ranking = validated["known_analog_ranking"]
    assert ranking["earth_tiles_ranked"] == len(index_dir.meta["earth"])
    for row in ranking["sites"]:
        for setting in ("shipped", "image_only"):
            if setting in row:
                assert 1 <= row[setting]["rank"] <= ranking["earth_tiles_ranked"]
                assert 0 <= row[setting]["top_pct"] <= 100
                assert row[setting]["role"] in row["tested_roles"]


def test_mars_analogs_are_reported_but_not_scored(index_dir, validated):
    """Ranking a Mars analog from a lunar site measures nothing, so it must not
    move the summary either way."""
    ranking = validated["known_analog_ranking"]
    scored = [r for r in ranking["sites"] if r["moon_target"] and "shipped" in r]
    assert ranking["summary"]["n"] == len(scored)


def test_every_known_analog_is_either_ranked_or_given_a_reason(index_dir, validated):
    from analogatlas.sites import ANALOG_INFO

    ranking = validated["known_analog_ranking"]
    accounted = {r["site"] for r in ranking["sites"]} | set(ranking["skipped_sites"])
    assert accounted == set(ANALOG_INFO)


def test_process_analogs_are_skipped_with_learn_pys_reason(index_dir, validated):
    skipped = validated["known_analog_ranking"]["skipped_sites"]
    assert "process analog" in skipped["Ries Crater, Germany"]


def test_polar_block_names_the_tile_each_region_resolved_to(index_dir, validated):
    """Artemis regions are ~15 km and our tiles 85 km, so regions can share one.
    Identical rows have to be explainable (#32)."""
    polar = validated["polar_analog_ranking"]
    for site, row in polar["by_query_site"].items():
        assert row["query_tile"].startswith("moonsp_")
        for name, r in row["analogs"].items():
            assert 1 <= r["rank"] <= polar["earth_tiles_ranked"]


def test_neighbours_never_returns_the_query_itself(index_dir):
    """A tile is its own nearest neighbour, which would inflate every score."""
    from analogatlas import analog

    module = load_script()
    moon = analog.load_index("moon")
    neigh = module._neighbours(moon, 5)
    assert neigh.shape == (len(moon.meta), 5)
    assert not any(i in row for i, row in enumerate(neigh))


def test_neighbours_are_ordered_best_first(index_dir):
    from analogatlas import analog

    module = load_script()
    moon = analog.load_index("moon")
    sim = 0.6 * (moon.shade @ moon.shade.T) + 0.4 * (moon.img @ moon.img.T)
    neigh = module._neighbours(moon, 5)
    for i, row in enumerate(neigh):
        scores = sim[i][row]
        assert np.all(np.diff(scores) <= 1e-6)


def test_ranks_are_a_permutation(index_dir):
    module = load_script()
    score = np.array([0.5, -1.0, 2.0, 0.0])
    assert list(module._ranks(score)) == [2, 4, 1, 3]
