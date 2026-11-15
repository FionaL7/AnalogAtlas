"""POST /analogs - cross-body search: Earth analogs for a Moon or Mars tile,
or the reverse (Earth -> Moon, or Earth -> Mars with dst_body="mars")."""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Request

from analogatlas.analog import cross_body

from ..indices import MODEL_SCORE_COLUMN, get_index, json_scalar, other_body
from ..schemas import AnalogHit, AnalogsRequest, AnalogsResponse, SrcTile
from .tile import tile_url

router = APIRouter(tags=["analogs"])


@router.post("/analogs", response_model=AnalogsResponse)
def post_analogs(req: AnalogsRequest, request: Request) -> AnalogsResponse:
    dst_body = other_body(req.src_body, req.dst_body)
    src = get_index(request, req.src_body)
    dst = get_index(request, dst_body)

    lon = ((req.lon + 180) % 360) - 180
    i = src.nearest_tile(req.lat, lon)
    src_row = src.meta.iloc[i]

    mask = None
    if req.new_only:
        # Lead with tiles that are *not* a known analog site - the "new,
        # unrecognized analogs" the challenge asks for.
        mask = dst.meta.known_analog.isna().values
    hits = cross_body(src, i, dst, k=req.k, mask=mask, w_phys=req.w_phys)
    hits = hits[np.isfinite(hits.score.values)]   # masked-out rows score -inf
    # the #29 score for this source's target (Moon or Mars); none for non-Earth hits
    score_col = MODEL_SCORE_COLUMN.get(req.src_body)

    return AnalogsResponse(
        src_tile=SrcTile(tile_id=src_row.tile_id, lat=float(src_row.lat), lon=float(src_row.lon)),
        results=[
            AnalogHit(tile_id=r.tile_id, lat=float(r.lat), lon=float(r.lon),
                      score=float(r.score), visual_cos_scaled=float(r.visual_cos_scaled),
                      physical=float(r.physical), known_analog=json_scalar(r.known_analog),
                      model_score=json_scalar(getattr(r, score_col, None)) if score_col else None,
                      tile_url=tile_url(request, dst_body, r.tile_id))
            for r in hits.itertuples()
        ])
