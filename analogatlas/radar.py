"""Radar roughness (CPR) on both bodies: the close-study measurement (#17, #18, #19).

CPR, the circular polarization ratio, is one number per pixel:
    CPR = same-sense echo / opposite-sense echo
A radar sends a circularly polarised ("twisting") wave. A smooth surface acts
like a mirror and flips the twist, so the echo is mostly opposite-sense: CPR
near 0. Rough, blocky ground at the wavelength scale scrambles it: CPR toward
1 or above. It measures roughness at roughly the wavelength scale (cm to m),
which is the scale a lander footpad or rover wheel meets.

Moon: LRO Mini-RF global mosaic, S-band (12.6 cm), CPR precomputed by the
  team (PDS MOSDDR, 32 px/deg = ~0.95 km/px, simple cylindrical).
Earth: RADARSAT Constellation Mission CEOS-ARD, C-band (5.6 cm), compact-pol,
  30 m. CPR is computed here from the RR and RL intensity images.

The two wavelengths differ (12.6 vs 5.6 cm), so they sense roughness at
slightly different scales. Report cards must say so.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config as C

# ---- Mini-RF global CPR mosaic (Moon) --------------------------------------
MINIRF_DIR = C.RAW / "minirf"
MINIRF_CPR = MINIRF_DIR / "global_cpr_32ppd_simp_0c.img"
MINIRF_PPD = 32
MINIRF_SHAPE = (180 * MINIRF_PPD, 360 * MINIRF_PPD)   # (5760, 11520), from the .lbl
# Plausible CPR range. The label's missing value (-1.8e308) can't be stored in
# float32, so missing cells arrive as -inf or huge negatives; anything outside
# this range is treated as no data.
CPR_VALID = (0.0, 10.0)


@dataclass
class RoughnessStat:
    """Roughness summary for one box: what goes on a report card."""
    cpr_median: float | None
    cpr_p90: float | None
    coverage: float          # fraction of the box with valid radar data, 0-1
    n_pixels: int
    source: str

    def as_dict(self) -> dict:
        return dict(cpr_median=self.cpr_median, cpr_p90=self.cpr_p90,
                    coverage=round(self.coverage, 3), n_pixels=self.n_pixels, source=self.source)


def summarise(values: np.ndarray, source: str) -> RoughnessStat:
    """Median and 90th percentile of the valid CPR values in a box.

    Median, not mean: radar speckle makes single pixels randomly bright or
    dark, and the median ignores those outliers.
    """
    v = np.asarray(values, dtype=np.float64).ravel()
    ok = np.isfinite(v) & (v >= CPR_VALID[0]) & (v <= CPR_VALID[1])
    good = v[ok]
    if good.size == 0:
        return RoughnessStat(None, None, 0.0, int(v.size), source)
    return RoughnessStat(float(np.median(good)), float(np.percentile(good, 90)),
                         float(ok.mean()), int(v.size), source)


def minirf_cpr(path: Path = MINIRF_CPR) -> np.ndarray:
    """The whole-Moon CPR grid, memory-mapped (reads only the parts used).

    Row 0 is 90N, column 0 is 180W; 32 px per degree.
    """
    return np.memmap(path, dtype="<f4", mode="r", shape=MINIRF_SHAPE)


def minirf_box(lat_min: float, lat_max: float, lon_min: float, lon_max: float,
               grid: np.ndarray | None = None) -> RoughnessStat:
    """Mini-RF CPR summary for a lat/lon box on the Moon (lon in -180..180)."""
    g = minirf_cpr() if grid is None else grid
    ppd = g.shape[1] / 360          # 32 for the real mosaic; smaller in tests
    r0 = int(np.floor((90 - lat_max) * ppd))
    r1 = int(np.ceil((90 - lat_min) * ppd))
    c0 = int(np.floor((lon_min + 180) * ppd))
    c1 = int(np.ceil((lon_max + 180) * ppd))
    r0, r1 = max(r0, 0), min(r1, g.shape[0])
    c0, c1 = max(c0, 0), min(c1, g.shape[1])
    return summarise(np.asarray(g[r0:r1, c0:c1]), "LRO Mini-RF S-band (12.6 cm), global mosaic 32 ppd")


def box_around(lat: float, lon: float, half_km: float, km_per_deg: float) -> tuple[float, float, float, float]:
    """A square box of +-half_km around a point, as (lat_min, lat_max, lon_min, lon_max)."""
    dlat = half_km / km_per_deg
    dlon = half_km / (km_per_deg * max(np.cos(np.radians(lat)), 1e-6))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


# ---- RCM compact-pol ARD (Earth) --------------------------------------------
# Verified on real data, not assumed (RCM ARD, Labrador, 2025-09-01): with
# CPR = RR / RL, dark water has median 0.23 and bright land 0.55. The other way
# round gives water 4.39, i.e. "water rougher than rock", which is impossible.
RCM_SAME_SENSE = "RR"
RCM_SOURCE = "RADARSAT Constellation Mission C-band (5.6 cm), compact-pol ARD 30 m"


def rcm_cpr(rr: np.ndarray, rl: np.ndarray, same_sense: str = RCM_SAME_SENSE) -> np.ndarray:
    """Per-pixel CPR from the two circular-receive intensity images.

    The images hold linear power (not dB); 0 means no data. RCM transmits a
    right-circular wave; which receive channel is "same sense" is checked on
    real data above (calm water must come out smooth). Zero or negative
    intensity -> NaN.
    """
    rr = np.asarray(rr, dtype=np.float64)
    rl = np.asarray(rl, dtype=np.float64)
    sc, oc = (rr, rl) if same_sense == "RR" else (rl, rr)
    with np.errstate(divide="ignore", invalid="ignore"):
        cpr = np.where((sc > 0) & (oc > 0), sc / oc, np.nan)
    return cpr


def rcm_box(scene_dir: Path, lat_min: float, lat_max: float, lon_min: float, lon_max: float,
            block: int = 4) -> RoughnessStat:
    """RCM CPR summary for a lat/lon box, read from one ARD scene folder.

    `scene_dir` holds `scene_RR.tif` and `scene_RL.tif`. Only the window that
    covers the box is read. Pixels are averaged in `block` x `block` groups
    (4 -> 80 m) before the ratio, which tames speckle without blurring away
    the wavelength-scale roughness CPR measures.

    Needs rasterio (GDAL). On Windows machines where Application Control blocks
    its DLLs, run this in Docker (see the radar-roughness skill).
    """
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.errors import WindowError
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds

    out = []
    for name in ("scene_RR.tif", "scene_RL.tif"):
        with rasterio.open(Path(scene_dir) / name) as src:
            left, bottom, right, top = transform_bounds("EPSG:4326", src.crs,
                                                        lon_min, lat_min, lon_max, lat_max)
            win = from_bounds(left, bottom, right, top, src.transform).round_offsets().round_lengths()
            try:
                win = win.intersection(Window(0, 0, src.width, src.height))
            except WindowError:
                # the box is outside this scene: no data, not a crash
                return RoughnessStat(None, None, 0.0, 0, RCM_SOURCE)
            h, w = max(int(win.height) // block, 1), max(int(win.width) // block, 1)
            out.append(src.read(1, window=win, out_shape=(h, w),
                                resampling=Resampling.average).astype(np.float64))
    return summarise(rcm_cpr(*out), RCM_SOURCE)
