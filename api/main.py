"""AnalogAtlas API - a thin FastAPI layer over `analogatlas.analog`.

Only the things that need CLIP or a live NASA POWER call at request time live
here. The demo path is precomputed by `scripts/03_export.py` and served as
static JSON, so judging does not depend on this service being up
(ARCHITECTURE.md §1, §4.2).

Run it locally:

    uvicorn api.main:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from analogatlas import config as C

from .indices import load_all
from .routers import analogs, search, tile, twins

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("analogatlas.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Both indices are loaded once, up front: ~35 MB resident, and every
    # /search and /analogs is then pure NumPy with no disk or network.
    app.state.indices = load_all()
    yield
    app.state.indices = {}


def create_app() -> FastAPI:
    app = FastAPI(
        title="AnalogAtlas API",
        version="0.1.0",
        description="Search engine for planetary analogs. Contract: docs/ARCHITECTURE.md §4.3.",
        lifespan=lifespan,
    )
    # The frontend is served from a different origin (static host) than the API.
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["GET", "POST"], allow_headers=["*"])
    for router in (search.router, analogs.router, twins.router, tile.router):
        app.include_router(router)

    @app.get("/health", tags=["meta"])
    def health(request: Request) -> dict:
        """Which bodies this instance can actually serve, and how big they are."""
        idx = request.app.state.indices
        return {"status": "ok",
                "index_dir": str(C.INDEX),
                "bodies": {b: len(i.meta) for b, i in idx.items()}}

    return app


app = create_app()
