"""Per-tile physical statistics from planetary and Earth rasters.

Moon : LRO LOLA LDEM_16 (topography), LRO Diviner GDR L3 rock abundance and
       regolith-temperature anomaly (PDS Geosciences Node).
Earth: ETOPO 2022 60-arc-second surface elevation.

LOLA LDEM_16 (1.9 km/px) and ETOPO 60s (1.85 km/px) have almost identical
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


# ------------------------------------------------------------- terrain -----
def terrain_stats(elev_m: np.ndarray, lat: float, m_per_deg: float, ppd: float) -> dict:
    """Elevation, relief and slope statistics for one DEM window (metres)."""
    if elev_m.size < 9 or np.isnan(elev_m).mean() > 0.5:
        return dict(elev_km=np.nan, relief_km=np.nan, slope_med=np.nan, slope_p90=np.nan)
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
