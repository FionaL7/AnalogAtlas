"""Paths, constants and data-source endpoints shared by every script."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"            # downloaded rasters (LOLA, Diviner, ETOPO)
TILES = DATA / "tiles"        # downloaded image tiles, one folder per body/layer
INDEX = DATA / "index"        # parquet metadata + embedding matrices

# ---- Body constants -------------------------------------------------------
MOON_RADIUS_M = 1_737_400.0
EARTH_RADIUS_M = 6_371_000.0
MOON_KM_PER_DEG = 2 * 3.141592653589793 * MOON_RADIUS_M / 1000 / 360    # ~30.3
EARTH_KM_PER_DEG = 2 * 3.141592653589793 * EARTH_RADIUS_M / 1000 / 360  # ~111.2

# ---- Tiling ----------------------------------------------------------------
# Moon tiles are NASA Trek WMTS zoom-6 tiles: 2.8125 deg ~= 85 km per side.
MOON_ZOOM = 6
MOON_TILE_DEG = 180.0 / 2 ** MOON_ZOOM                 # 2.8125
TILE_KM = MOON_TILE_DEG * MOON_KM_PER_DEG              # ~85 km
MOON_MAX_ABS_LAT = 60.0     # Diviner GDR L3 cylindrical products cover +/-60
# Earth tiles are requested from GIBS WMS with the same ground size (~85 km).
EARTH_TILE_DEG_LAT = TILE_KM / EARTH_KM_PER_DEG        # ~0.77 deg
EARTH_GRID_STEP_DEG = 1.0
EARTH_MAX_ABS_LAT = 82.0    # ASTER GDEM coverage limit is ~83 deg
TILE_PX = 256

# ---- Endpoints -------------------------------------------------------------
TREK = "https://trek.nasa.gov/tiles/Moon/EQ"
MOON_LAYERS = {
    # LROC WAC global morphology mosaic (imagery)
    "img": f"{TREK}/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.jpg",
    # LOLA hillshade (terrain shape)
    "shade": f"{TREK}/LRO_LOLA_Shade_Global_256ppd_v06/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.png",
}
GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
EARTH_LAYERS = {
    "img": "BlueMarble_NextGeneration",               # cloud-free true colour, 500 m
    "shade": "ASTER_GDEM_Greyscale_Shaded_Relief",    # terrain shape from ASTER GDEM
}
POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"

# ---- Raw rasters -----------------------------------------------------------
LOLA_DEM = RAW / "ldem_16.img"
DIVINER_ROCK = RAW / "dgdr_ra_avg_cyl_032_img.img"
DIVINER_NIGHT_T = RAW / "dgdr_st_avg_cyl_032_img.img"
ETOPO = RAW / "ETOPO_2022_v1_60s_N90W180_surface.nc"

# ---- Model -----------------------------------------------------------------
CLIP_ARCH = "ViT-B-32"
CLIP_WEIGHTS = "laion2b_s34b_b79k"
