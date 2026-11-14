"""GET /tile/{body}/{layer}/{tile_id} - tile image passthrough.

Local-dev convenience only: it serves the files `scripts/01_tiles.py` already
downloaded into `data/tiles/`. In production the frontend points straight at
object storage and this route is never hit (ARCHITECTURE.md §4.3).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from analogatlas.tiles import tile_path

from ..schemas import Body, Layer

router = APIRouter(tags=["tiles"])

EXTENSIONS = (".jpg", ".jpeg", ".png")


def tile_url(request: Request, body: str, tile_id: str, layer: str = "img") -> str:
    return str(request.url_for("get_tile", body=body, layer=layer, tile_id=tile_id))


@router.get("/tile/{body}/{layer}/{tile_id}", name="get_tile",
            response_class=FileResponse,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}})
def get_tile(body: Body, layer: Layer, tile_id: str) -> FileResponse:
    """`tile_id` may carry its file extension or not; both resolve to the same tile."""
    for ext in EXTENSIONS:
        tile_id = tile_id.removesuffix(ext)
    path = tile_path(body, layer, tile_id)
    if not path.exists():
        raise HTTPException(404, f"no {layer} tile on disk for {tile_id!r}")
    return FileResponse(path)
