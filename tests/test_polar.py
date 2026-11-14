"""Geometry for the south polar index (#26) and the chip aspect fix (#27).

The projection checks run against the real LOLA polar DEM when it is on disk
and skip otherwise, because `data/` is gitignored and rebuilt per machine.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from analogatlas import config as C, tiles
from analogatlas.analog import polar_night_days


# ------------------------------------------------------- projection --------
def test_sp_forward_matches_the_products_edge_radius():
    """Trek's Moon/SP 75 deg products are published with a +/-457440 m bbox;
    the projection has to land on that number or every chip is misplaced."""
    _, y = tiles.sp_forward(-75.0, 0.0)
    assert float(y) == pytest.approx(457_440, abs=200)


def test_sp_round_trip():
    lat = np.array([-75.0, -80.0, -85.5, -89.9])
    lon = np.array([0.0, 129.78, -88.34, 31.0])
    back_lat, back_lon = tiles.sp_inverse(*tiles.sp_forward(lat, lon))
    assert back_lat == pytest.approx(lat, abs=1e-9)
    assert ((back_lon - lon + 180) % 360 - 180) == pytest.approx(0, abs=1e-9)


def test_pole_is_the_origin():
    x, y = tiles.sp_forward(-90.0, 0.0)
    assert (float(x), float(y)) == pytest.approx((0.0, 0.0), abs=1e-6)


# ------------------------------------------------------------- grid --------
def test_polar_grid_cells_are_square_and_cover_the_artemis_regions():
    from analogatlas.sites import MOON_BASE_REGIONS

    grid = tiles.moon_polar_grid()
    assert len(grid) > 50
    assert np.allclose(grid.size_m.values, C.TILE_KM * 1000)
    assert grid.lat.max() <= C.MOON_POLAR_MAX_LAT + 1.5

    half_diagonal = C.TILE_KM * 1000 * math.sqrt(2) / 2
    for name, (lat, lon) in MOON_BASE_REGIONS.items():
        x, y = tiles.sp_forward(lat, lon)
        d = np.hypot(grid.x_m - float(x), grid.y_m - float(y)).min()
        assert d < half_diagonal, f"{name} falls outside every polar cell"


def test_polar_tile_ids_are_unique():
    grid = tiles.moon_polar_grid()
    assert grid.tile_id.is_unique


def test_the_cell_containing_the_pole_reports_reaching_the_pole():
    """None of its corners are at -90, so a corner-derived bbox would miss it,
    and every longitude runs through it."""
    grid = tiles.moon_polar_grid()
    centre = grid.loc[np.hypot(grid.x_m, grid.y_m).idxmin()]
    assert centre.lat == pytest.approx(-90, abs=1e-6)
    assert centre.lat_min == -90.0
    assert (centre.lon_min, centre.lon_max) == (-180.0, 180.0)
    # ordinary cells keep a real longitude span
    edge = grid.loc[np.hypot(grid.x_m, grid.y_m).idxmax()]
    assert edge.lon_max - edge.lon_min < 360.0


# --------------------------------------------------- chip geometry (#27) ---
@pytest.mark.parametrize("lat", [0.0, 15.0, 30.0, 45.0, -52.0, 58.6])
def test_equirectangular_chips_are_square_in_kilometres(lat):
    """The bug this replaces cropped to cos(lat) of one tile and resized back,
    leaving a ground aspect of cos^2(lat) -- 4x off by 60 deg."""
    keep = tiles._lon_window_px(lat)
    km_per_px = C.TILE_KM * math.cos(math.radians(lat)) / C.TILE_PX
    width_km = keep * km_per_px
    assert width_km == pytest.approx(C.TILE_KM, rel=0.01)


def test_chip_window_widens_towards_the_pole_rather_than_narrowing():
    """Direction-of-correction regression: an E-W stretch is undone by taking
    *more* longitude, not less."""
    assert tiles._lon_window_px(0.0) == C.TILE_PX
    assert tiles._lon_window_px(60.0) == pytest.approx(2 * C.TILE_PX, rel=0.01)
    assert tiles._lon_window_px(45.0) > C.TILE_PX


# ------------------------------------------------------ Earth analogue -----
def test_polar_night_days():
    assert polar_night_days(0.0) == 0.0
    assert polar_night_days(-45.0) == 0.0          # outside the polar circles
    assert polar_night_days(-66.0) == 0.0
    assert polar_night_days(-90.0) == pytest.approx(365.25 / 2, rel=0.01)
    assert 0 < polar_night_days(-77.5) < 365.25 / 2   # McMurdo Dry Valleys
    assert polar_night_days(-85.0) > polar_night_days(-77.5)


# ---------------------------------------------- against the real rasters ---
@pytest.mark.skipif(not C.LOLA_POLAR_DEM.exists(), reason="LOLA polar DEM not downloaded")
def test_known_features_land_where_the_gazetteer_says():
    """Pins the projection sign convention. Shackleton and de Gerlache are deep
    craters; Mons Malapert is a massif. Any flipped axis breaks this."""
    from analogatlas.rasters import PDSPolar

    dem = PDSPolar(C.LOLA_POLAR_DEM)
    dem.offset = 0.0

    def relative_height(lat, lon, box_m=30_000):
        x, y = (float(v) for v in tiles.sp_forward(lat, lon))
        window = dem.window(x - box_m, x + box_m, y - box_m, y + box_m)
        centre = window[window.shape[0] // 2, window.shape[1] // 2]
        return float(centre - np.nanmean(window))

    assert relative_height(-89.67, 129.78) < -1000     # Shackleton
    assert relative_height(-88.48, -88.34) < -300      # de Gerlache
    assert relative_height(-85.98, -1.67) > 1000       # Mons Malapert


@pytest.mark.skipif(not C.AVG_ILLUM.exists(), reason="PGDA illumination rasters not downloaded")
def test_shackleton_rim_is_among_the_best_lit_places_on_the_moon():
    """Independent check on the illumination read: the Shackleton rim is the
    textbook near-continuously-lit site, so it must rank near the top."""
    from analogatlas import rasters

    grid = tiles.moon_polar_grid()
    meta = rasters.moon_polar_physical(grid)
    x, y = (float(v) for v in tiles.sp_forward(-89.67, 129.78))
    i = int(np.argmin(np.hypot(meta.x_m - x, meta.y_m - y)))
    assert meta.illum_max.iloc[i] > 0.8
    assert meta.illum_max.iloc[i] >= meta.illum_max.quantile(0.9)
    # a PSR-heavy tile must never be modelled as warm
    assert (meta.t_max_k <= 200.0).all() and (meta.t_max_k >= meta.t_min_k).all()
