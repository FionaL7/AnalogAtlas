"""Crater labels from the Robbins catalog (#16), on craters placed by hand.

The real catalog is 227 MB and gitignored, so every test here builds a CSV with
the columns `load_catalog` reads and puts each crater where its answer is known.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from analogatlas import config as C, craters


def write_catalog(path, rows) -> None:
    """rows: (lat, lon_east_0_360, diam_km). The catalog's own longitude convention."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["LAT_CIRC_IMG", "LON_CIRC_IMG", "DIAM_CIRC_IMG"]).assign(
        CRATER_ID=[f"c{i}" for i in range(len(rows))]).to_csv(path, index=False)


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    """A catalog builder that `load_catalog()` will find."""
    path = tmp_path / "robbins" / "catalog.csv"
    monkeypatch.setattr(craters, "CATALOG", path)

    def build(rows):
        write_catalog(path, rows)
        return craters.load_catalog()
    return build


def moon_meta(points):
    return pd.DataFrame([{"tile_id": f"moon_6_{i}_{i}", "lat": lat, "lon": lon}
                         for i, (lat, lon) in enumerate(points)])


def polar_meta(points):
    return pd.DataFrame([{"tile_id": f"moonsp_{i}_{i}", "x_m": x, "y_m": y,
                          "size_m": C.TILE_KM * 1000} for i, (x, y) in enumerate(points)])


# ---------------------------------------------------------------- loading ----
def test_longitude_becomes_signed(catalog):
    cat = catalog([(0.0, 10.0, 2.0), (0.0, 350.0, 3.0), (0.0, 180.0, 4.0)])
    assert list(cat.lon) == [10.0, -10.0, -180.0]
    assert list(cat.diam_km) == [2.0, 3.0, 4.0]


def test_missing_catalog_says_where_to_put_it(tmp_path, monkeypatch):
    monkeypatch.setattr(craters, "CATALOG", tmp_path / "nope.csv")
    with pytest.raises(FileNotFoundError, match="data/raw/robbins"):
        craters.load_catalog()


# --------------------------------------------------------------- labelling ---
def test_counts_only_craters_whose_centre_is_in_the_chip(catalog):
    half = C.MOON_TILE_DEG / 2
    cat = catalog([
        (0.0, 0.0, 50.0),               # dead centre
        (half * 0.9, 0.5, 7.0),         # inside
        (half * 1.5, 0.0, 99.0),        # too far north: outside the chip
    ])
    labels = craters.per_tile(moon_meta([(0.0, 0.0)]), "moon", cat)
    row = labels.iloc[0]
    assert row.n_ge_1km == 2
    assert row.n_ge_5km == 2
    assert row.n_ge_20km == 1
    assert row.largest_km == 50.0


def test_chip_is_wider_than_the_grid_cell_at_high_latitude(catalog):
    """A chip spans TILE_KM in both directions, so 1/cos(lat) grid cells of
    longitude (#27). At 60 deg that is twice the cell: a crater 2 deg east is
    outside `lon_min..lon_max` but inside the image the model saw."""
    cat = catalog([(60.0, 2.0, 10.0)])
    at_60 = craters.per_tile(moon_meta([(60.0, 0.0)]), "moon", cat).iloc[0]
    at_0 = craters.per_tile(moon_meta([(0.0, 0.0)]), "moon", cat.assign(lat=0.0)).iloc[0]
    assert at_60.n_ge_1km == 1      # inside the widened chip
    assert at_0.n_ge_1km == 0       # same longitude offset, no widening, outside


def test_the_dateline_is_not_a_wall(catalog):
    cat = catalog([(0.0, 180.1, 6.0)])       # i.e. -179.9
    labels = craters.per_tile(moon_meta([(0.0, 179.0)]), "moon", cat)
    assert labels.iloc[0].n_ge_1km == 1


def test_density_is_per_area_not_per_tile(catalog):
    cat = catalog([(0.0, 0.0, 3.0)])
    row = craters.per_tile(moon_meta([(0.0, 0.0)]), "moon", cat).iloc[0]
    assert row.per_1e4km2 == pytest.approx(1e4 / C.TILE_KM ** 2, rel=1e-6)


def test_empty_chip_scores_zero_not_nan(catalog):
    cat = catalog([(40.0, 40.0, 5.0)])
    row = craters.per_tile(moon_meta([(0.0, 0.0)]), "moon", cat).iloc[0]
    assert row.n_ge_1km == 0
    assert row.largest_km == 0.0


def test_labels_keep_the_meta_row_order(catalog):
    cat = catalog([(0.0, 0.0, 3.0), (30.0, 60.0, 9.0)])
    meta = moon_meta([(30.0, 60.0), (0.0, 0.0), (-45.0, 120.0)])
    labels = craters.per_tile(meta, "moon", cat)
    assert list(labels.tile_id) == list(meta.tile_id)
    assert list(labels.n_ge_1km) == [1, 1, 0]


# ------------------------------------------------------------------- polar ---
def test_polar_chips_are_square_in_metres(catalog):
    """The polar grid is metres from the pole, so no cos(lat) anywhere (#26)."""
    cat = catalog([(-89.99, 0.0, 20.0), (-85.0, 0.0, 30.0)])
    row = craters.per_tile(polar_meta([(0.0, 0.0)]), "moon_polar", cat).iloc[0]
    assert row.n_ge_1km == 1            # the pole crater only; -85 is ~150 km out
    assert row.largest_km == 20.0
    assert row.per_1e4km2 == pytest.approx(1e4 / C.TILE_KM ** 2, rel=1e-3)


def test_polar_ignores_craters_on_the_far_side_of_the_moon(catalog):
    cat = catalog([(80.0, 0.0, 40.0)])          # north pole: never in a south chip
    row = craters.per_tile(polar_meta([(0.0, 0.0)]), "moon_polar", cat).iloc[0]
    assert row.n_ge_1km == 0


# ------------------------------------------------------------------ labels ---
def test_density_class_splits_into_thirds():
    labels = pd.DataFrame({"n_ge_1km": list(range(90))})
    cls = craters.density_class(labels)
    assert set(cls) == {0, 1, 2}
    assert cls.value_counts().to_dict() == {0: 30, 1: 30, 2: 30}
    assert cls.iloc[0] == 0 and cls.iloc[-1] == 2


def test_big_crater_is_half_a_chip_wide():
    labels = pd.DataFrame({"largest_km": [craters.BIG_KM - 0.1, craters.BIG_KM, 300.0]})
    assert list(craters.big_crater(labels)) == [False, True, True]
    # the threshold is about half an 85 km chip, not an arbitrary round number
    assert craters.BIG_KM == pytest.approx(C.TILE_KM / 2, rel=0.1)


def test_earth_has_no_lunar_crater_labels(catalog):
    cat = catalog([(0.0, 0.0, 3.0)])
    with pytest.raises(ValueError, match="lunar"):
        craters.per_tile(moon_meta([(0.0, 0.0)]), "earth", cat)


def test_chip_widening_matches_the_tiler(catalog):
    """`craters` and `tiles` must agree on how wide a chip is, or the labels
    describe a different footprint from the image."""
    from analogatlas.tiles import _lon_window_px

    for lat in (0.0, 30.0, 57.65625):
        from_tiler = _lon_window_px(lat) / C.TILE_PX
        from_labels = 1 / math.cos(math.radians(lat))
        assert from_tiler == pytest.approx(from_labels, rel=0.01)
