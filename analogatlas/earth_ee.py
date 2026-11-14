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
