"""Mars physical features (#38): raster readers, models, and known geography.

Raster-backed tests run only when the files are in data/raw/ (the same
skip-if-absent pattern as test_polar.py), because data/ is rebuilt per machine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analogatlas import config as C, rasters, tiles


# ------------------------------------------------------------ pure units ---
def test_eq_window_wraps_the_180_seam():
    a = np.arange(360, dtype=float).reshape(1, 360).repeat(180, 0)  # 1 ppd, col=lon index
    w = rasters._eq_window(a, -1, 1, 179, 181)
    assert w.shape[1] >= 2
    assert 359 in w and 0 in w                      # both sides of the seam


def test_eq_window_centre_matches_longitude():
    a = np.arange(360, dtype=float).reshape(1, 360).repeat(180, 0)
    w = rasters._eq_window(a, -1, 1, -6, -4)        # 5 W -> col 175
    assert np.all((w >= 174) & (w <= 176))


def test_grs_table_shape_and_units(tmp_path):
    rows = []
    for lat in np.arange(-87.5, 90, 5):
        for lon_e in np.arange(2.5, 360, 5):
            rows.append(f"{lat:6.1f} {lon_e:6.1f} {3.0 if abs(lat) < 60 else 9999.999:9.3f} 0.3 0.3")
    p = tmp_path / "h2o.tab"
    p.write_text("\n".join(rows))
    a = rasters._grs_weh(p)
    assert a.shape == (36, 72)
    assert np.nanmax(a) == pytest.approx(3.0)       # 9999.999 became NaN
    assert np.isnan(a[0]).all() and np.isnan(a[-1]).all()


def test_dust_decode_orientation(tmp_path):
    from PIL import Image
    # red = dust-covered -> 1, blue = dust-free -> 0, grey hillshade -> NaN
    im = Image.new("RGB", (3, 1))
    im.putpixel((0, 0), (255, 30, 30))
    im.putpixel((1, 0), (30, 30, 255))
    im.putpixel((2, 0), (150, 150, 150))
    p = tmp_path / "dust.png"
    im.save(p)
    d = rasters._decode_dust(p)[0]
    assert d[0] == pytest.approx(1.0, abs=0.05)
    assert d[1] == pytest.approx(0.0, abs=0.05)
    assert np.isnan(d[2])


def test_mars_temperature_model_is_physical():
    hot = rasters.mars_temperature_model(0.0, 0.12, 400.0)
    cold = rasters.mars_temperature_model(-60.0, 0.25, 60.0)
    assert 270 < hot["t_max_k"] < 320                # equatorial noon
    assert hot["t_min_k"] > cold["t_min_k"]          # rock holds the night
    assert cold["t_min_k"] >= rasters.MARS_CO2_FROST_K   # nothing below CO2 frost
    assert all(v["t_max_k"] > v["t_min_k"] for v in (hot, cold))
    # higher albedo must mean a cooler noon
    assert (rasters.mars_temperature_model(0, 0.35, 200)["t_max_k"]
            < rasters.mars_temperature_model(0, 0.10, 200)["t_max_k"])


# ------------------------------------------------- against the real rasters ---
def _tile_for(grid, lat, lon):
    hit = grid[(grid.lat_min <= lat) & (lat < grid.lat_max)
               & (grid.lon_min <= lon) & (lon < grid.lon_max)]
    return hit.iloc[[0]]


@pytest.mark.skipif(not C.MOLA_DEM.exists(), reason="MOLA DEM not downloaded")
@pytest.mark.skipif(not C.TES_TI.exists(), reason="TES TI not assembled")
def test_known_mars_features_read_correctly():
    """Olympus Mons reads high, Hellas reads low, Valles Marineris is rough --
    any projection or sign error in the MOLA reader breaks this."""
    grid = tiles.mars_grid()
    sub = pd.concat([_tile_for(grid, 18.65, -133.8),    # Olympus Mons summit
                     _tile_for(grid, -42.4, 70.5),      # Hellas floor
                     _tile_for(grid, -13.9, -59.2)]).reset_index(drop=True)
    meta = rasters.mars_physical(sub)
    olympus, hellas, vm = meta.iloc[0], meta.iloc[1], meta.iloc[2]
    assert olympus.elev_km > 15
    assert hellas.elev_km < -5
    assert vm.relief_km > 3
    assert vm.relief_km > olympus.relief_km * 0.3
    # Mars-only columns arrive with sane units
    assert 0 < hellas.thermal_inertia < 1500
    assert 0 < olympus.albedo < 1
    assert meta.t_max_k.between(150, 330).all()
