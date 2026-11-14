"""POST /search - rank tiles within one body by text or by an uploaded image.

This is the half of the app that cannot be precomputed: it needs CLIP at request
time, which is why the API exists at all.
"""
from __future__ import annotations

import base64
import binascii
import io

import numpy as np
from fastapi import APIRouter, HTTPException, Request

from analogatlas.analog import search

from ..indices import get_index, json_scalar
from ..schemas import SearchHit, SearchRequest, SearchResponse
from .tile import tile_url

router = APIRouter(tags=["search"])


def _text_vector(query: str) -> np.ndarray:
    from analogatlas.embed import embed_text  # imports torch; keep it off startup
    return embed_text(query)


def _image_vector(image_b64: str) -> np.ndarray:
    from PIL import Image, UnidentifiedImageError

    from analogatlas.embed import embed_images
    payload = image_b64.split(",", 1)[-1] if image_b64.startswith("data:") else image_b64
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "image_b64 is not valid base64")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "image_b64 does not decode to an image")
    return embed_images([img])[0]


@router.post("/search", response_model=SearchResponse)
def post_search(req: SearchRequest, request: Request) -> SearchResponse:
    idx = get_index(request, req.body)
    vec = _text_vector(req.query) if req.query else _image_vector(req.image_b64)
    hits = search(idx, vec, k=req.k, w_shade=req.w_shade)
    return SearchResponse(results=[
        SearchHit(tile_id=r.tile_id, lat=float(r.lat), lon=float(r.lon),
                  score=float(r.score), known_analog=json_scalar(r.known_analog),
                  tile_url=tile_url(request, req.body, r.tile_id))
        for r in hits.itertuples()
    ])
