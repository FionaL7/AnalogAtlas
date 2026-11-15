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


# --------------------------------------------------------------- Mars ------
def _eq_window(a: np.ndarray, lat_min, lat_max, lon_min, lon_max) -> np.ndarray:
    """Slice a global equirectangular array (row 0 = 90 N, col 0 = 180 W).

    Longitude wraps, so tiles touching the +/-180 seam get a full window
    rather than the clipped one PDSCyl settles for.
    """
    ppd_y, ppd_x = a.shape[0] / 180.0, a.shape[1] / 360.0
    r0 = max(int(math.floor((90 - lat_max) * ppd_y)), 0)
    r1 = min(int(math.ceil((90 - lat_min) * ppd_y)), a.shape[0])
    c0 = int(math.floor(((lon_min + 180) % 360) * ppd_x))
    w = max(int(math.ceil((lon_max - lon_min) * ppd_x)), 1)
    return a[r0:r1][:, np.arange(c0, c0 + w) % a.shape[1]]


def fetch_tes_ti() -> None:
    """Assemble the numeric Putzig 2007 nightside TI map (20 ppd, int16,
    J m-2 K-1 s-1/2) from the JMARS WMS, which rejects one whole-globe
    request as CanvasTooBig. The downloadable NBmap2007.tif is only a
    coloured rendering, so the WMS is the actual data source."""
    if C.TES_TI.exists():
        return
    import requests
    out = np.zeros((3600, 7200), "<i2")
    for i, lon0 in enumerate(range(0, 360, 90)):
        for j, lat_top in enumerate((90, 0)):
            # the ASU server never URL-decodes, so FORMAT=image%2Fvicar fails:
            # the query has to go up verbatim. It also streams with no
            # Content-Length, so a dropped connection looks like success --
            # check the byte count ourselves and retry.
            url = (f"{C.TES_TI_WMS}?SERVICE=WMS&REQUEST=GetMap&FORMAT=image/vicar"
                   f"&WIDTH=1800&HEIGHT=1800&SRS=JMARS:4&STYLES=&VERSION=1.1.1"
                   f"&BBOX={lon0},{lat_top - 90},{lon0 + 90},{lat_top}"
                   f"&LAYERS=tes_nightside_ti_putzig_2007")
            for attempt in range(4):
                r = requests.get(url, timeout=300)
                r.raise_for_status()
                m = re.match(rb"LBLSIZE=(\d+)", r.content)
                if m and len(r.content) == int(m.group(1)) + 1800 * 1800 * 2:
                    break
            else:
                raise RuntimeError(f"WMS kept truncating: {r.content[:120]!r}")
            chunk = np.frombuffer(r.content[int(m.group(1)):], "<i2")
            out[j * 1800:(j + 1) * 1800, i * 1800:(i + 1) * 1800] = chunk.reshape(1800, 1800)
    np.save(C.TES_TI, np.roll(out, 3600, axis=1))   # lon 0..360 -> -180..180


def _decode_dust(path: Path) -> np.ndarray:
    """Relative dust cover from the TES dust PNG, decoded by hue.

    The published raster is a colour rendering (blue = dust-free, red =
    dust-covered) over a grey hillshade. Grey (unsaturated) pixels carry no
    data. The result is a RELATIVE 0..1 index, 1 = dustiest; the DCI values
    themselves are not recoverable from the image.
    """
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB"), np.float32) / 255
    mx, mn = a.max(-1), a.min(-1)
    spread = mx - mn
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    s = np.where(spread == 0, 1, spread)
    hue = np.select(                                  # 0 = red, 2/3 = blue
        [mx == r, mx == g], [((g - b) / s) % 6, (b - r) / s + 2], (r - g) / s + 4) / 6
    sat = spread / np.where(mx == 0, 1, mx)
    return np.where(sat < 0.25, np.nan, 1 - np.clip(hue / (2 / 3), 0, 1))


def _grs_weh(path: Path) -> np.ndarray:
    """GRS water-equivalent hydrogen into a 36 x 72 global array, wt%."""
    t = pd.read_csv(path, sep=r"\s+", header=None, usecols=[0, 1, 2],
                    names=["lat", "lon_e", "wt"])
    t.loc[t.wt > 9000, "wt"] = np.nan
    a = np.full((36, 72), np.nan, np.float32)
    rows = ((87.5 - t.lat) / 5).round().astype(int)
    cols = (((t.lon_e + 180) % 360 - 2.5) / 5).round().astype(int)
    a[rows, cols] = t.wt
    return a


def _crism_counts(grid: pd.DataFrame) -> np.ndarray | None:
    """Hydrous-mineral detections per tile, if the Trek point dump exists."""
    if not C.CRISM_HYDROUS.exists():
        return None
    import json
    feats = json.loads(C.CRISM_HYDROUS.read_text())["features"]
    pts = [(f["geometry"]["y"], f["geometry"]["x"]) if "geometry" in f
           else (f["lat"], f["lon"]) for f in feats]
    lat = np.array([p[0] for p in pts])
    lon = (np.array([p[1] for p in pts]) + 180) % 360 - 180
    counts = np.zeros(len(grid))
    for i, r in enumerate(grid.itertuples()):
        counts[i] = int(((lat >= r.lat_min) & (lat < r.lat_max)
                         & (lon >= r.lon_min) & (lon < r.lon_max)).sum())
    return counts


# CO2 condenses at ~148 K at Mars surface pressure: nothing radiates below it.
MARS_CO2_FROST_K = 148.0
MARS_SOLAR_WM2 = 589.0


def mars_temperature_model(lat: float, albedo: float, ti: float) -> dict:
    """Surface extremes, modelled as on the Moon but with measured inputs:
    noon from radiative balance with the tile's own albedo (the 6 mbar CO2
    atmosphere moves it only a few K), pre-dawn from thermal inertia -- rock
    (TI ~600) coasts through the night near 200 K at the equator, dust
    (TI ~50) falls towards the CO2 frost point. Consistent with TES/MCS
    climatology; labelled modelled in the report card."""
    c = max(math.cos(math.radians(lat)), 0.0)
    a = albedo if np.isfinite(albedo) else 0.22
    t_max = (MARS_SOLAR_WM2 * (1 - a) * c / 5.670e-8) ** 0.25
    f = math.sqrt(np.clip((ti - 30.0) / 570.0, 0.0, 1.0)) if np.isfinite(ti) else 0.5
    t_min = max(MARS_CO2_FROST_K, (145.0 + 55.0 * f) * c ** 0.25)
    return dict(t_max_k=float(max(t_max, MARS_CO2_FROST_K)), t_min_k=float(t_min))


# MOLA at 463 m is block-averaged x4 to ~1.85 km, the slope baseline every
# body shares (LOLA LDEM_16 1.9 km, Copernicus DEM resampled to 1.85 km).
MOLA_SLOPE_BLOCK = 4


def mars_physical(grid: pd.DataFrame) -> pd.DataFrame:
    """Terrain from MOLA plus the Mars-only surface dimensions per tile."""
    import rasterio

    fetch_tes_ti()
    ti = np.load(C.TES_TI).astype(np.float32)
    ti[ti <= 0] = np.nan
    with rasterio.open(C.TES_ALBEDO) as ds:
        alb = ds.read(1).astype(np.float32)
        alb[alb == ds.nodata] = np.nan
    dust = _decode_dust(C.TES_DUST)
    weh = _grs_weh(C.GRS_H2O)
    hydrous = _crism_counts(grid)

    dem = rasterio.open(C.MOLA_DEM)
    ppd = dem.width / 360.0
    m_per_deg = C.MARS_KM_PER_DEG * 1000

    def dem_window(r) -> np.ndarray:
        r0 = max(int(math.floor((90 - r.lat_max) * ppd)), 0)
        r1 = min(int(math.ceil((90 - r.lat_min) * ppd)), dem.height)
        c0 = int(math.floor(((r.lon_min + 180) % 360) * ppd))
        w = int(math.ceil((r.lon_max - r.lon_min) * ppd))
        if c0 + w <= dem.width:
            a = dem.read(1, window=((r0, r1), (c0, c0 + w)))
        else:                                        # tile crosses the 180 seam
            a = np.concatenate([dem.read(1, window=((r0, r1), (c0, dem.width))),
                                dem.read(1, window=((r0, r1), (0, c0 + w - dem.width)))], 1)
        a = a.astype(np.float32)
        if dem.nodata is not None:
            a[a == dem.nodata] = np.nan
        return a

    out = []
    for r in tqdm(grid.itertuples(), total=len(grid), desc="mars physical"):
        box = (r.lat_min, r.lat_max, r.lon_min, r.lon_max)
        d = terrain_stats(_block_mean(dem_window(r), MOLA_SLOPE_BLOCK), r.lat,
                          m_per_deg, ppd / MOLA_SLOPE_BLOCK)
        with np.errstate(all="ignore"):
            d["thermal_inertia"] = float(np.nanmean(_eq_window(ti, *box)))
            d["albedo"] = float(np.nanmean(_eq_window(alb, *box)))
            d["dust_index"] = float(np.nanmean(_eq_window(dust, *box)))
            d["weh_pct"] = float(np.nanmean(_eq_window(weh, *box)))
        d["hydrous_count"] = np.nan if hydrous is None else hydrous[r.Index]
        d.update(mars_temperature_model(r.lat, d["albedo"], d["thermal_inertia"]))
        out.append(d)
    dem.close()
    return pd.concat([grid.reset_index(drop=True), pd.DataFrame(out)], axis=1)


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
