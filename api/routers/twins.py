"""GET /twins - the report card for one Moon/Earth or Mars/Earth pair.

This is the answer to "say where the analogy breaks down": every row is a
dimension, with a 0-1 match, or null when Earth has no equivalent at all.
"""
from __future__ import annotations

import logging

import pandas as pd
import requests
from fastapi import APIRouter, HTTPException, Query, Request

from analogatlas.analog import breakdown, earth_climate
from analogatlas.fieldtest import what_to_test

from ..indices import MODEL_SCORE_COLUMN, get_index, json_scalar, row_by_tile_id, row_dict
from ..schemas import Body, TwinsResponse

log = logging.getLogger("analogatlas.api")
router = APIRouter(tags=["twins"])


@router.get("/twins", response_model=TwinsResponse)
def get_twins(
    request: Request,
    src_tile_id: str = Query(..., description="a Moon or Mars tile_id"),
    earth_tile_id: str = Query(..., description="an Earth tile_id"),
    src_body: Body = Query("moon", description="'moon_polar' for the south pole (#26), "
                                               "'mars' for Mars"),
) -> TwinsResponse:
    if src_body == "earth":
        raise HTTPException(400, "src_body is the Moon or Mars tile's body, not 'earth'")
    moon = get_index(request, src_body)
    earth = get_index(request, "earth")
    i = row_by_tile_id(moon, src_tile_id)
    j = row_by_tile_id(earth, earth_tile_id)

    moon_row, earth_row = moon.meta.iloc[i], earth.meta.iloc[j].copy()
    # The report card's first row is the ML terrain-shape match, expressed as
    # this pair's percentile among all Earth tiles for the same Moon tile.
    visual = earth.shade @ moon.shade[i]
    earth_row["visual_cos_scaled"] = float((visual < visual[j]).mean())

    climate = None
    try:
        climate = earth_climate(round(float(earth_row.lat), 2), round(float(earth_row.lon), 2))
    except (requests.RequestException, KeyError, ValueError) as e:
        # NASA POWER being slow or down must not take the report card with it;
        # the climate rows are simply omitted (ARCHITECTURE.md §7).
        log.warning("NASA POWER lookup failed for %s: %s", earth_tile_id, e)

    rows = breakdown(moon_row, earth_row, climate)
    rows = rows.astype(object).where(pd.notna(rows), None)

    return TwinsResponse(
        moon=row_dict(moon, i),
        earth={**row_dict(earth, j),
               "visual_cos_scaled": float(earth_row.visual_cos_scaled)},
        climate=None if climate is None else {k: json_scalar(v) for k, v in climate.items()},
        breakdown=rows.to_dict("records"),
        field_tests=what_to_test(rows, body="mars" if src_body == "mars" else "moon"),
        model_score=json_scalar(earth_row.get(MODEL_SCORE_COLUMN[src_body])),
    )
