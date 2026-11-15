"""Lookalike traps (#30): Moon-Earth or Mars-Earth pairs that look alike but
break physically.

The pitch: this is what an image-only AI would recommend, and why it fails.

How:
1. For every lunar tile, take the Earth tiles whose terrain *looks* most alike:
   the top of the hillshade-embedding similarity, the same visual signal
   cross_body() uses.
2. Check each lookalike against physics: ice, plants, water, a wet climate,
   or very different slope/relief. Any hit makes it a trap, with the reason
   in plain words and the numbers behind it.
3. Record where three rankings put it:
   - visual_rank: image-only similarity (the trap)
   - physics_rank: where our search (cross_body) puts it. It weighs slope
     and relief and pushes ice, plants and water down (#33), so a trap should
     rank far lower here than on looks alone
   - model_score_pct: the #29 analog model (earth_scores.parquet), which knows
     ice, plants and climate. 1 = most like known Moon analogs

The environment checks are defined once in checks.py and shared with the
search. They need the Earth environment columns (earth_ee.environment);
without them, only the slope/relief checks run.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import checks as K
from .analog import BodyIndex, _closeness, cross_body_scores, is_mars, mars_ice_rich

TOP_N = 20          # lookalikes considered per lunar tile
W_PHYS = 0.3        # same default as cross_body / the API
SHAPE_MISMATCH = 0.35   # slope/relief closeness below this = "very different"


@dataclass(frozen=True)
class Breaker:
    id: str
    label: str
    environment: bool   # True: about what the ground *is*; False: about its shape


BREAKERS = {
    "ice": Breaker("ice", "Ice sheet, not rock", True),
    "vegetation": Breaker("vegetation", "Covered in plants", True),
    "water": Breaker("water", "Mostly lakes or wetland", True),
    "wet_climate": Breaker("wet_climate", "Wet climate", True),
    "slope": Breaker("slope", "Different steepness", False),
    "relief": Breaker("relief", "Different height range", False),
}


def _num(row: pd.Series, col: str) -> float | None:
    v = row.get(col)
    return None if v is None or pd.isna(v) else float(v)


def check(moon: pd.Series, earth: pd.Series) -> list[dict]:
    """Which physical checks this pair fails, each with a plain reason.

    `moon` is the source tile, on the Moon or Mars. For an ice-rich Mars tile
    an Earth ice tile is a real analog, so ice is not a trap there.
    """
    hits = []
    mars = is_mars(moon)
    where = "on Mars" if mars else "on the Moon"

    def hit(bid: str, reason: str):
        b = BREAKERS[bid]
        hits.append(dict(id=b.id, label=b.label, environment=b.environment, reason=reason))

    flags = K.env_flags(earth.to_frame().T).iloc[0]
    ice, veg, water = _num(earth, "ice_frac"), _num(earth, "veg_frac"), _num(earth, "water_frac")
    ndvi, aridity = _num(earth, "ndvi"), _num(earth, "aridity")
    if flags["ice"] and not mars_ice_rich(moon):
        hit("ice", f"{ice:.0%} permanent ice. Smooth because ice flows and snow fills the hollows; "
                   + ("this part of Mars is dry rock and dust" if mars
                      else "the Moon's plains are rock and dust"))
    if flags["vegetation"]:
        what = (f"{veg:.0%} forest, savanna or crops" if veg is not None and veg >= K.VEG_MIN
                else f"greenness {ndvi:.2f}")
        hit("vegetation", f"{what}. The shape matches, but the surface is soil and roots, not regolith")
    if flags["water"]:
        hit("water", f"{water:.0%} lakes or wetland")
    if flags["wet_climate"]:
        hit("wet_climate", f"Rain-to-evaporation ratio {aridity:.2f} (drylands are below 0.65): "
                           "rain and rivers shaped it; "
                           + ("Mars has had no rain for billions of years" if mars
                              else "the Moon has no liquid water"))
    s_m, s_e = _num(moon, "slope_med"), _num(earth, "slope_med")
    if s_m is not None and s_e is not None and float(_closeness(s_e, s_m, 1.0)) < SHAPE_MISMATCH:
        hit("slope", f"Median slope {s_m:.1f}° {where} vs {s_e:.1f}° on Earth")
    r_m, r_e = _num(moon, "relief_km"), _num(earth, "relief_km")
    if r_m is not None and r_e is not None and float(_closeness(r_e, r_m, 1.0)) < SHAPE_MISMATCH:
        hit("relief", f"Height range {r_m:.2f} km {where} vs {r_e:.2f} km on Earth")
    return hits


def traps_for_tile(src: BodyIndex, i: int, dst: BodyIndex, src_body: str,
                   top_n: int = TOP_N, w_phys: float = W_PHYS,
                   model_scores: dict[str, float] | None = None) -> list[dict]:
    """Traps among the top_n lookalikes of one source tile.

    `model_scores`: Earth tile_id -> #29 analog score for this body
    (`analog_score_moon` or `analog_score_mars`, 0-1), if available.
    """
    score, visual, _, _ = cross_body_scores(src, i, dst, w_phys)
    order = np.argsort(-visual)
    s_row = src.meta.iloc[i]
    out = []
    for vis_rank, j in enumerate(order[:top_n], start=1):
        e_row = dst.meta.iloc[j]
        hits = check(s_row, e_row)
        if not hits:
            continue
        out.append(dict(
            src_body=src_body, src_tile_id=str(s_row.tile_id),
            src_lat=round(float(s_row.lat), 3), src_lon=round(float(s_row.lon), 3),
            earth_tile_id=str(e_row.tile_id),
            earth_lat=round(float(e_row.lat), 3), earth_lon=round(float(e_row.lon), 3),
            visual_cos=round(float(visual[j]), 4),
            visual_pct=round(float((visual < visual[j]).mean()), 4),
            visual_rank=vis_rank,
            physics_rank=int((score > score[j]).sum()) + 1,
            model_score_pct=(None if not model_scores or str(e_row.tile_id) not in model_scores
                             else round(float(model_scores[str(e_row.tile_id)]), 4)),
            known_analog=None if pd.isna(e_row.get("known_analog")) else e_row.get("known_analog"),
            breakers=hits,
        ))
    return out


def find_traps(src: BodyIndex, dst: BodyIndex, src_body: str, top_n: int = TOP_N,
               limit: int = 40, w_phys: float = W_PHYS,
               model_scores: dict[str, float] | None = None) -> list[dict]:
    """The strongest traps across all source tiles: one per Earth tile and per
    lunar tile, ranked so the most convincing lookalikes with a hard physical
    reason (ice, plants, water) come first."""
    found, _ = scan(src, dst, src_body, top_n, w_phys, model_scores)
    return pick(found, limit)


def scan(src: BodyIndex, dst: BodyIndex, src_body: str, top_n: int = TOP_N,
         w_phys: float = W_PHYS, model_scores: dict[str, float] | None = None
         ) -> tuple[list[dict], dict]:
    """Every trap among every source tile's top_n lookalikes, plus the rate:
    what share of the image-only top picks fail a physics check, overall and
    per reason. That share is the headline number for the slides."""
    found = []
    for i in range(len(src.meta)):
        found += traps_for_tile(src, i, dst, src_body, top_n, w_phys, model_scores)
    considered = len(src.meta) * min(top_n, len(dst.meta))
    by_reason = {bid: sum(any(b["id"] == bid for b in t["breakers"]) for t in found) for bid in BREAKERS}
    stats = dict(src_body=src_body, lookalikes_checked=considered, traps=len(found),
                 trap_rate=round(len(found) / considered, 4) if considered else 0.0,
                 by_reason={k: v for k, v in by_reason.items() if v})
    return found, stats


def pick(found: list[dict], limit: int = 40) -> list[dict]:
    """Strongest traps, one per Earth tile and per lunar tile: the most
    convincing lookalikes with a hard reason (ice, plants, water) first."""
    found = sorted(found, key=lambda t: (-any(b["environment"] for b in t["breakers"]),
                                         -t["visual_cos"], -len(t["breakers"])))
    picked, seen_e, seen_s = [], set(), set()
    for t in found:
        if t["earth_tile_id"] in seen_e or t["src_tile_id"] in seen_s:
            continue
        picked.append(t)
        seen_e.add(t["earth_tile_id"])
        seen_s.add(t["src_tile_id"])
        if len(picked) >= limit:
            break
    return picked
