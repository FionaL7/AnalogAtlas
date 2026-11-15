"""Paths, constants and data-source endpoints shared by every script."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"            # downloaded rasters (LOLA, Diviner, ETOPO)
TILES = DATA / "tiles"        # downloaded image tiles, one folder per body/layer
INDEX = DATA / "index"        # parquet metadata + embedding matrices

# ---- Body constants -------------------------------------------------------
MOON_RADIUS_M = 1_737_400.0
MARS_RADIUS_M = 3_389_500.0
EARTH_RADIUS_M = 6_371_000.0
MOON_KM_PER_DEG = 2 * 3.141592653589793 * MOON_RADIUS_M / 1000 / 360    # ~30.3
MARS_KM_PER_DEG = 2 * 3.141592653589793 * MARS_RADIUS_M / 1000 / 360    # ~59.2
EARTH_KM_PER_DEG = 2 * 3.141592653589793 * EARTH_RADIUS_M / 1000 / 360  # ~111.2

# ---- Tiling ----------------------------------------------------------------
# Moon tiles are NASA Trek WMTS zoom-6 tiles: 2.8125 deg ~= 85 km per side.
MOON_ZOOM = 6
MOON_TILE_DEG = 180.0 / 2 ** MOON_ZOOM                 # 2.8125
TILE_KM = MOON_TILE_DEG * MOON_KM_PER_DEG              # ~85 km
MOON_MAX_ABS_LAT = 60.0     # Diviner GDR L3 cylindrical products cover +/-60
# Mars tiles are Trek zoom-7 tiles: 1.40625 deg ~= 83 km, so features are
# compared at (almost) the same ground scale as the ~85 km Moon/Earth tiles.
MARS_ZOOM = 7
MARS_TILE_DEG = 180.0 / 2 ** MARS_ZOOM                 # 1.40625
MARS_TILE_KM = MARS_TILE_DEG * MARS_KM_PER_DEG         # ~83 km
MARS_MAX_ABS_LAT = 60.0     # all 7 target sites (TARGET-SITES.md) are inside
# Earth tiles are requested from GIBS WMS with the same ground size (~85 km).
EARTH_TILE_DEG_LAT = TILE_KM / EARTH_KM_PER_DEG        # ~0.77 deg
EARTH_GRID_STEP_DEG = 1.0
EARTH_MAX_ABS_LAT = 82.0    # ASTER GDEM coverage limit is ~83 deg
TILE_PX = 256

# ---- Moon south pole (the `moon_polar` body) -------------------------------
# Past ~60 deg an equirectangular tile stops being square on the ground: at
# 85 S a 2.8125 deg tile is 6 km wide and 85 km tall, and the imagery comes
# back as horizontal smear. The pole therefore gets its own index on a south
# polar stereographic grid -- the same split every lunar mission data set makes
# (it is also why the Diviner cylindrical products stop at +/-60).
MOON_POLAR_MAX_LAT = -75.0     # edge of the LOLA/PGDA polar products
# Trek serves the polar layers from a separate tile tree whose tile matrix set
# is in metres from the pole, 2^(z+1) x 2^z tiles from the top-left corner.
TREK_SP = "https://trek.nasa.gov/tiles/Moon/SP"
MOON_SP_ZOOM = 6                       # 133.8 m/px; a 85 km chip is 638 px
MOON_SP_ORIGIN_M = (-1_095_930.0, 1_095_930.0)   # top-left (x, y) of the matrix
MOON_SP_EXTENT_M = 2_191_860.0                   # one tile at zoom 0
MOON_SP_LAYERS = {
    # LOLA polar hillshade, 75-90 S. Carries the visual channel at the pole.
    "shade": f"{TREK_SP}/LRO_LOLA_Shade_SPole75_30mp_v04/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.png",
    # LROC NAC average mosaic. Only 85.5-90 S, and half of the pole is in
    # genuine shadow, so many chips have no usable imagery -- see `has_img`.
    "img": f"{TREK_SP}/LRO_NAC_AvgMosaic_SPole855_1mp/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.png",
}

# ---- Endpoints -------------------------------------------------------------
TREK = "https://trek.nasa.gov/tiles/Moon/EQ"
MOON_LAYERS = {
    # LROC WAC global morphology mosaic (imagery)
    "img": f"{TREK}/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.jpg",
    # LOLA hillshade (terrain shape)
    "shade": f"{TREK}/LRO_LOLA_Shade_Global_256ppd_v06/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.png",
}
TREK_MARS = "https://trek.nasa.gov/tiles/Mars/EQ"
MARS_LAYERS = {
    # Viking MDIM 2.1 colour mosaic (imagery)
    "img": f"{TREK_MARS}/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.jpg",
    # MOLA + HRSC blended hillshade (terrain shape)
    "shade": f"{TREK_MARS}/Mars_MOLA_blend200ppx_HRSC_Shade_clon0dd_200mpp_lzw/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.jpg",
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
# South polar rasters. All four share one grid: south polar stereographic,
# centred on -90, x/y in metres from the pole, so one reader serves them all.
LOLA_POLAR_DEM = RAW / "ldem_75s_240m.img"                   # 240 m/px
LPSR = RAW / "LPSR_75S_120M_201608.IMG"                      # permanent shadow
AVG_ILLUM = RAW / "AVGVISIB_75S_120M_201608.IMG"             # mean solar illumination
EARTH_VIS = RAW / "AVGVISIB_75S_120M_201608_EARTH.IMG"       # mean Earth visibility

# ---- Model -----------------------------------------------------------------
CLIP_ARCH = "ViT-B-32"
CLIP_WEIGHTS = "laion2b_s34b_b79k"

# Local settings: a gitignored .env at the repo root (template: .env.example).
# Real environment variables win over .env.
import os  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

# ---- Google Earth Engine (Earth side) -------------------------------------
# Cloud project registered for non-commercial Earth Engine use, set in .env.
EE_PROJECT = os.environ.get("EE_PROJECT")
EE_DEM = "COPERNICUS/DEM/GLO30_2024_1"   # Copernicus DEM, 30 m
# Slope/relief are measured on the DEM resampled to ~1.85 km, the same
# baseline as LOLA LDEM_16 (1.9 km/px), so the numbers compare across bodies.
EARTH_SLOPE_SCALE_M = 1850
# Hillshade tiles: computed at 118 m (like LOLA 256 ppd), sun 315/45 deg (the
# Moon tiles' flat-ground grey of ~176 implies a 45 deg sun). Heights are
# exaggerated x3 only to avoid 8-bit banding; contrast is normalised per tile
# before embedding anyway (embed.normalize_shade), on both bodies.
EARTH_SHADE_SCALE_M = 118
EARTH_SHADE_ZFACTOR = 3
SUN_AZIMUTH, SUN_ELEVATION = 315, 45
