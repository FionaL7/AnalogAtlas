"""Analog portfolio (#31): the fewest Earth sites that together cover a target.

No single Earth site matches a lunar site on every count. One has the right
slopes, another the deep cold, a third is easy to reach. The portfolio picks a
small set of sites that between them cover every dimension.

How:
1. Score every Earth tile 0-1 on each dimension for one lunar tile
   (`dimension_scores`). 1 = as good a match as possible.
2. A tile "covers" a dimension when its score reaches the threshold
   (`thresholds`). Where no Earth tile can reach it (no place on Earth swings
   as far in temperature as the Moon), the bar drops to 90% of Earth's best,
   and the dimension is flagged `earth_best_only` so the app can say so.
3. Greedy set cover (`greedy_cover`): keep picking the tile that covers the
   most dimensions not yet covered, until all are covered.

Tiles that fail the ice, plants or water checks (checks.PUSH_DOWN) are never
picked: they are the lookalike traps (#30).

Greedy set cover is not always the true minimum, but it is within a small
factor of it, and with 7 dimensions it is almost always exact.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .analog import BodyIndex, _closeness
from .checks import push_down_mask

HOLDS = 0.6           # a match "holds" (same bar as fieldtest.HOLDS and the UI)
SHAPE_MIN = 0.9       # terrain shape: top 10% of Earth tiles by visual similarity
EARTH_BEST_SHARE = 0.9    # if Earth can't reach the bar, within 90% of its best
DRY_MM = 182.5        # precip scale: 0.5 mm/day, as in analog.breakdown
SUN_SCALE_DEG = 15.0  # noon sun elevation: 15 degrees apart -> 0.37
FROST_C = -20.0       # coldest night at or below this counts as frozen ground
ACCESS_MIN = 720.0    # travel time scale: 12 hours to a city -> 0.37


@dataclass(frozen=True)
class Dimension:
    id: str
    label: str
    note: str
    threshold: float


DIMENSIONS = [
    Dimension("shape", "Terrain shape",
              "Visual similarity of the hillshade tiles (CLIP), as a percentile among Earth tiles",
              SHAPE_MIN),
    Dimension("slope", "Slope and relief",
              "Closeness of median slope and local relief, both measured at ~1.9 km/px", HOLDS),
    Dimension("thermal_swing", "Thermal swing",
              "Earth's hottest day minus coldest night (MODIS) as a share of the Moon's "
              "modelled swing", HOLDS),
    Dimension("dryness", "Dryness",
              "Annual rainfall (TerraClimate); the Moon has no liquid water", HOLDS),
    Dimension("sun_angle", "Low sun angle",
              "Noon sun height, set by latitude on both bodies. Low at the lunar pole, "
              "so long shadows and glare for cameras and solar panels", HOLDS),
    Dimension("rock_ice", "Bare rock (frozen at the pole)",
              "Bare or sparse ground (MODIS land cover). For a polar target the ground must "
              "also freeze hard, like the cold traps that hold ice", HOLDS),
    Dimension("access", "Access",
              "Travel time to the nearest city. Practical, not similarity: a field team "
              "must get there", HOLDS),
]
DIMENSION_IDS = [d.id for d in DIMENSIONS]


def _col(meta: pd.DataFrame, name: str) -> np.ndarray:
    if name not in meta:
        return np.full(len(meta), np.nan)
    return pd.to_numeric(meta[name], errors="coerce").to_numpy(dtype=float)


def is_polar(row: pd.Series) -> bool:
    return "psr_frac" in row and not pd.isna(row.get("psr_frac"))


def noon_sun_deg(lat) -> np.ndarray:
    """Noon sun height above the horizon, averaged over the year: 90 - |lat|.
    True on both bodies to within the tilt (Moon 1.5 deg; Earth's 23.4 deg
    averages out over a year)."""
    return 90.0 - np.abs(np.asarray(lat, dtype=float))


def moon_swing_k(moon: pd.Series) -> float:
    return float(moon.t_max_k - moon.t_min_k)


def earth_swing_k(earth: pd.DataFrame) -> np.ndarray:
    """Hottest day minus coldest night; the day-night mean swing if those are missing."""
    swing = _col(earth, "lst_hot_c") - _col(earth, "lst_cold_c")
    return np.where(np.isnan(swing), _col(earth, "lst_swing_c"), swing)


def dimension_scores(src: BodyIndex, i: int, dst: BodyIndex) -> pd.DataFrame:
    """One 0-1 score per dimension (columns) for every Earth tile (rows).
    Missing data scores 0: it can't cover a dimension."""
    moon = src.meta.iloc[i]
    earth = dst.meta
    polar = is_polar(moon)

    visual = dst.shade @ src.shade[i]
    order = visual.argsort()
    shape = np.empty(len(visual))
    shape[order] = np.arange(len(visual)) / max(len(visual) - 1, 1)

    slope = np.mean([_closeness(_col(earth, "slope_med"), moon.slope_med, 1.0),
                     _closeness(_col(earth, "relief_km"), moon.relief_km, 1.0)], axis=0)
    swing = earth_swing_k(earth) / moon_swing_k(moon)
    dry = np.exp(-_col(earth, "precip_mm") / DRY_MM)
    sun = np.exp(-np.abs(noon_sun_deg(earth.lat.values) - noon_sun_deg(moon.lat)) / SUN_SCALE_DEG)
    rock = _col(earth, "barren_frac") + 0.5 * _col(earth, "sparse_frac")
    if polar:
        cold = _col(earth, "lst_cold_c")
        rock = rock * np.exp(-np.maximum(cold - FROST_C, 0) / 15.0)
    access = np.exp(-_col(earth, "access_min") / ACCESS_MIN)

    out = pd.DataFrame(dict(shape=shape, slope=slope, thermal_swing=swing, dryness=dry,
                            sun_angle=sun, rock_ice=rock, access=access), index=earth.index)
    return out.clip(0, 1).fillna(0.0)


def moon_values(moon: pd.Series) -> dict[str, str]:
    """What each dimension looks like on the Moon side, in words."""
    polar = is_polar(moon)
    return dict(
        shape="-",
        slope=f"{moon.slope_med:.1f}° median, {moon.relief_km:.2f} km relief",
        thermal_swing=f"{moon_swing_k(moon):.0f} K (modelled)",
        dryness="no liquid water",
        sun_angle=f"{float(noon_sun_deg(moon.lat)):.0f}° at noon",
        rock_ice=("rock and regolith; ice in permanently shadowed cold traps" if polar
                  else "bare rock and regolith"),
        access="-",
    )


def thresholds(scores: pd.DataFrame) -> dict[str, tuple[float, bool]]:
    """{dimension: (bar to cover it, earth_best_only)}. If no candidate reaches
    the dimension's bar, the bar becomes 90% of the best candidate."""
    out = {}
    for d in DIMENSIONS:
        best = float(scores[d.id].max()) if len(scores) else 0.0
        if best >= d.threshold:
            out[d.id] = (d.threshold, False)
        else:
            out[d.id] = (EARTH_BEST_SHARE * best, True)
    return out


def greedy_cover(scores: pd.DataFrame, bars: dict[str, float],
                 max_sites: int = 7) -> tuple[list, set[str]]:
    """Greedy set cover. Returns (picked row labels, dimensions left uncovered).

    Each step picks the tile that covers the most uncovered dimensions; ties go
    to the higher total score, so the picks are good all-round sites too.
    A dimension with a bar of 0 (no Earth tile scores at all) is uncoverable.
    """
    covers = pd.DataFrame({d: (scores[d] >= b) & (b > 0) for d, b in bars.items()})
    total = scores.sum(axis=1).to_numpy()
    left = {d for d in bars if covers[d].any()}
    uncoverable = set(bars) - left
    picked: list = []
    while left and len(picked) < max_sites:
        gain = covers[sorted(left)].sum(axis=1).to_numpy()
        if gain.max() == 0:
            break
        best = np.flatnonzero(gain == gain.max())
        j = best[np.argmax(total[best])]
        label = scores.index[j]
        picked.append(label)
        left -= {d for d in left if covers.at[label, d]}
    return picked, left | uncoverable


def build_portfolio(src: BodyIndex, i: int, dst: BodyIndex, max_sites: int = 7) -> dict:
    """The portfolio for lunar tile i: dimensions, picked sites, and how many
    dimensions the best single site covers on its own (for comparison)."""
    moon = src.meta.iloc[i]
    scores = dimension_scores(src, i, dst)
    eligible = scores[~push_down_mask(dst.meta)]
    bar_info = thresholds(eligible)
    bars = {d: b for d, (b, _) in bar_info.items()}

    picked, uncovered = greedy_cover(eligible, bars, max_sites)
    covered_by: dict[str, str] = {}
    sites = []
    for n, label in enumerate(picked, start=1):
        row = dst.meta.loc[label]
        s = eligible.loc[label]
        covers = [d for d in DIMENSION_IDS if bars[d] > 0 and s[d] >= bars[d]]
        new = [d for d in covers if d not in covered_by]
        for d in new:
            covered_by[d] = str(row.tile_id)
        known = row.get("known_analog")
        sites.append(dict(
            order=n, tile_id=str(row.tile_id),
            lat=round(float(row.lat), 3), lon=round(float(row.lon), 3),
            known_analog=None if known is None or pd.isna(known) else str(known),
            covers=covers, adds=new,
            scores={d: round(float(s[d]), 4) for d in DIMENSION_IDS},
        ))

    coverable = [d for d in DIMENSION_IDS if bars[d] > 0]
    n_cover = sum((eligible[d] >= bars[d]) for d in coverable) if coverable else pd.Series(dtype=int)
    best_single = None
    if len(eligible) and coverable:
        label = n_cover.idxmax()
        best_single = dict(tile_id=str(dst.meta.loc[label, "tile_id"]),
                           covers=int(n_cover[label]))

    words = moon_values(moon)
    return dict(
        src_tile=dict(tile_id=str(moon.tile_id), lat=round(float(moon.lat), 3),
                      lon=round(float(moon.lon), 3)),
        polar=is_polar(moon),
        dimensions=[dict(id=d.id, label=d.label, note=d.note, moon=words[d.id],
                         threshold=round(bars[d.id], 4),
                         earth_best=round(float(eligible[d.id].max()), 4) if len(eligible) else None,
                         earth_best_only=bar_info[d.id][1],
                         covered_by=covered_by.get(d.id))
                    for d in DIMENSIONS],
        sites=sites,
        uncovered=[d for d in DIMENSION_IDS if d in uncovered],
        best_single_site=best_single,
        candidates=int(len(eligible)),
    )
