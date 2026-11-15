"""Search index + analog scoring.

Similarity has two parts:
  * a learned part: CLIP embeddings of terrain-shape (hillshade) and imagery tiles
  * a physical part: slope, relief, temperature, atmosphere, gravity, water...
The physical breakdown is what explains *where the analogy holds and where it
breaks down*, which the challenge asks for explicitly.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
import requests

from . import config as C
from .checks import PUSH_DOWN, env_flags
from .sites import KNOWN_EARTH_ANALOGS

log = logging.getLogger("analogatlas")


# ------------------------------------------------------------- index -------
@dataclass
class BodyIndex:
    meta: pd.DataFrame
    shade: np.ndarray   # (N, D) rotation-averaged hillshade embeddings
    img: np.ndarray     # (N, D) imagery embeddings

    def nearest_tile(self, lat: float, lon: float) -> int:
        d = haversine_deg(self.meta.lat.values, self.meta.lon.values, lat, lon)
        return int(np.argmin(d))


class IndexMismatchError(RuntimeError):
    """The meta rows and the embedding rows no longer line up."""


def tile_order_digest(tile_ids) -> str:
    """SHA-256 over the tile_id sequence: changes if any row moves."""
    return hashlib.sha256("\n".join(map(str, tile_ids)).encode()).hexdigest()


def write_order_stamp(body: str, meta: pd.DataFrame, directory=None) -> None:
    """Record the row order the embeddings were written in (02_features.py).

    `{body}_order.json` sits next to the index. load_index() re-checks it, so a
    re-sorted or re-written `_meta.parquet` can't silently pair rows with the
    wrong embeddings (ARCHITECTURE.md §7).
    """
    directory = directory or C.INDEX
    stamp = {"rows": int(len(meta)), "tile_id_sha256": tile_order_digest(meta.tile_id)}
    (directory / f"{body}_order.json").write_text(json.dumps(stamp, indent=2))


def load_index(body: str) -> BodyIndex:
    meta = pd.read_parquet(C.INDEX / f"{body}_meta.parquet")
    shade = np.load(C.INDEX / f"{body}_shade.npy").astype(np.float32)
    img = np.load(C.INDEX / f"{body}_img.npy").astype(np.float32)

    if not len(meta) == len(shade) == len(img):
        raise IndexMismatchError(
            f"{body} index rows differ: meta={len(meta)} shade={len(shade)} img={len(img)}")

    stamp_path = C.INDEX / f"{body}_order.json"
    if stamp_path.exists():
        stamp = json.loads(stamp_path.read_text())
        if stamp["rows"] != len(meta) or stamp["tile_id_sha256"] != tile_order_digest(meta.tile_id):
            raise IndexMismatchError(
                f"{body}_meta.parquet row order changed since the embeddings were written; "
                f"rebuild with scripts/02_features.py {body}")
    else:
        # Indexes built before the stamp existed: lengths are checked, order can't be.
        log.warning("%s has no %s; row order not verified. Rebuild with "
                    "scripts/02_features.py %s to add it.", body, stamp_path.name, body)
    return BodyIndex(meta, shade, img)


def haversine_deg(lat1, lon1, lat2, lon2):
    """Great-circle angle in degrees (body-independent)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(a, 0, 1))))


def known_analog_name(lat: float, lon: float, radius_km: float = 150) -> str | None:
    for name, (la, lo) in KNOWN_EARTH_ANALOGS.items():
        if haversine_deg(lat, lon, la, lo) * C.EARTH_KM_PER_DEG < radius_km:
            return name
    return None


# ------------------------------------------------------------ search -------
def search(index: BodyIndex, query_vec: np.ndarray, k: int = 12,
           w_shade: float = 0.6, mask: np.ndarray | None = None) -> pd.DataFrame:
    """Rank tiles by a weighted mix of shade- and imagery-embedding cosine."""
    s = w_shade * (index.shade @ query_vec) + (1 - w_shade) * (index.img @ query_vec)
    if mask is not None:
        s = np.where(mask, s, -np.inf)
    top = np.argsort(-s)[:k]
    out = index.meta.iloc[top].copy()
    out["score"] = s[top]
    out["row"] = top
    return out


# How hard the search pushes down tiles that fail the ice, plant or water
# checks (#33), per unit of w_phys. At the default w_phys=0.3 that is 2.4 in
# score units, about 3.4 standard deviations of visual similarity: an ice
# sheet that is the closest lookalike falls well out of the top results.
# At w_phys=0 there is no push-down: the pure image-only ranking.
ENV_PENALTY = 8.0


def is_mars(row: pd.Series) -> bool:
    return row.get("body") == "mars"


# Mars: poleward of ~35 deg, ice is stable just under the surface (the SWIM
# maps find it down to ~35 N), and GRS sees it as hydrogen. A tile that is both
# is "ice-rich": glaciers and frozen ground on Earth are then real analogs
# (Deuteronilus Mensae is debris-covered glacier), not lookalike traps.
MARS_ICE_LAT = 35.0
MARS_ICE_WEH = 6.0      # GRS water-equivalent hydrogen, weight %
ALBEDO_SCALE = 0.1      # albedo 0.1 apart -> closeness 0.37


def _has(row: pd.Series, col: str) -> bool:
    v = row.get(col)
    return v is not None and not pd.isna(v)


def mars_ice_rich(row: pd.Series) -> bool:
    return bool(is_mars(row) and _has(row, "weh_pct") and row.weh_pct >= MARS_ICE_WEH
                and abs(float(row.lat)) >= MARS_ICE_LAT)


def push_down_for(src_row: pd.Series, dst_meta: pd.DataFrame) -> np.ndarray:
    """Earth tiles the search pushes down for this source tile. Ice is not
    pushed down for an ice-rich Mars tile; plants and water always are."""
    checks = [c for c in PUSH_DOWN if not (c == "ice" and mars_ice_rich(src_row))]
    return env_flags(dst_meta)[checks].any(axis=1).to_numpy()


def _col(meta: pd.DataFrame, name: str) -> np.ndarray:
    if name not in meta:
        return np.full(len(meta), np.nan)
    return pd.to_numeric(meta[name], errors="coerce").to_numpy(dtype=float)


def _albedo_closeness(earth_albedo, mars_albedo):
    return np.exp(-np.abs(np.asarray(earth_albedo, dtype=float) - float(mars_albedo)) / ALBEDO_SCALE)


def _physical(s_row: pd.Series, dst_meta: pd.DataFrame) -> np.ndarray:
    """Closeness of the like-for-like measurements, 0-1 per dst tile.

    Slope and relief on every body. Mars adds albedo (TES vs MODIS), the one
    extra quantity measured the same way on both worlds. Proxies (thermal
    inertia, dust) are on the report card but stay out of the score.
    """
    terms = [_closeness(dst_meta.slope_med.values, s_row.slope_med, 1.0),
             _closeness(dst_meta.relief_km.values, s_row.relief_km, 1.0)]
    if not is_mars(s_row):
        return np.nan_to_num(np.mean(terms, axis=0), nan=0.0)
    if _has(s_row, "albedo"):
        terms.append(_albedo_closeness(_col(dst_meta, "albedo"), s_row.albedo))
    stack = np.vstack(terms)
    seen = (~np.isnan(stack)).sum(axis=0)     # a missing value is skipped, not a zero
    return np.where(seen > 0, np.nansum(stack, axis=0) / np.maximum(seen, 1), 0.0)


def cross_body_scores(src: BodyIndex, i: int, dst: BodyIndex, w_phys: float = 0.3
                      ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """cross_body's score for every dst tile: (score, visual, physical, pushed)."""
    visual = dst.shade @ src.shade[i]
    s_row = src.meta.iloc[i]
    phys = _physical(s_row, dst.meta)
    # standardise the visual score so the two parts mix on comparable scales
    v = (visual - visual.mean()) / (visual.std() + 1e-9)
    pushed = push_down_for(s_row, dst.meta)
    score = (1 - w_phys) * v + w_phys * (phys - 0.5) * 4 - w_phys * ENV_PENALTY * pushed
    return score, visual, phys, pushed


def cross_body(src: BodyIndex, i: int, dst: BodyIndex, k: int = 12,
               mask: np.ndarray | None = None, w_phys: float = 0.3) -> pd.DataFrame:
    """Tiles on `dst` most similar to tile i on `src`.

    Visual: cosine between rotation-averaged hillshade embeddings (terrain shape,
    independent of colour and sun direction).
    Physical: closeness of slope and relief, measured on 1.9 km DEMs on both bodies.
    A Mars source adds albedo closeness (see `_physical`).
    Environment: Earth tiles that are ice, plants or water are pushed down
    (checks.PUSH_DOWN), so lookalike traps don't lead the results. Ice is kept
    for an ice-rich Mars tile (`mars_ice_rich`).
    """
    score, visual, phys, pushed = cross_body_scores(src, i, dst, w_phys)
    if mask is not None:
        score = np.where(mask, score, -np.inf)
    top = np.argsort(-score)[:k]
    out = dst.meta.iloc[top].copy()
    out["score"], out["visual_cos"], out["physical"], out["row"] = score[top], visual[top], phys[top], top
    out["env_pushed"] = pushed[top]
    # percentile of the visual similarity among all candidate tiles -> 0..1
    out["visual_cos_scaled"] = [(visual < v).mean() for v in visual[top]]
    return out


def _closeness(a, b, scale):
    """1 when equal, decays with log-ratio distance (relief/slope span decades)."""
    a = np.asarray(a, dtype=float)
    return np.exp(-np.abs(np.log1p(a) - np.log1p(b)) / scale)


# ---------------------------------------------------- NASA POWER climate ----
@lru_cache(maxsize=512)
def earth_climate(lat: float, lon: float) -> dict:
    """NASA POWER climatology (2001-2025) for one point. Cached; ~1 s per call."""
    params = "TS_MIN,TS_MAX,T2M_RANGE,PRECTOTCORR,RH2M,WS10M,ALLSKY_SFC_SW_DWN"
    r = requests.get(C.POWER_URL, timeout=60, params=dict(
        parameters=params, community="RE", latitude=round(lat, 2),
        longitude=round(lon, 2), format="JSON"))
    r.raise_for_status()
    p = r.json()["properties"]["parameter"]
    return {k: v.get("ANN") for k, v in p.items()}


# -------------------------------------------------------- breakdown --------
# Every report-card row has a `kind`:
#   compare        measured on both bodies; match is 0-1
#   no_equivalent  measured on the Moon only; match is None
#   earth_limit    no place on Earth can reproduce it; match is always 0
# The UI groups by `kind`, never by guessing from the score (issue #20).
# Every row also has a `basis`, so the card never passes a model or a proxy
# off as a measurement:
#   measured   read from data on the source body (and on Earth, for compare rows)
#   modelled   the source-body value comes from a model
#   proxy      two different quantities standing in for the same property
# The source-body value is in the `moon` key whatever the body (Moon or Mars).
MODELLED = "modelled from latitude, not measured"
POLAR_MODELLED = ("modelled from the tile's shadowed fraction, not measured; "
                  "a latitude fit does not apply at the pole")

# Fixed rows: what Earth cannot reproduce, whichever tile is chosen. The brief
# calls recognising these "part of good scientific analysis".
EARTH_LIMITS = [
    dict(dimension="Atmosphere", moon="vacuum (trace exosphere)", earth="1 bar at sea level",
         note="No air: no convective cooling and no wind. Dust, thermal and EVA tests behave differently"),
    dict(dimension="Gravity", moon="1.62 m/s² (1/6 g)", earth="9.81 m/s²",
         note="Mobility and construction tests overestimate traction and load"),
    dict(dimension="Radiation", moon="~1.4 mSv/day at the surface (Chang'e-4)",
         earth="~0.007 mSv/day natural background",
         note="No atmosphere or global magnetic field to shield cosmic rays and solar particle events"),
    dict(dimension="Magnetic field", moon="no global field (local crustal anomalies)",
         earth="global magnetosphere",
         note="Earth's field deflects the solar wind; on the Moon it reaches the surface"),
    dict(dimension="Day/night cycle", moon="~29.5 Earth days (~2 weeks light, ~2 weeks dark)",
         earth="24 hours",
         note="Long nights drive power and thermal design; some polar peaks are lit almost continuously"),
    dict(dimension="Regolith dust", moon="sharp, unweathered, electrostatically charged",
         earth="rounded by wind and water",
         note="Earth dust is a poor stand-in for lunar abrasion, adhesion and seal wear"),
]


def _adder(rows: list):
    def add(dim, mv, ev, match, note, kind="compare", basis="measured"):
        rows.append(dict(dimension=dim, moon=mv, earth=ev,
                         match=None if match is None else float(np.clip(match, 0, 1)),
                         note=note, kind=kind, basis=basis))
    return add


def breakdown(moon: pd.Series, earth: pd.Series, climate: dict | None) -> pd.DataFrame:
    """Dimension-by-dimension comparison of a lunar or Mars tile and an Earth tile.
    Returns rows of (dimension, moon value, earth value, match 0-1, note, kind, basis)."""
    if is_mars(moon):
        return pd.DataFrame(mars_rows(moon, earth, climate))
    rows = []
    polar = "psr_frac" in moon and not pd.isna(moon.get("psr_frac"))
    # Both temperature models are models, but not the same one, and the UI
    # must not claim the polar numbers came from a latitude fit.
    modelled = POLAR_MODELLED if polar else MODELLED
    add = _adder(rows)

    add("Terrain shape (ML)", "-", "-", earth.get("visual_cos_scaled"),
        "CLIP similarity of hillshade tiles, sun-direction invariant")
    add("Median slope", f"{moon.slope_med:.1f}°", f"{earth.slope_med:.1f}°",
        float(_closeness(earth.slope_med, moon.slope_med, 1.0)),
        "LOLA vs the Earth DEM, both measured at ~1.9 km/px")
    add("Local relief", f"{moon.relief_km:.2f} km", f"{earth.relief_km:.2f} km",
        float(_closeness(earth.relief_km, moon.relief_km, 1.0)),
        "98th-2nd percentile elevation within ~85 km")
    if climate:
        ts_min, ts_max = climate["TS_MIN"], climate["TS_MAX"]
        swing_e, swing_m = ts_max - ts_min, moon.t_max_k - moon.t_min_k
        add("Surface temperature swing", f"{swing_m:.0f} K", f"{swing_e:.0f} K",
            swing_e / swing_m, f"Moon: {modelled}. Earth: NASA POWER skin temperature",
            basis="modelled")
        add("Coldest surface", f"{moon.t_min_k - 273.15:.0f} °C", f"{ts_min:.0f} °C",
            math.exp(-abs((ts_min + 273.15) - moon.t_min_k) / 60),
            f"Moon: {modelled}. Earth: NASA POWER skin temperature", basis="modelled")
        precip = climate["PRECTOTCORR"]
        add("Dryness", "no liquid water", f"{precip:.2f} mm/day", math.exp(-precip / 0.5),
            "NASA POWER precipitation; hyper-arid < 0.1 mm/day")
        add("Solar exposure", "unfiltered", f"{climate['ALLSKY_SFC_SW_DWN']:.1f} kWh/m²/day",
            climate["ALLSKY_SFC_SW_DWN"] / 8.0, "Higher = closer to airless illumination")
    if "rock_abundance" in moon and not pd.isna(moon.rock_abundance):
        add("Surface rock cover", f"{moon.rock_abundance * 100:.1f}%", "no global Earth equivalent",
            None, "Diviner rock abundance - landing-hazard proxy", kind="no_equivalent")
    if polar:
        rows += _polar_rows(moon, earth)
    for lim in EARTH_LIMITS:
        add(lim["dimension"], lim["moon"], lim["earth"], 0.0, lim["note"], kind="earth_limit")
    return pd.DataFrame(rows)


AXIAL_TILT_DEG = 23.44
EARTH_SUNLIT_FRACTION = 0.5     # annual, at every latitude: Earth rotates daily


def polar_night_days(lat: float) -> float:
    """Length of the continuous polar night at this latitude, in days.

    Geometric, ignoring refraction and terrain. The Sun stays below the
    horizon while the subsolar latitude is beyond 90 - |lat| in the opposite
    hemisphere; that holds for a fraction 0.5 - asin(s)/pi of the year, where
    s = (90 - |lat|) / tilt. Zero outside the polar circles, half a year at
    the pole itself.
    """
    if abs(lat) <= 90 - AXIAL_TILT_DEG:
        return 0.0
    s = float(np.clip((90 - abs(lat)) / AXIAL_TILT_DEG, 0.0, 1.0))
    return 365.25 * (0.5 - math.asin(s) / math.pi)


def _polar_rows(moon: pd.Series, earth: pd.Series) -> list[dict]:
    """Report-card rows that only the south polar index can fill (#26).

    These are the dimensions a permanent base is actually sited on, and each
    has a real Earth counterpart, which is the point: they compare rather than
    just assert that the pole is different.

    Temperature is deliberately absent here: `breakdown` already emits the
    coldest-surface row from `t_min_k`, which the polar index fills from
    `rasters.polar_temperature_model`. Repeating it would be two rows for one
    measurement.
    """
    rows = []
    add = _adder(rows)

    add("Sunlight availability", f"{moon.illum_max * 100:.0f}% of the time",
        f"~{EARTH_SUNLIT_FRACTION * 100:.0f}% of the year",
        math.exp(-abs(moon.illum_max - EARTH_SUNLIT_FRACTION) / 0.25),
        "Moon: LOLA illumination model over 18.6 years, best-lit point in the tile. "
        "Earth sits near 50% at every latitude because it rotates daily, so a "
        "near-permanently-lit ridge is the one thing no Earth site reproduces",
        basis="modelled")
    night = polar_night_days(float(earth.lat))
    add("Longest continuous darkness",
        "permanent inside a PSR; ~14 Earth days elsewhere",
        f"{night:.0f} days of polar night" if night else "none (sun rises daily)",
        math.exp(-abs(night - 14) / 30) if night else 0.0,
        "Earth figure is geometric polar night, ignoring refraction and terrain. "
        "This is where Antarctic and high-Arctic sites earn their place")
    add("Permanent shadow", f"{moon.psr_frac * 100:.1f}% of the tile",
        "no permanent shadow at this scale", None,
        "LOLA-modelled permanently shadowed regions. Earth's axial tilt and "
        "atmosphere mean nowhere stays sunless year round at 85 km scale",
        kind="no_equivalent", basis="modelled")
    add("Direct-to-Earth comms", f"{moon.earth_vis * 100:.0f}% of the time",
        "always available", None,
        "LOLA Earth-visibility model: a south polar base can lose line of "
        "sight to Earth entirely, which has no terrestrial equivalent",
        kind="no_equivalent", basis="modelled")
    return rows


# ------------------------------------------------------------- Mars --------
MARS_MODELLED = "modelled from latitude, albedo and thermal inertia, not measured"

# What Earth cannot reproduce for Mars, whichever tile is chosen.
MARS_LIMITS = [
    dict(dimension="Atmosphere", moon="~0.6 kPa, 95% CO₂", earth="101 kPa, nitrogen and oxygen",
         note="Under 1% of Earth's pressure: parachutes, rotors, cooling and wind loads on "
              "dust all behave differently"),
    dict(dimension="Gravity", moon="3.71 m/s² (38% of Earth's)", earth="9.81 m/s²",
         note="Mobility and construction tests overestimate traction and load"),
    dict(dimension="Radiation", moon="~0.67 mSv/day at the surface (Curiosity RAD)",
         earth="~0.007 mSv/day natural background",
         note="A thin atmosphere and no global magnetic field: cosmic rays and solar "
              "particle events reach the ground"),
    dict(dimension="Sunlight", moon="~590 W/m² above the atmosphere (43% of Earth's)",
         earth="~1,361 W/m² above the atmosphere",
         note="Mars is 1.52 times farther from the Sun, so solar-power tests on Earth read high"),
    dict(dimension="Soil chemistry", moon="0.5-1% perchlorate salts in the soil (Phoenix)",
         earth="trace amounts, in the driest deserts only",
         note="Perchlorates are toxic and change how soil, water and organics react; "
              "Earth soils need them added for ISRU and life-detection tests"),
    dict(dimension="Global dust storms", moon="planet-encircling storms every few Mars years",
         earth="regional storms only",
         note="Weeks of dimmed sunlight across the whole planet have no Earth counterpart"),
]

MARS_SOL_HOURS = 24.66
# Thermal inertia (TES), J m^-2 K^-1 s^-1/2: below ~100 is loose fine dust,
# above ~350 is rock or cemented ground (Putzig et al. 2005). On Earth the
# stand-in is the day-night surface temperature swing of bare ground: loose
# dry fines swing far, rock and damp ground swing little.
TI_DUST, TI_ROCK = 40.0, 600.0
SWING_ROCK_C, SWING_DUST_C = 8.0, 40.0
# TES dust cover index: below ~0.94 dust-covered, above ~0.97 dust-free
# (Ruff & Christensen 2002). Earth stand-in: MERRA-2 dust optical depth.
DCI_DUSTY, DCI_CLEAR = 0.93, 0.97
AOD_DUSTY = 0.3


def looseness_from_ti(ti: float) -> float:
    """0 = rock, 1 = loose dust, from Mars thermal inertia (log scale)."""
    return float(np.clip(1 - math.log(ti / TI_DUST) / math.log(TI_ROCK / TI_DUST), 0, 1))


def looseness_from_swing(swing_c):
    """0 = rock, 1 = loose dust, from Earth's day-night surface swing."""
    return np.clip((np.asarray(swing_c, dtype=float) - SWING_ROCK_C)
                   / (SWING_DUST_C - SWING_ROCK_C), 0, 1)


def material_words(ti: float) -> str:
    return "loose dust" if ti < 100 else "sand and crusted soil" if ti < 350 else "rock or cemented ground"


def mars_dustiness(dci: float) -> float:
    return float(np.clip((DCI_CLEAR - dci) / (DCI_CLEAR - DCI_DUSTY), 0, 1))


def frozen_match(lst_mean_c):
    """1 where the ground is frozen on average, falling off above 0 °C."""
    return np.exp(-np.maximum(np.asarray(lst_mean_c, dtype=float), 0) / 10.0)


def earth_mean_c(earth):
    """Mean surface temperature of Earth tiles (a row or a whole table), °C.
    `lst_mean_c` if the index has it, else the mean of the MODIS day and night
    means, which is the same number."""
    def col(name):
        if isinstance(earth, pd.DataFrame):
            return _col(earth, name)
        return float(earth[name]) if _has(earth, name) else float("nan")
    mean = np.asarray(col("lst_mean_c"), dtype=float)
    return np.where(np.isnan(mean), (np.asarray(col("lst_day_c"), dtype=float)
                                     + np.asarray(col("lst_night_c"), dtype=float)) / 2, mean)


def mars_rows(mars: pd.Series, earth: pd.Series, climate: dict | None) -> list[dict]:
    """Report-card rows for a Mars tile. Any Mars-only or Earth column may be
    missing or NaN; its row is then left out, never faked."""
    rows: list[dict] = []
    add = _adder(rows)

    add("Terrain shape (ML)", "-", "-", earth.get("visual_cos_scaled"),
        "CLIP similarity of hillshade tiles, sun-direction invariant")
    add("Median slope", f"{mars.slope_med:.1f}°", f"{earth.slope_med:.1f}°",
        float(_closeness(earth.slope_med, mars.slope_med, 1.0)),
        "MOLA vs the Earth DEM, both measured at ~1.9 km/px")
    add("Local relief", f"{mars.relief_km:.2f} km", f"{earth.relief_km:.2f} km",
        float(_closeness(earth.relief_km, mars.relief_km, 1.0)),
        "98th-2nd percentile elevation within ~85 km")
    if _has(mars, "albedo") and _has(earth, "albedo"):
        add("Surface brightness (albedo)", f"{mars.albedo:.2f}", f"{earth.albedo:.2f}",
            float(_albedo_closeness(earth.albedo, mars.albedo)),
            "TES albedo vs MODIS albedo: how much sunlight the ground reflects")
    if _has(mars, "thermal_inertia") and _has(earth, "lst_swing_c"):
        add("Surface material", f"{mars.thermal_inertia:.0f} tiu ({material_words(mars.thermal_inertia)})",
            f"{earth.lst_swing_c:.0f} °C day-night swing",
            1 - abs(looseness_from_ti(mars.thermal_inertia) - float(looseness_from_swing(earth.lst_swing_c))),
            "Mars: TES thermal inertia (low = loose dust, high = rock). Earth: MODIS day-night "
            "surface swing as a stand-in; air and soil moisture damp it, so read it as a guide",
            basis="proxy")
    if _has(mars, "dust_index") and _has(earth, "dust_aod"):
        add("Dust", f"dust cover index {mars.dust_index:.3f}", f"dust optical depth {earth.dust_aod:.2f}",
            1 - abs(mars_dustiness(mars.dust_index) - float(np.clip(earth.dust_aod / AOD_DUSTY, 0, 1))),
            "Mars: TES dust cover index (dust lying on the surface; lower = dustier). "
            "Earth: MERRA-2 dust in the air. Related, not the same quantity", basis="proxy")
    if climate:
        ts_min, ts_max = climate["TS_MIN"], climate["TS_MAX"]
        if _has(mars, "t_max_k") and _has(mars, "t_min_k"):
            swing_e, swing_m = ts_max - ts_min, mars.t_max_k - mars.t_min_k
            add("Surface temperature swing", f"{swing_m:.0f} K", f"{swing_e:.0f} K",
                swing_e / swing_m, f"Mars: {MARS_MODELLED}. Earth: NASA POWER skin temperature",
                basis="modelled")
            add("Coldest surface", f"{mars.t_min_k - 273.15:.0f} °C", f"{ts_min:.0f} °C",
                math.exp(-abs((ts_min + 273.15) - mars.t_min_k) / 60),
                f"Mars: {MARS_MODELLED}. Earth: NASA POWER skin temperature", basis="modelled")
        precip = climate["PRECTOTCORR"]
        add("Dryness", "no liquid water at the surface", f"{precip:.2f} mm/day",
            math.exp(-precip / 0.5), "NASA POWER precipitation; hyper-arid < 0.1 mm/day")
    mean_c = float(earth_mean_c(earth))
    if mars_ice_rich(mars) and not math.isnan(mean_c):
        add("Ground ice", f"{mars.weh_pct:.0f}% water-equivalent hydrogen",
            f"mean surface {mean_c:.0f} °C ({'frozen ground' if mean_c < 0 else 'not frozen'})",
            float(frozen_match(mean_c)),
            "Mars: GRS hydrogen in the top metre, averaged over ~300 km, so regional "
            "context, not a per-tile reading. Earth: MODIS mean surface temperature "
            "below 0 °C as a stand-in for frozen ground", basis="proxy")
    elif _has(mars, "weh_pct"):
        add("Near-surface water", f"{mars.weh_pct:.0f}% water-equivalent hydrogen",
            "no comparable global measurement", None,
            "GRS hydrogen in the top metre, averaged over ~300 km: bound in minerals "
            "here rather than ice. Regional context only", kind="no_equivalent")
    if _has(mars, "hydrous_count") and mars.hydrous_count > 0:
        add("Water-altered minerals", f"{int(mars.hydrous_count)} CRISM detections in the tile",
            "no global Earth mineral layer", None,
            "CRISM hydrated-mineral detections (clays, sulfates): a sign of past water. "
            "Check the Earth site's geology by hand", kind="no_equivalent")
    add("Day length", "24 h 37 min", "24 h", math.exp(-abs(MARS_SOL_HOURS - 24) / 24),
        "Nearly the same: crew routines, daily thermal cycles and solar-power days carry over")
    for lim in MARS_LIMITS:
        add(lim["dimension"], lim["moon"], lim["earth"], 0.0, lim["note"], kind="earth_limit")
    return rows
