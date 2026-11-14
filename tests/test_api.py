"""The API contract in ARCHITECTURE.md §4.3, checked against a synthetic index."""
from __future__ import annotations

import base64
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from analogatlas import config as C

from .conftest import write_index


def test_health_reports_both_bodies(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body["bodies"]) == {"moon", "earth"}
    assert body["bodies"]["moon"] > 0


# ------------------------------------------------------------------ search --
def test_search_text_returns_k_hits_with_tile_urls(client):
    r = client.post("/search", json={"body": "moon", "query": "a large impact crater", "k": 5})
    assert r.status_code == 200
    hits = r.json()["results"]
    assert len(hits) == 5
    assert [h["tile_id"].startswith("moon_") for h in hits] == [True] * 5
    assert all(h["tile_url"].endswith(f"/tile/moon/img/{h['tile_id']}") for h in hits)
    assert [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True)


def test_search_image_accepts_a_data_url(client):
    buf = io.BytesIO()
    Image.new("L", (64, 64), 128).save(buf, format="PNG")
    payload = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    r = client.post("/search", json={"body": "moon", "image_b64": payload, "k": 3})
    assert r.status_code == 200
    assert len(r.json()["results"]) == 3


def test_search_tags_known_analogs_on_earth(client):
    hits = client.post("/search", json={"body": "earth", "query": "dry valley", "k": 36}).json()
    tagged = {h["known_analog"] for h in hits["results"] if h["known_analog"]}
    assert "McMurdo Dry Valleys, Antarctica" in tagged


@pytest.mark.parametrize("payload, status", [
    ({"body": "moon"}, 422),                                   # neither query nor image
    ({"body": "moon", "query": "x", "image_b64": "x"}, 422),    # both
    ({"body": "pluto", "query": "x"}, 422),                     # unknown body
    ({"body": "moon", "query": "x", "k": 0}, 422),              # k out of range
    ({"body": "moon", "query": "x", "w_shade": 1.5}, 422),      # weight out of range
])
def test_search_rejects_bad_requests(client, payload, status):
    assert client.post("/search", json=payload).status_code == status


def test_search_image_rejects_non_image_base64(client):
    r = client.post("/search", json={"body": "moon", "image_b64": base64.b64encode(b"nope").decode()})
    assert r.status_code == 400
    assert "detail" in r.json()


# ----------------------------------------------------------------- analogs --
def test_analogs_moon_to_earth(client, index_dir):
    moon = index_dir.meta["moon"].iloc[0]
    r = client.post("/analogs", json={"src_body": "moon", "lat": float(moon.lat),
                                      "lon": float(moon.lon), "k": 6})
    assert r.status_code == 200
    out = r.json()
    assert out["src_tile"]["tile_id"] == moon.tile_id
    assert len(out["results"]) == 6
    for hit in out["results"]:
        assert hit["tile_id"].startswith("earth_")
        assert 0.0 <= hit["visual_cos_scaled"] <= 1.0
        assert 0.0 <= hit["physical"] <= 1.0
        assert np.isfinite(hit["score"])


def test_analogs_works_in_both_directions(client, index_dir):
    earth = index_dir.meta["earth"].iloc[3]
    out = client.post("/analogs", json={"src_body": "earth", "lat": float(earth.lat),
                                        "lon": float(earth.lon), "k": 4}).json()
    assert out["src_tile"]["tile_id"] == earth.tile_id
    assert all(h["tile_id"].startswith("moon_") for h in out["results"])


def test_analogs_new_only_drops_known_sites(client, index_dir):
    moon = index_dir.meta["moon"].iloc[0]
    req = {"src_body": "moon", "lat": float(moon.lat), "lon": float(moon.lon), "k": 36}
    everything = client.post("/analogs", json=req).json()["results"]
    new_only = client.post("/analogs", json={**req, "new_only": True}).json()["results"]

    assert any(h["known_analog"] for h in everything)
    assert all(h["known_analog"] is None for h in new_only)
    assert len(new_only) < len(everything)


def test_analogs_normalises_eastward_longitudes(client, index_dir):
    """A site given as 0-360 must land on the same tile as its -180..180 form."""
    moon = index_dir.meta["moon"].iloc[1]
    base = {"src_body": "moon", "lat": float(moon.lat), "k": 3}
    west = client.post("/analogs", json={**base, "lon": float(moon.lon)}).json()
    east = client.post("/analogs", json={**base, "lon": float(moon.lon) % 360}).json()
    assert west["src_tile"] == east["src_tile"]


# ------------------------------------------------------------------- twins --
def test_twins_report_card(client, index_dir):
    moon_id = index_dir.meta["moon"].tile_id.iloc[0]
    earth_id = index_dir.meta["earth"].tile_id.iloc[0]   # McMurdo
    r = client.get("/twins", params={"src_tile_id": moon_id, "earth_tile_id": earth_id})
    assert r.status_code == 200
    out = r.json()

    assert out["moon"]["tile_id"] == moon_id
    assert out["earth"]["tile_id"] == earth_id
    assert out["climate"]["TS_MIN"] == -55.2
    assert 0.0 <= out["earth"]["visual_cos_scaled"] <= 1.0

    rows = {row["dimension"]: row for row in out["breakdown"]}
    assert rows["Median slope"]["match"] is not None
    # Earth's limits: these must come back as a hard 0, not a near-miss.
    assert rows["Atmosphere"]["match"] == 0.0
    assert rows["Gravity"]["match"] == 0.0
    # No Earth equivalent at all -> null, so the UI can say so instead of scoring it.
    assert rows["Surface rock cover"]["match"] is None
    for row in out["breakdown"]:
        assert row["match"] is None or 0.0 <= row["match"] <= 1.0


def test_twins_earths_limits_are_complete_and_explicit(client, index_dir):
    """Issue #20: the 'Earth cannot reproduce' group is fixed, complete, and
    marked by `kind`, not inferred from a score of 0."""
    from analogatlas.analog import EARTH_LIMITS

    out = client.get("/twins", params={
        "src_tile_id": index_dir.meta["moon"].tile_id.iloc[0],
        "earth_tile_id": index_dir.meta["earth"].tile_id.iloc[0]}).json()
    rows = {row["dimension"]: row for row in out["breakdown"]}

    limits = [r for r in out["breakdown"] if r["kind"] == "earth_limit"]
    assert [r["dimension"] for r in limits] == [lim["dimension"] for lim in EARTH_LIMITS]
    assert {"Atmosphere", "Gravity", "Radiation", "Magnetic field",
            "Day/night cycle", "Regolith dust"} <= set(rows)
    assert all(r["match"] == 0.0 for r in limits)
    assert rows["Surface rock cover"]["kind"] == "no_equivalent"
    assert rows["Median slope"]["kind"] == "compare"

    assert {r["kind"] for r in out["breakdown"]} <= {"compare", "no_equivalent", "earth_limit"}

    # Lunar temperatures are modelled and must say so (ARCHITECTURE.md §6).
    for dim in ("Surface temperature swing", "Coldest surface"):
        assert "not measured" in rows[dim]["note"]


def test_twins_survives_nasa_power_being_down(client, index_dir, monkeypatch):
    import requests

    from api.routers import twins as twins_router
    def boom(lat, lon):
        raise requests.ConnectionError("POWER unreachable")
    monkeypatch.setattr(twins_router, "earth_climate", boom)

    out = client.get("/twins", params={
        "src_tile_id": index_dir.meta["moon"].tile_id.iloc[0],
        "earth_tile_id": index_dir.meta["earth"].tile_id.iloc[0]}).json()
    assert out["climate"] is None
    dims = {row["dimension"] for row in out["breakdown"]}
    assert "Median slope" in dims and "Dryness" not in dims


@pytest.mark.parametrize("params", [
    {"src_tile_id": "moon_6_0_0", "earth_tile_id": "earth_+99.00_+99.00"},
    {"src_tile_id": "nope", "earth_tile_id": "earth_-77.50_+162.00"},
])
def test_twins_unknown_tile_id_is_404(client, params):
    r = client.get("/twins", params=params)
    assert r.status_code == 404
    assert "detail" in r.json()


# ------------------------------------------------------------------- tiles --
def test_tile_passthrough_with_and_without_extension(client, index_dir):
    tile_id = index_dir.meta["moon"].tile_id.iloc[0]
    path = index_dir.tiles / "moon" / "img" / f"{tile_id}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (8, 8), 42).save(path)

    for suffix in ("", ".jpg"):
        r = client.get(f"/tile/moon/img/{tile_id}{suffix}")
        assert r.status_code == 200, suffix
        assert r.headers["content-type"] == "image/jpeg"


def test_tile_missing_file_is_404(client, index_dir):
    r = client.get(f"/tile/moon/shade/{index_dir.meta['moon'].tile_id.iloc[0]}")
    assert r.status_code == 404


def test_unknown_layer_is_422(client, index_dir):
    assert client.get("/tile/moon/elevation/moon_6_0_0").status_code == 422


# ------------------------------------------------------------------ safety --
def test_missing_body_index_is_503_not_a_crash(tmp_path, monkeypatch, stub_clip):
    """A Moon-only machine must still serve Moon search."""
    d = tmp_path / "index"
    write_index(d, bodies=("moon",))
    monkeypatch.setattr(C, "INDEX", d)
    from api import main as api_main

    with TestClient(api_main.create_app()) as c:
        assert c.get("/health").json()["bodies"] == {"moon": 48}
        assert c.post("/search", json={"body": "moon", "query": "crater"}).status_code == 200
        r = c.post("/search", json={"body": "earth", "query": "desert"})
        assert r.status_code == 503
        assert "earth" in r.json()["detail"]


def test_row_order_mismatch_is_refused_at_startup(tmp_path, monkeypatch, stub_clip):
    """The hardest bug to spot (ARCHITECTURE.md §7): embeddings out of step with
    the parquet produce silently wrong analogs. Refuse to serve such an index."""
    d = tmp_path / "index"
    write_index(d, bodies=("moon",))
    truncated = np.load(d / "moon_shade.npy")[:-5]
    np.save(d / "moon_shade.npy", truncated)
    monkeypatch.setattr(C, "INDEX", d)
    from api import main as api_main

    with pytest.raises(RuntimeError, match="rows differ"):
        with TestClient(api_main.create_app()):
            pass
