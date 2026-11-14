"""Radar roughness helpers (#17, #18), on small synthetic grids."""
from __future__ import annotations

import numpy as np
import pytest

from analogatlas.radar import box_around, minirf_box, rcm_cpr, summarise


def test_summarise_skips_missing_and_reports_coverage():
    v = np.array([0.2, 0.4, 0.6, np.nan, -np.inf, -1e30, 99.0, 0.8])
    s = summarise(v, "test")
    assert s.cpr_median == pytest.approx(0.5)      # median of 0.2, 0.4, 0.6, 0.8
    assert s.coverage == pytest.approx(4 / 8)
    assert s.n_pixels == 8


def test_summarise_with_no_valid_data_is_none_not_zero():
    s = summarise(np.full(10, -np.inf), "test")
    assert s.cpr_median is None and s.cpr_p90 is None and s.coverage == 0.0


def test_minirf_box_reads_the_right_place():
    """1 px per degree: row 0 is 90N..89N, column 0 is 180W..179W."""
    grid = np.full((180, 360), -np.inf, dtype="<f4")
    # a patch at 10N..12N, 20E..23E with CPR 0.7
    grid[90 - 12:90 - 10, 180 + 20:180 + 23] = 0.7
    s = minirf_box(10, 12, 20, 23, grid=grid)
    assert s.cpr_median == pytest.approx(0.7)
    assert s.coverage == pytest.approx(1.0)
    # one degree away: nothing there
    assert minirf_box(13, 15, 20, 23, grid=grid).cpr_median is None


def test_minirf_box_clips_at_the_map_edge():
    grid = np.full((180, 360), 0.3, dtype="<f4")
    s = minirf_box(-95, -85, 170, 190, grid=grid)
    assert s.cpr_median == pytest.approx(0.3)


def test_box_around_is_wider_in_longitude_near_the_pole():
    lat0 = box_around(0, 0, 30, 30.3)
    lat80 = box_around(80, 0, 30, 30.3)
    assert (lat80[3] - lat80[2]) > (lat0[3] - lat0[2]) * 5


def test_rcm_cpr_smooth_surface_is_low_and_the_convention_is_explicit():
    # a mirror-like surface: almost all echo in the opposite-sense channel
    rr, rl = np.array([0.01]), np.array([1.0])
    assert rcm_cpr(rr, rl, same_sense="RR")[0] == pytest.approx(0.01)
    # same data under the other convention reads as very rough: why the
    # convention is checked on real calm water, not assumed
    assert rcm_cpr(rr, rl, same_sense="RL")[0] == pytest.approx(100.0)


def test_rcm_cpr_bad_pixels_are_nan():
    out = rcm_cpr(np.array([0.0, 1.0, -1.0]), np.array([1.0, 0.0, 1.0]))
    assert np.isnan(out).all()


# ---- rcm_box on a tiny synthetic GeoTIFF scene (needs rasterio; skipped without it)
def _write_scene(d, rr, rl):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin
    # 20 m pixels in UTM 20N, near (54.5N, 63.4W), like the real Labrador scene
    tr = from_origin(590000, 6040000, 20, 20)
    for name, arr in (("scene_RR.tif", rr), ("scene_RL.tif", rl)):
        with rasterio.open(d / name, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                           count=1, dtype="float32", crs="EPSG:32620", transform=tr, nodata=0) as dst:
            dst.write(arr.astype("float32"), 1)
    return tr


def test_rcm_box_reads_known_values_and_handles_outside(tmp_path):
    pytest.importorskip("rasterio")
    from rasterio.warp import transform

    from analogatlas.radar import rcm_box
    n = 400
    rr = np.full((n, n), 0.02); rl = np.full((n, n), 0.10)   # left half: water-like, CPR 0.2
    rr[:, n // 2:] = 0.06                                     # right half: land-like, CPR 0.6
    tr = _write_scene(tmp_path, rr, rl)

    def box_at(col, row, half=40):   # a box of +-half pixels around (col,row), in lat/lon
        xs = [tr.c + (col - half) * 20, tr.c + (col + half) * 20]
        ys = [tr.f - (row + half) * 20, tr.f - (row - half) * 20]
        lons, lats = transform("EPSG:32620", "EPSG:4326", xs, ys)
        return min(lats), max(lats), min(lons), max(lons)

    water = rcm_box(tmp_path, *box_at(100, 200), block=1)
    land = rcm_box(tmp_path, *box_at(300, 200), block=1)
    assert water.cpr_median == pytest.approx(0.2, abs=1e-6)
    assert land.cpr_median == pytest.approx(0.6, abs=1e-6)
    assert water.coverage > 0.9 and land.coverage > 0.9

    outside = rcm_box(tmp_path, 10.0, 10.1, 10.0, 10.1)
    assert outside.cpr_median is None and outside.coverage == 0.0
