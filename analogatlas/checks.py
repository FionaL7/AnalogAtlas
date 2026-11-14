"""Environment checks on Earth tiles: one definition, used by search and traps.

- traps.py (#30) names a lookalike a trap when it fails one of these.
- analog.cross_body (#33) pushes tiles that fail ice, plants or water down the
  ranking, so the search avoids the traps instead of only spotting them.

Needs the Earth environment columns (earth_ee.environment). A missing column
or value never fails a check: no data, no penalty.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ICE_MIN = 0.5        # ice_frac: mostly permanent ice
VEG_MIN = 0.3        # veg_frac: forest, savanna or crops
NDVI_MIN = 0.4       # ndvi: green even where land cover says otherwise
WATER_MIN = 0.3      # water_frac: lakes or wetland
WET_ARIDITY = 0.65   # aridity (precip / PET): UNEP drylands are below 0.65

CHECKS = ("ice", "vegetation", "water", "wet_climate")
# What the search pushes down. A wet climate is reported as a trap reason but
# not penalised: some well-studied analogs (Iceland) are wet.
PUSH_DOWN = ("ice", "vegetation", "water")


def _col(meta: pd.DataFrame, name: str) -> np.ndarray:
    if name not in meta:
        return np.full(len(meta), np.nan)
    return pd.to_numeric(meta[name], errors="coerce").to_numpy(dtype=float)


def env_flags(meta: pd.DataFrame) -> pd.DataFrame:
    """One boolean column per check, one row per tile. NaN compares False."""
    ice, veg = _col(meta, "ice_frac"), _col(meta, "veg_frac")
    ndvi, water, aridity = _col(meta, "ndvi"), _col(meta, "water_frac"), _col(meta, "aridity")
    with np.errstate(invalid="ignore"):
        is_ice = ice >= ICE_MIN
        return pd.DataFrame({
            "ice": is_ice,
            "vegetation": (veg >= VEG_MIN) | (ndvi >= NDVI_MIN),
            "water": water >= WATER_MIN,
            # ice caps have near-zero evaporation, so aridity runs high: not "wet"
            "wet_climate": (aridity >= WET_ARIDITY) & ~is_ice,
        }, index=meta.index)


def push_down_mask(meta: pd.DataFrame) -> np.ndarray:
    """True for tiles the search should push down (fail ice, plants or water)."""
    return env_flags(meta)[list(PUSH_DOWN)].any(axis=1).to_numpy()
