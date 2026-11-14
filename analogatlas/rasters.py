"""Per-tile physical statistics from planetary and Earth rasters.

Moon : LRO LOLA LDEM_16 (topography), LRO Diviner GDR L3 rock abundance and
       regolith-temperature anomaly (PDS Geosciences Node).
Earth: Copernicus DEM via Earth Engine (earth_ee.physical), resampled to
       1.85 km; ETOPO 2022 60s is the offline fallback.

LOLA LDEM_16 (1.9 km/px) and the 1.85 km Earth DEM have almost identical
sampling, so slope and relief are measured at the same baseline on both bodies.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from . import config as C


# ------------------------------------------------------------ PDS3 IMG -----
class PDSCyl:
    """Memory-mapped PDS3 simple-cylindrical IMG with its .lbl label."""

    def __init__(self, img: Path):
        lbl = Path(str(img).replace(".img", ".lbl")).read_text()

        def num(key):
            return float(re.search(rf"\b{key}\s*=\s*([-\d.]+)", lbl).group(1))

        self.lines, self.samples = int(num("LINES")), int(num("LINE_SAMPLES"))
        self.scale = num("SCALING_FACTOR")
        self.offset = num("OFFSET")
        self.ppd = num("MAP_RESOLUTION")
        self.max_lat = num("MAXIMUM_LATITUDE")
        self.west_lon = num("WESTERNMOST_LONGITUDE")
        m = re.search(r"MISSING_CONSTANT\s*=\s*(-?\d+)", lbl)
        self.missing = int(m.group(1)) if m else None
        self.arr = np.memmap(img, dtype="<i2", mode="r", shape=(self.lines, self.samples))

    def window(self, lat_min, lat_max, lon_min, lon_max) -> np.ndarray:
        r0 = int(math.floor((self.max_lat - lat_max) * self.ppd))
        r1 = int(math.ceil((self.max_lat - lat_min) * self.ppd))
        lo0, lo1 = lon_min % 360, (lon_min % 360) + (lon_max - lon_min)
        c0 = int(math.floor((lo0 - self.west_lon) * self.ppd))
        c1 = int(math.ceil((lo1 - self.west_lon) * self.ppd))
        r0, r1 = max(r0, 0), min(r1, self.lines)
        if r1 <= r0:
            return np.full((1, 1), np.nan, np.float32)
        a = np.asarray(self.arr[r0:r1, max(c0, 0):min(c1, self.samples)]).astype(np.float32)
        if self.missing is not None:
            a[a == self.missing] = np.nan
        return a * self.scale + self.offset


class PDSPolar:
    """Memory-mapped PDS3 south polar stereographic IMG with its .lbl label.

    The LOLA polar DEM and the PGDA illumination/PSR/Earth-visibility rasters
    all share one grid -- centred on -90, x/y in metres from the pole -- so a
    single reader serves them, at whatever pixel scale each one ships at.
    """

    def __init__(self, img: Path):
        lbl = next(p for p in (img.with_suffix(".lbl"), img.with_suffix(".LBL")) if p.exists())
        text = lbl.read_text()

        def num(key):
            return float(re.search(rf"\b{key}\s*=\s*(-?[\d.]+)", text).group(1))

        self.lines, self.samples = int(num("LINES")), int(num("LINE_SAMPLES"))
        self.scale = num("SCALING_FACTOR")
        self.offset = num("OFFSET")
        self.map_scale = num("MAP_SCALE")                   # metres per pixel
        self.line_off = num("LINE_PROJECTION_OFFSET")
        self.sample_off = num("SAMPLE_PROJECTION_OFFSET")
        m = re.search(r"MISSING_CONSTANT\s*=\s*(-?\d+)", text)
        self.missing = int(m.group(1)) if m else None
        self.arr = np.memmap(img, dtype="<i2", mode="r", shape=(self.lines, self.samples))

    def window(self, x_min, x_max, y_min, y_max) -> np.ndarray:
        """Values over an (x, y) box in metres. y is north-up, lines are not."""
        s0 = int(math.floor(self.sample_off + x_min / self.map_scale))
        s1 = int(math.ceil(self.sample_off + x_max / self.map_scale))
        l0 = int(math.floor(self.line_off - y_max / self.map_scale))
        l1 = int(math.ceil(self.line_off - y_min / self.map_scale))
        s0, s1 = max(s0, 0), min(s1, self.samples)
        l0, l1 = max(l0, 0), min(l1, self.lines)
        if s1 <= s0 or l1 <= l0:
            return np.full((1, 1), np.nan, np.float32)
        a = np.asarray(self.arr[l0:l1, s0:s1]).astype(np.float32)
        if self.missing is not None:
            a[a == self.missing] = np.nan
        return a * self.scale + self.offset


# ------------------------------------------------------------- terrain -----
def terrain_stats(elev_m: np.ndarray, lat: float, m_per_deg: float, ppd: float,
                  spacing_m: float | None = None) -> dict:
    """Elevation, relief and slope statistics for one DEM window (metres).

    `spacing_m` overrides the equirectangular spacing for grids that are
    already isotropic in metres -- the polar stereographic products. Keeping
    one implementation is what makes slope comparable across bodies.
    """
    if elev_m.size < 9 or np.isnan(elev_m).mean() > 0.5:
        return dict(elev_km=np.nan, relief_km=np.nan, slope_med=np.nan, slope_p90=np.nan)
    if spacing_m is not None:
        dy = dx = spacing_m
    else:
        dy = m_per_deg / ppd
        dx = dy * max(math.cos(math.radians(lat)), 0.05)
    gy, gx = np.gradient(elev_m, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    return dict(
        elev_km=float(np.nanmean(elev_m) / 1000),
        relief_km=float((np.nanpercentile(elev_m, 98) - np.nanpercentile(elev_m, 2)) / 1000),
        slope_med=float(np.nanmedian(slope)),
        slope_p90=float(np.nanpercentile(slope, 90)),
    )


def moon_physical(grid: pd.DataFrame) -> pd.DataFrame:
    dem = PDSCyl(C.LOLA_DEM)
    dem.offset = 0.0     # keep height relative to the 1737.4 km reference sphere
    rock, night = PDSCyl(C.DIVINER_ROCK), PDSCyl(C.DIVINER_NIGHT_T)
    m_per_deg = C.MOON_KM_PER_DEG * 1000
    out = []
    for r in tqdm(grid.itertuples(), total=len(grid), desc="moon physical"):
        box = (r.lat_min, r.lat_max, r.lon_min, r.lon_max)
        d = terrain_stats(dem.window(*box), r.lat, m_per_deg, dem.ppd)
        with np.errstate(all="ignore"):
            d["rock_abundance"] = float(np.nanmean(rock.window(*box)))
            d["regolith_t_anom"] = float(np.nanmean(night.window(*box)))
        d.update(lunar_temperature_model(r.lat))
        out.append(d)
    return pd.concat([grid.reset_index(drop=True), pd.DataFrame(out)], axis=1)


# 8 x 240 m. LOLA LDEM_16 is 1.9 km/px and the Earth DEM is resampled to
# 1.85 km, so measuring the pole at 1.92 km keeps slope comparable everywhere.
POLAR_SLOPE_BASELINE_M = 1920.0


def _block_mean(a: np.ndarray, k: int) -> np.ndarray:
    """Average k x k blocks, dropping any ragged edge."""
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    if k < 2 or h < k or w < k:
        return a
    return np.nanmean(a[:h, :w].reshape(h // k, k, w // k, k), axis=(1, 3))


def moon_polar_physical(grid: pd.DataFrame) -> pd.DataFrame:
    """Terrain, illumination, permanent shadow and Earth visibility per tile.

    The last three are what a base actually cares about and have no equivalent
    in the equatorial index, where Diviner's cylindrical products stop at 60.
    """
    dem = PDSPolar(C.LOLA_POLAR_DEM)
    dem.offset = 0.0     # keep height relative to the 1737.4 km reference sphere
    psr, illum, evis = (PDSPolar(p) for p in (C.LPSR, C.AVG_ILLUM, C.EARTH_VIS))
    block = max(int(round(POLAR_SLOPE_BASELINE_M / dem.map_scale)), 1)
    out = []
    for r in tqdm(grid.itertuples(), total=len(grid), desc="moon_polar physical"):
        half = r.size_m / 2
        box = (r.x_m - half, r.x_m + half, r.y_m - half, r.y_m + half)
        with np.errstate(all="ignore"):
            d = terrain_stats(_block_mean(dem.window(*box), block), r.lat, 0.0, 0.0,
                              spacing_m=block * dem.map_scale)
            lit = illum.window(*box)
            d["psr_frac"] = float(np.nanmean(psr.window(*box) > 0.5))
            d["avg_illum"] = float(np.nanmean(lit))
            # the siting number: a base wants the best-lit ridge in the tile,
            # not the tile average, which 85 km of terrain dilutes away
            d["illum_max"] = float(np.nanmax(lit))
            d["earth_vis"] = float(np.nanmean(evis.window(*box)))
        d.update(polar_temperature_model(d["psr_frac"]))
        out.append(d)
    return pd.concat([grid.reset_index(drop=True), pd.DataFrame(out)], axis=1)


# Diviner south polar observations (Paige et al. 2010, Science 330): cold traps
# stay below ~40 K year round, while sunlit polar ground peaks near ~200 K.
PSR_T_MAX_K, PSR_T_MIN_K = 40.0, 30.0
LIT_POLE_T_MAX_K, LIT_POLE_T_MIN_K = 200.0, 50.0


def polar_temperature_model(psr_frac: float) -> dict:
    """Surface extremes near the pole, weighted by how much of the tile is shadowed.

    The `lunar_temperature_model` latitude fit must NOT be used here: it goes
    to 0 K at the pole, because a noon-sun fit is meaningless where the Sun
    never rises more than ~1.5 deg. These two endpoints are Diviner
    measurements instead. Still a model, and labelled that way in the UI.
    """
    f = 0.0 if not np.isfinite(psr_frac) else float(np.clip(psr_frac, 0.0, 1.0))
    return dict(t_max_k=(1 - f) * LIT_POLE_T_MAX_K + f * PSR_T_MAX_K,
                t_min_k=(1 - f) * LIT_POLE_T_MIN_K + f * PSR_T_MIN_K)


def lunar_temperature_model(lat: float) -> dict:
    """Surface temperature extremes vs latitude, a simple fit consistent with
    Diviner equatorial observations (~390 K noon, ~95 K pre-dawn;
    Williams et al. 2017, Icarus 283). Used because the Diviner GDR L3 temperature
    product in the archive is an anomaly map, not absolute temperatures."""
    c = max(math.cos(math.radians(lat)), 0.0)
    t_max = 392.0 * c ** 0.25
    t_min = 95.0 * c ** 0.25 if c > 0.1 else 50.0
    return dict(t_max_k=t_max, t_min_k=t_min)


def earth_physical(grid: pd.DataFrame) -> pd.DataFrame:
    if C.EE_PROJECT:
        from . import earth_ee
        return earth_ee.physical(grid)
    return earth_physical_etopo(grid)


def earth_physical_etopo(grid: pd.DataFrame) -> pd.DataFrame:
    """Offline fallback: needs C.ETOPO in data/raw/."""
    import xarray as xr
    ds = xr.open_dataset(C.ETOPO)
    z = ds["z"]
    lat_name = "lat" if "lat" in z.dims else "y"
    lon_name = "lon" if "lon" in z.dims else "x"
    lat_desc = float(z[lat_name][0]) > float(z[lat_name][-1])
    m_per_deg = C.EARTH_KM_PER_DEG * 1000
    out = []
    for r in tqdm(grid.itertuples(), total=len(grid), desc="earth physical"):
        lat_sl = slice(r.lat_max, r.lat_min) if lat_desc else slice(r.lat_min, r.lat_max)
        lon_min, lon_max = max(r.lon_min, -180), min(r.lon_max, 180)
        a = z.sel({lat_name: lat_sl, lon_name: slice(lon_min, lon_max)}).values.astype(np.float32)
        out.append(terrain_stats(a, r.lat, m_per_deg, 60.0))
    return pd.concat([grid.reset_index(drop=True), pd.DataFrame(out)], axis=1)
