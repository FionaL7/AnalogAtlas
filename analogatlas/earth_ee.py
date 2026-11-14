"""Earth tiles and terrain statistics from Google Earth Engine.

Uses the Copernicus DEM (GLO-30) for both:
  * physical(grid): elev_km, relief_km, slope_med, slope_p90 per tile, measured
    on the DEM resampled to ~1.85 km (same baseline as LOLA LDEM_16);
  * shade_tile(row): a 256x256 hillshade of the tile, the Earth counterpart of
    the LOLA hillshade tiles used on the Moon.

Needs `earthengine authenticate` once per machine and C.EE_PROJECT.
"""
from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import pandas as pd
import requests
from PIL import Image
from tqdm import tqdm

from . import config as C


@lru_cache(maxsize=1)
def init():
    import ee
    ee.Initialize(project=C.EE_PROJECT)
    return ee


def _dem():
    ee = init()
    return (ee.ImageCollection(C.EE_DEM).select("DEM").mosaic()
            .setDefaultProjection("EPSG:4326", None, 30))


def _rect(row):
    ee = init()
    return ee.Geometry.Rectangle([row.lon_min, row.lat_min, row.lon_max, row.lat_max], None, False)


@lru_cache(maxsize=1)
def _shade_image():
    ee = init()
    dem = _dem().multiply(C.EARTH_SHADE_ZFACTOR).reproject("EPSG:4326", None, C.EARTH_SHADE_SCALE_M)
    return ee.Terrain.hillshade(dem, C.SUN_AZIMUTH, C.SUN_ELEVATION)


def shade_tile(row, session: requests.Session | None = None) -> Image.Image:
    """256x256 greyscale hillshade. The box is square in km, so forcing a
    square image gives equal ground scale in both directions."""
    url = _shade_image().getThumbURL({
        "region": _rect(row), "dimensions": f"{C.TILE_PX}x{C.TILE_PX}",
        "format": "png", "min": 0, "max": 255})
    r = (session or requests).get(url, timeout=120)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("L")


def physical(grid: pd.DataFrame, batch: int = 250, workers: int = 4) -> pd.DataFrame:
    """Per-tile terrain statistics, same columns as rasters.terrain_stats."""
    ee = init()
    dem = _dem().reproject("EPSG:4326", None, C.EARTH_SLOPE_SCALE_M)
    img = dem.rename("elev").addBands(ee.Terrain.slope(dem).rename("slope"))
    red = ee.Reducer.mean().combine(ee.Reducer.percentile([2, 50, 90, 98]), sharedInputs=True)

    def run(chunk: pd.DataFrame) -> list[dict]:
        fc = ee.FeatureCollection([ee.Feature(_rect(r), {"tile_id": r.tile_id}) for r in chunk.itertuples()])
        feats = img.reduceRegions(fc, red, scale=C.EARTH_SLOPE_SCALE_M).getInfo()["features"]
        out = []
        for f in feats:
            p = {k: (np.nan if v is None else v) for k, v in f["properties"].items()}
            out.append(dict(
                tile_id=p["tile_id"],
                elev_km=p.get("elev_mean", np.nan) / 1000,
                relief_km=(p.get("elev_p98", np.nan) - p.get("elev_p2", np.nan)) / 1000,
                slope_med=p.get("slope_p50", np.nan),
                slope_p90=p.get("slope_p90", np.nan)))
        return out

    chunks = [grid.iloc[i:i + batch] for i in range(0, len(grid), batch)]
    rows = []
    with ThreadPoolExecutor(workers) as ex:
        for res in tqdm(ex.map(run, chunks), total=len(chunks), desc="earth physical (EE)"):
            rows.extend(res)
    stats = pd.DataFrame(rows).set_index("tile_id")
    return pd.concat([grid.reset_index(drop=True),
                      stats.loc[grid.tile_id].reset_index(drop=True)], axis=1)


# ------------------------------------------------------------ environment --
ENV_SCALE_M = 5000           # environment layers are ~1 km; 5 km is plenty per 85 km tile
ENV_YEARS = ("2015-01-01", "2025-01-01")

# MODIS MCD12Q1 IGBP classes (LC_Type1) grouped into what matters for analogs.
LAND_CLASSES = {
    "ice_frac": [15],                        # permanent snow and ice
    "barren_frac": [16],                     # barren / sparse
    "veg_frac": [1, 2, 3, 4, 5, 6, 8, 9, 12, 14],  # forest, closed shrub, savannas, crops
    "sparse_frac": [7, 10],                  # open shrubland, grassland: desert scrub counts here
    "water_frac": [11, 17],                  # wetland, water
    "urban_frac": [13],
}


@lru_cache(maxsize=1)
def _env_image():
    """One multi-band image of per-pixel environment variables."""
    ee = init()
    t0, t1 = ENV_YEARS
    lst = ee.ImageCollection("MODIS/061/MOD11A2").filterDate(t0, t1)
    k2c = lambda im: im.multiply(0.02).subtract(273.15)           # noqa: E731
    day = k2c(lst.select("LST_Day_1km").mean()).rename("lst_day_c")
    night = k2c(lst.select("LST_Night_1km").mean()).rename("lst_night_c")
    cold = k2c(lst.select("LST_Night_1km").reduce(ee.Reducer.percentile([5]))).rename("lst_cold_c")
    hot = k2c(lst.select("LST_Day_1km").reduce(ee.Reducer.percentile([95]))).rename("lst_hot_c")

    tc = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterDate(t0, t1)
    pr = tc.select("pr").mean().multiply(12).rename("precip_mm")             # mm / year
    pet = tc.select("pet").mean().multiply(0.1 * 12).rename("pet_mm")        # mm / year
    srad = tc.select("srad").mean().multiply(0.1).rename("solar_wm2")        # W / m2

    ndvi = (ee.ImageCollection("MODIS/061/MOD13A2").filterDate(t0, t1)
            .select("NDVI").mean().multiply(0.0001).rename("ndvi"))

    lc = (ee.ImageCollection("MODIS/061/MCD12Q1").filterDate("2023-01-01", "2024-01-01")
          .first().select("LC_Type1"))                                    # newest complete year
    land = [lc.remap(v, [1] * len(v), 0).rename(k) for k, v in LAND_CLASSES.items()]

    access = ee.Image("Oxford/MAP/accessibility_to_cities_2015_v1_0").rename("access_min")
    return ee.Image.cat(day, night, cold, hot, pr, pet, srad, ndvi, *land, access)


def environment(grid: pd.DataFrame, batch: int = 150, workers: int = 4) -> pd.DataFrame:
    """Per-tile environment columns (means over the tile, except access: 10th pct).

    lst_*_c      MODIS land-surface temperature 2015-24, deg C (day/night mean,
                 hottest day p95, coldest night p5); lst_swing_c = day - night
    precip_mm    TerraClimate annual precipitation; aridity = precip / PET
    solar_wm2    TerraClimate mean downward shortwave
    ndvi         MODIS NDVI mean
    *_frac       MODIS MCD12Q1 land-cover fractions (ice, barren, sparse veg,
                 dense veg, water, urban)
    access_min   travel time to nearest city (Oxford/MAP 2015), 10th percentile
                 in the tile = the most reachable part; NaN = no data
                 (mostly Antarctica, i.e. very remote)
    """
    ee = init()
    img = _env_image()
    red = ee.Reducer.mean().combine(ee.Reducer.percentile([10]), sharedInputs=True)

    def run(chunk: pd.DataFrame) -> list[dict]:
        fc = ee.FeatureCollection([ee.Feature(_rect(r), {"tile_id": r.tile_id}) for r in chunk.itertuples()])
        feats = img.reduceRegions(fc, red, scale=ENV_SCALE_M, tileScale=4).getInfo()["features"]
        out = []
        for f in feats:
            p = {k: (np.nan if v is None else v) for k, v in f["properties"].items()}
            row = {"tile_id": p["tile_id"]}
            for band in ["lst_day_c", "lst_night_c", "lst_cold_c", "lst_hot_c", "precip_mm",
                         "pet_mm", "solar_wm2", "ndvi", *LAND_CLASSES]:  # noqa: E501
                row[band] = p.get(f"{band}_mean", np.nan)
            row["access_min"] = p.get("access_min_p10", np.nan)
            out.append(row)
        return out

    chunks = [grid.iloc[i:i + batch] for i in range(0, len(grid), batch)]
    rows = []
    with ThreadPoolExecutor(workers) as ex:
        for res in tqdm(ex.map(run, chunks), total=len(chunks), desc="earth environment (EE)"):
            rows.extend(res)
    env = pd.DataFrame(rows).set_index("tile_id").loc[grid.tile_id].reset_index(drop=True)
    env["lst_swing_c"] = env.lst_day_c - env.lst_night_c
    # precip / PET; capped, because PET -> 0 on ice sheets (TerraClimate is
    # unreliable in Antarctica anyway, where ice_frac says what matters)
    env["aridity"] = (env.precip_mm / env.pet_mm.where(env.pet_mm > 0)).clip(upper=10)
    return env.drop(columns="pet_mm")
