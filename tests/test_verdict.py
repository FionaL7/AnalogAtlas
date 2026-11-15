"""Verdict tier rule (#50): the bottom line follows from the compare rows."""
from __future__ import annotations

import math

import pandas as pd

from analogatlas.verdict import verdict


def row(dimension, match, kind="compare"):
    return dict(dimension=dimension, moon="m", earth="e", match=match, note="", kind=kind)


def test_all_holding_is_strong():
    out = verdict([row("Median slope", 0.9), row("Local relief", 0.8), row("Dryness", 0.7)])
    assert out["tier"] == "strong"
    assert out["holds_frac"] == 1.0
    assert out["n_compare"] == 3
    assert out["top_holds"] == ["Median slope", "Local relief"]
    assert out["top_breaks"] == []


def test_tier_bars_are_inclusive():
    # 7 of 10 hold -> exactly 0.7 -> strong; 4 of 10 -> exactly 0.4 -> moderate
    seven = [row(f"d{i}", 0.9) for i in range(7)] + [row(f"b{i}", 0.1) for i in range(3)]
    assert verdict(seven)["tier"] == "strong"
    four = [row(f"d{i}", 0.9) for i in range(4)] + [row(f"b{i}", 0.1) for i in range(6)]
    assert verdict(four)["tier"] == "moderate"


def test_mostly_breaking_is_partial_and_names_the_worst():
    out = verdict([row("Median slope", 0.9), row("Dryness", 0.1),
                   row("Coldest surface", 0.3), row("Solar exposure", 0.5)])
    assert out["tier"] == "partial"
    # worst first, and 0.5 counts as breaking (below the 0.6 holds bar)
    assert out["top_breaks"] == ["Dryness", "Coldest surface"]


def test_only_compare_rows_count():
    out = verdict([row("Median slope", 0.9),
                   row("Gravity", 0.0, kind="earth_limit"),
                   row("Surface rock cover", None, kind="no_equivalent"),
                   row("Terrain shape (ML)", math.nan)])
    assert out["n_compare"] == 1
    assert out["tier"] == "strong"


def test_no_comparable_rows_is_no_verdict():
    assert verdict([row("Gravity", 0.0, kind="earth_limit")]) is None
    assert verdict([]) is None


def test_sentence_names_dimensions_and_best_field_test():
    tests = dict(tests=[dict(title="Rover mobility and traverse planning")], avoid=[])
    out = verdict([row("Median slope", 0.9), row("Dryness", 0.2)], tests)
    assert "1 of 2 comparable dimensions hold" in out["sentence"]
    assert "led by Median slope" in out["sentence"]
    assert "Dryness breaks down" in out["sentence"]
    assert "rover mobility and traverse planning" in out["sentence"]


def test_accepts_a_dataframe():
    rows = pd.DataFrame([row("Median slope", 0.9), row("Local relief", 0.8)])
    assert verdict(rows)["tier"] == "strong"
