"""The Mars tile grid (#37): Trek zoom-7, same matrix as the Moon's zoom-6."""
from __future__ import annotations

import math

import pytest

from analogatlas import config as C, tiles

# Centres from docs/MARS-PLAN.md's target sites.
GALE = (-5.4, 137.8)
JEZERO = (18.44, 77.45)


@pytest.fixture(scope="module")
def grid():
    return tiles.mars_grid()


def test_grid_size_and_ids(grid):
    """~21,800 tiles inside +/-60 deg, ids mars_7_{y}_{x}, no duplicates."""
    assert 21_000 < len(grid) < 22_500
    assert grid.tile_id.is_unique
    first = grid.iloc[0]
    assert first.tile_id == f"mars_{first.z}_{first.y}_{first.x}"
    assert (grid.body == "mars").all()
    assert (grid.z == C.MARS_ZOOM).all()


def test_grid_stays_inside_the_latitude_band(grid):
    assert grid.lat.abs().max() <= C.MARS_MAX_ABS_LAT
    # the band is used fully: the outermost row centre is within one tile of it
    assert grid.lat.abs().max() > C.MARS_MAX_ABS_LAT - C.MARS_TILE_DEG


def test_tiles_are_on_the_trek_matrix(grid):
    """Each centre must sit exactly on the zoom-7 tile matrix, or every
    downloaded chip is offset from its metadata."""
    row = grid.iloc[len(grid) // 2]
    assert row.lat == pytest.approx(90 - (row.y + 0.5) * C.MARS_TILE_DEG)
    assert row.lon == pytest.approx(-180 + (row.x + 0.5) * C.MARS_TILE_DEG)
    assert row.lat_max - row.lat_min == pytest.approx(C.MARS_TILE_DEG)
    assert grid.x.max() == 2 ** (C.MARS_ZOOM + 1) - 1
    assert grid.x.min() == 0


@pytest.mark.parametrize("name,lat,lon", [("Gale", *GALE), ("Jezero", *JEZERO)])
def test_target_sites_fall_inside_a_tile(grid, name, lat, lon):
    hit = grid[(grid.lat_min <= lat) & (lat < grid.lat_max)
               & (grid.lon_min <= lon) & (lon < grid.lon_max)]
    assert len(hit) == 1, f"{name} must land in exactly one tile"


def test_mars_tiles_match_the_moon_and_earth_ground_scale():
    """The whole design: one zoom level down on a body ~2x the radius keeps
    the tile at ~83 km, within a few percent of the Moon/Earth ~85 km."""
    assert C.MARS_TILE_KM == pytest.approx(C.TILE_KM, rel=0.05)


def test_mars_chips_use_the_27_square_crop():
    """The #27 aspect fix is latitude-only, so it transfers to Mars as is."""
    keep = tiles._lon_window_px(55.0)
    width_km = keep * C.MARS_TILE_KM * math.cos(math.radians(55.0)) / C.TILE_PX
    assert width_km == pytest.approx(C.MARS_TILE_KM, rel=0.01)
