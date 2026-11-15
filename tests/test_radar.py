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


# ---- Sentinel-1 indicator and the close-study helpers (#19)
def test_s1_ratio_is_vh_over_vv_and_masks_nodata():
    from analogatlas.radar import s1_ratio
    out = s1_ratio(np.array([1.0, 0.0, -32768.0, 0.5]), np.array([0.2, 0.1, 0.1, 0.05]))
    assert out[0] == pytest.approx(0.2) and out[3] == pytest.approx(0.1)
    assert np.isnan(out[1]) and np.isnan(out[2])


def test_summarise_records_which_measure_it_is():
    s = summarise(np.array([0.1, 0.2]), "s1", measure="s1_vh_vv")
    assert s.as_dict()["measure"] == "s1_vh_vv"
    assert summarise(np.array([0.5]), "minirf").as_dict()["measure"] == "cpr"


def test_combine_scenes_takes_the_median_of_scene_medians_and_skips_empty():
    from analogatlas.radar import RoughnessStat, combine_scenes
    stats = [RoughnessStat(0.1, 0.2, 1.0, 10, "x"), RoughnessStat(0.3, 0.5, 0.8, 10, "x"),
             RoughnessStat(0.2, 0.4, 0.9, 10, "x"), RoughnessStat(None, None, 0.0, 10, "x")]
    c = combine_scenes(stats, "src", "cpr")
    assert c.cpr_median == pytest.approx(0.2) and c.cpr_p90 == pytest.approx(0.4)
    assert "3 dates" in c.source
    assert combine_scenes([], "src", "cpr").cpr_median is None


def test_slope_deg_on_a_known_ramp():
    from analogatlas.closestudy import slope_deg
    z = np.tile(np.arange(5) * 30.0, (5, 1))          # rises 30 m per 30 m pixel: 45 degrees
    assert np.median(slope_deg(z, 30.0, 30.0)) == pytest.approx(45.0)


def test_contains_and_spread():
    from analogatlas.closestudy import contains, spread
    box = (10.0, 11.0, 20.0, 21.0)                    # lat_min, lat_max, lon_min, lon_max
    assert contains([19.5, 9.5, 21.5, 11.5], box)
    assert not contains([20.5, 9.5, 21.5, 11.5], box)
    assert spread(list(range(10)), 3) == [0, 4, 9]
    assert spread([1, 2], 6) == [1, 2]


def test_close_study_pairs_name_real_sites():
    from analogatlas.closestudy import PAIRS
    from analogatlas.sites import MOON_BASE_REGIONS, MOON_SITES
    assert 2 <= len(PAIRS) <= 3
    for p in PAIRS:
        assert p["site"] in {**MOON_BASE_REGIONS, **MOON_SITES}
        assert p["earth_tile_id"].startswith("earth_")
