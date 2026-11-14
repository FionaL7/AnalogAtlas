"""Request and response models. The contract is ARCHITECTURE.md §4.3."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Body = Literal["moon", "moon_polar", "earth"]
Layer = Literal["img", "shade"]


class SearchRequest(BaseModel):
    body: Body
    query: str | None = Field(None, description="free-text terrain description")
    image_b64: str | None = Field(None, description="base64 image, with or without a data: prefix")
    k: int = Field(12, ge=1, le=200)
    w_shade: float = Field(0.6, ge=0.0, le=1.0,
                           description="mixes hillshade vs imagery similarity")

    @model_validator(mode="after")
    def exactly_one_query(self):
        if bool(self.query) == bool(self.image_b64):
            raise ValueError("provide exactly one of query or image_b64")
        return self


class SearchHit(BaseModel):
    tile_id: str
    lat: float
    lon: float
    score: float
    known_analog: str | None = None
    tile_url: str


class SearchResponse(BaseModel):
    results: list[SearchHit]


class AnalogsRequest(BaseModel):
    src_body: Body
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=360)
    k: int = Field(12, ge=1, le=200)
    w_phys: float = Field(0.3, ge=0.0, le=1.0,
                          description="weights physical closeness against visual similarity")
    new_only: bool = Field(False, description="drop tiles tagged as a known analog site")


class SrcTile(BaseModel):
    tile_id: str
    lat: float
    lon: float


class AnalogHit(BaseModel):
    tile_id: str
    lat: float
    lon: float
    score: float = Field(..., description="ranking value, NOT a 0-1 similarity")
    visual_cos_scaled: float = Field(..., description="0-1 percentile of visual similarity")
    physical: float
    known_analog: str | None = None
    model_score: float | None = Field(
        None, description="#29 analog model, 0-1 percentile among Earth tiles; null if not trained")
    tile_url: str


class AnalogsResponse(BaseModel):
    src_tile: SrcTile
    results: list[AnalogHit]


class BreakdownRow(BaseModel):
    dimension: str
    moon: Any
    earth: Any
    match: float | None = Field(None, description="0-1, or null when Earth has no equivalent")
    note: str = ""
    kind: Literal["compare", "no_equivalent", "earth_limit"] = Field(
        "compare", description="earth_limit rows are what Earth cannot reproduce; group by this")


class FieldTest(BaseModel):
    title: str
    risk: str
    detail: str
    based_on: list[str]
    strength: float


class AvoidNote(BaseModel):
    dimension: str
    reason: str


class FieldTests(BaseModel):
    """What to test at this Earth site (C6), from `analogatlas.fieldtest`."""
    tests: list[FieldTest]
    avoid: list[AvoidNote]


class TwinsResponse(BaseModel):
    moon: dict[str, Any]
    earth: dict[str, Any]
    climate: dict[str, Any] | None
    breakdown: list[BreakdownRow]
    field_tests: FieldTests | None = None
    model_score: float | None = None
