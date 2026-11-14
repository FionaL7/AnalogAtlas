"""What-to-test rules (C6): suggestions follow from the rows that hold."""
from __future__ import annotations

import pandas as pd

from analogatlas.fieldtest import what_to_test


def row(dimension, match, kind="compare", moon="m", earth="e"):
    return dict(dimension=dimension, moon=moon, earth=earth, match=match, note="", kind=kind)


def titles(result):
    return [t["title"] for t in result["tests"]]


def test_matching_slopes_suggest_rover_tests():
    out = what_to_test([row("Median slope", 0.9), row("Local relief", 0.8)])
    assert "Rover mobility and traverse planning" in titles(out)
    rover = out["tests"][0]
    assert rover["based_on"] == ["Median slope", "Local relief"]
    assert rover["strength"] == 0.8


def test_one_missing_dimension_means_no_suggestion():
    """A rule needs every row it names; half the evidence is not enough."""
    out = what_to_test([row("Median slope", 0.9), row("Local relief", 0.1)])
    assert "Rover mobility and traverse planning" not in titles(out)
    assert any(a["dimension"] == "Local relief" for a in out["avoid"])


def test_earth_limits_and_no_equivalent_rows_are_not_avoid_entries():
    out = what_to_test([row("Gravity", 0.0, kind="earth_limit"),
                        row("Surface rock cover", None, kind="no_equivalent")])
    assert out == {"tests": [], "avoid": []}


def test_polar_caveats_are_reported():
    out = what_to_test([row("Permanent shadow", None, kind="no_equivalent"),
                        row("Longest continuous darkness", 0.5)])
    assert "Surviving long darkness" in titles(out)
    assert any(a["dimension"] == "Permanent shadow" for a in out["avoid"])


def test_accepts_a_dataframe_with_nan():
    df = pd.DataFrame([row("Dryness", 0.95), row("Solar exposure", float("nan"))])
    out = what_to_test(df)
    assert titles(out) == ["Dust handling and dry excavation"]
