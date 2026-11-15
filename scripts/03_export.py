"""Step 3: precompute the demo path as static JSON.

    python scripts/03_export.py                  # -> web/public/data/
    python scripts/03_export.py --no-climate     # skip the NASA POWER calls
    python scripts/03_export.py --out /tmp/data  # somewhere else
    python scripts/03_export.py --geocode        # also fill missing Earth place names

Everything the demo opens is written here, so judging never depends on the API
being up (ARCHITECTURE.md §1, §4.2). The API still serves free-text and image
search, which need CLIP at request time and cannot be precomputed.

Reads data/index/ and writes, under --out:

    sites.json                     targets and known Earth analogs
    dimensions.json                the report card's dimensions
    tiles/{body}.json              per-tile geometry + features for the map (moon,
                                   moon_polar, mars and earth, where the index exists)
    analogs/{site_id}.json         top-k Earth analogs per site (or Moon, reversed)
    twins/{site}__{tile}.json      report cards, climate baked in
    validation.json                copied from data/index/ if #16 has produced it
    traps.json                     lookalike traps (#30)
    candidates.json                the #29 model's top new candidates, per target, with
                                   place names from analogatlas/place_names.json
    radar.json                     Mini-RF CPR per lunar site (#17), keyed by site id
    portfolio/{site_id}.json       fewest Earth sites covering every dimension (#31)
    close_study.json               the #19 close-study pairs, plus close_study/*.jpg
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import (  # noqa: E402
    analog, config as C, fieldtest, places, portfolio, tiles, traps, verdict,
)
from analogatlas.sites import (  # noqa: E402
    EARTH_PRESETS, KNOWN_EARTH_ANALOGS, MARS_SITE_BLURBS, MARS_SITES, MOON_BASE_REGIONS, MOON_SITES,
)
from api.indices import annotate_known  # noqa: E402  (shared so the export and API agree)

TILE_COLUMNS = ["tile_id", "lat", "lon", "lat_min", "lat_max", "lon_min", "lon_max",
                "slope_med", "relief_km", "elev_km"]
# The polar map pane draws in polar stereographic metres, not lat/lon.
POLAR_TILE_COLUMNS = ["x_m", "y_m", "size_m", "psr_frac", "avg_illum", "illum_max",
                      "earth_vis"]
# What the Mars field guide shows (docs/MARS-PLAN.md contract).
MARS_TILE_COLUMNS = ["thermal_inertia", "albedo", "dust_index", "weh_pct", "hydrous_count"]
# The #29 model's score column for each source body's target.
MODEL_SCORE_COLUMN = {"moon": "analog_score_moon", "moon_polar": "analog_score_moon",
                      "mars": "analog_score_mars"}
# Earth hits per site that get a place name: the app lists 12, new-first or new-only.
NAMED_HITS = 12
# Set by --geocode: look up names missing from analogatlas/place_names.json.
GEOCODE = False


def name_places(points) -> None:
    """With --geocode, fill the place-name cache for these Earth points first."""
    if GEOCODE:
        places.fill([(float(la), float(lo)) for la, lo in points])


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower())
    return s.strip("-")


def write_json(path: Path, payload) -> int:
    """Write compact JSON and return the byte size."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    path.write_text(text)
    return len(text)


def clean(value, digits: int | None = None):
    """NumPy/pandas scalar -> JSON. NaN and infinity become null, not garbage."""
    if value is None:
        return None
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        if not math.isfinite(f):
            return None
        return round(f, digits) if digits is not None else f
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if pd.isna(value):
        return None
    return str(value)


# --------------------------------------------------------------- sites ------
def moon_trek_tile_url(lat: float, lon: float) -> str:
    """The Trek WMTS tile covering a point, at the grid's zoom (config.MOON_ZOOM)."""
    z, d = C.MOON_ZOOM, C.MOON_TILE_DEG
    y = int((90 - lat) // d)
    x = int((lon + 180) // d)
    return C.MOON_LAYERS["img"].format(z=z, y=y, x=x)


def moon_polar_trek_tile_url(lat: float, lon: float) -> str:
    """The Trek Moon/SP tile covering a point, at the polar grid's zoom."""
    x_m, y_m = tiles.sp_forward(lat, lon)
    tile_m = C.MOON_SP_EXTENT_M / 2 ** C.MOON_SP_ZOOM
    ox, oy = C.MOON_SP_ORIGIN_M
    return C.MOON_SP_LAYERS["shade"].format(
        z=C.MOON_SP_ZOOM, y=int((oy - float(y_m)) // tile_m), x=int((float(x_m) - ox) // tile_m))


def build_sites(moon_in_index, polar_in_index, mars_in_index=lambda lat: False) -> list[dict]:
    """Every target and known analog, with ids the frontend routes on.

    Moon base regions are all poleward of 80°S, so they belong to the
    `moon_polar` index, not `moon` -- the equirectangular grid cannot
    represent them at all (#26). If the polar index is absent they are still
    exported, with `in_index: false`, because without that flag
    `nearest_tile` would quietly clamp to the index edge and we would publish
    analogs for a place 25° away from the one named.
    """
    out: list[dict] = []
    for name, (lat, lon) in MOON_BASE_REGIONS.items():
        out.append(dict(id=slug(name), body="moon_polar", name=name, lat=lat, lon=lon,
                        is_base_region=True, in_index=bool(polar_in_index(lat)),
                        tile_url=moon_polar_trek_tile_url(lat, lon),
                        blurb="Artemis candidate landing region."))
    for name, (lat, lon) in MOON_SITES.items():
        out.append(dict(id=slug(name), body="moon", name=name, lat=lat, lon=lon,
                        is_base_region=False, in_index=bool(moon_in_index(lat)),
                        tile_url=moon_trek_tile_url(lat, lon)))
    for name, (lat, lon) in MARS_SITES.items():
        # Without a Mars index the sites still export, with in_index false, so
        # the app lists them and says plainly that they have no analogs yet.
        out.append(dict(id=slug(name), body="mars", name=name, lat=lat, lon=lon,
                        is_base_region=False, in_index=bool(mars_in_index(lat)),
                        blurb=MARS_SITE_BLURBS.get(name)))
    for name, (lat, lon) in EARTH_PRESETS.items():
        out.append(dict(id=slug(name), body="earth", name=name, lat=lat, lon=lon,
                        is_base_region=False, in_index=True))
    for name, (lat, lon) in KNOWN_EARTH_ANALOGS.items():
        out.append(dict(id=slug(name), body="earth", name=name, lat=lat, lon=lon,
                        is_base_region=False, in_index=True, is_known_analog=True))
    # A name can be both an Earth preset and a known analog; first wins.
    seen, unique = set(), []
    for site in out:
        if site["id"] not in seen:
            seen.add(site["id"])
            unique.append(site)
    return unique


# ---------------------------------------------------------- dimensions ------
def build_dimensions(moon: analog.BodyIndex, earth: analog.BodyIndex,
                     climate: dict | None, polar: analog.BodyIndex | None = None,
                     mars: analog.BodyIndex | None = None) -> list[dict]:
    """Derived from what `analog.breakdown()` actually returns, not hand-listed,
    so rows added there (#20, #26, #44) appear here without a second list to
    maintain. `bodies` says which worlds a row appears for: a dimension such as
    Atmosphere is on both, with different values."""
    earth_row = earth.meta.iloc[0].copy()
    earth_row["visual_cos_scaled"] = 0.5
    rows = analog.breakdown(moon.meta.iloc[0], earth_row, climate).assign(world="moon")
    if polar is not None:
        # the polar-only dimensions (illumination, permanent shadow, comms)
        # exist only for a moon_polar row, so collect them from one too
        polar_rows = analog.breakdown(polar.meta.iloc[0], earth_row, climate).assign(world="moon")
        rows = pd.concat([rows, polar_rows])
    if mars is not None:
        # Some Mars rows depend on the tile (ground ice, minerals), so take
        # them from a few tiles that between them show every row: one
        # ice-rich, one not, and one with mineral detections if any has them.
        m = mars.meta
        picks = [m.index[0]]
        ice = m.lat.abs() >= analog.MARS_ICE_LAT
        picks += [m.index[ice.to_numpy()][0]] if ice.any() else []
        picks += [m.index[(~ice).to_numpy()][0]] if (~ice).any() else []
        if "hydrous_count" in m and (m.hydrous_count > 0).any():
            picks.append(m.index[(m.hydrous_count > 0).to_numpy()][0])
        rows = pd.concat([rows] + [analog.breakdown(m.loc[k], earth_row, climate).assign(world="mars")
                                   for k in dict.fromkeys(picks)])
    worlds = rows.groupby("dimension", sort=False).world.agg(lambda w: sorted(set(w)))
    rows = rows.drop_duplicates(subset="dimension")
    out = []
    for row in rows.itertuples():
        out.append(dict(
            id=slug(row.dimension), label=row.dimension, note=row.note,
            bodies=worlds[row.dimension],
            # breakdown() marks each row's kind (#20); group on it, never on
            # match == 0, which a real comparison can also score.
            kind=row.kind,
            earth_cannot_reproduce=row.kind == "earth_limit",
            no_earth_equivalent=row.kind == "no_equivalent",
        ))
    return out


# ------------------------------------------------------------- exports ------
@lru_cache(maxsize=1)
def verdict_prose() -> dict[str, dict]:
    """{twin stem: {text, model}} from scripts/07_verdicts.py (#51); {} until it runs."""
    path = C.INDEX / "verdicts.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_model_scores(column: str = "analog_score_moon") -> dict[str, float] | None:
    """Earth tile_id -> #29 model score (0-1 percentile, 1 = most like the
    known Moon analogs). None until scripts/04_train.py has run."""
    path = C.INDEX / "earth_scores.parquet"
    if not path.exists():
        return None
    sc = pd.read_parquet(path)
    if column not in sc:
        return None
    return dict(zip(sc.tile_id.astype(str), sc[column].astype(float)))


def export_tiles(idx: analog.BodyIndex, body: str, out: Path) -> int:
    extra = {"moon_polar": POLAR_TILE_COLUMNS, "mars": MARS_TILE_COLUMNS}.get(body, [])
    wanted = TILE_COLUMNS + extra
    cols = [c for c in wanted if c in idx.meta.columns]
    rows = []
    for row in idx.meta[cols + (["known_analog"] if body == "earth" else [])].itertuples(index=False):
        d = row._asdict()
        tile = dict(
            tile_id=d["tile_id"],
            lat=clean(d["lat"], 3), lon=clean(d["lon"], 3),
            bbox=[clean(d.get("lon_min"), 3), clean(d.get("lat_min"), 3),
                  clean(d.get("lon_max"), 3), clean(d.get("lat_max"), 3)],
            slope_med=clean(d.get("slope_med"), 2),
            relief_km=clean(d.get("relief_km"), 3),
        )
        if body == "earth":
            tile["known_analog"] = clean(d.get("known_analog"))
        if body == "moon_polar":
            # the polar pane positions tiles in metres from the pole; a
            # lat/lon bbox is meaningless for the cells containing it
            tile["xy"] = [clean(d.get("x_m"), 1), clean(d.get("y_m"), 1),
                          clean(d.get("size_m"), 1)]
            for c in ("psr_frac", "avg_illum", "illum_max", "earth_vis"):
                tile[c] = clean(d.get(c), 4)
        if body == "mars":
            for c in MARS_TILE_COLUMNS:
                tile[c] = clean(d.get(c), 4)
        rows.append(tile)
    return write_json(out / "tiles" / f"{body}.json", rows)


def export_analogs(site: dict, src: analog.BodyIndex, dst: analog.BodyIndex,
                   k: int, out: Path,
                   model_scores: dict[str, float] | None = None) -> list[dict] | None:
    """Top-k cross-body analogs for one site. None when the site is off-index."""
    if not site["in_index"]:
        return None
    i = src.nearest_tile(site["lat"], site["lon"])
    hits = analog.cross_body(src, i, dst, k=k)
    hits = hits[np.isfinite(hits.score.values)]
    on_earth = site["body"] != "earth"
    if on_earth:
        known = hits.known_analog.notna() if "known_analog" in hits else np.zeros(len(hits), bool)
        shown = pd.concat([hits.head(NAMED_HITS), hits[~known].head(NAMED_HITS)])
        name_places(zip(shown.lat, shown.lon))
    results = [dict(
        tile_id=r.tile_id, lat=clean(r.lat, 3), lon=clean(r.lon, 3),
        score=clean(r.score, 4),
        visual_cos_scaled=clean(r.visual_cos_scaled, 4),
        physical=clean(r.physical, 4),
        known_analog=clean(getattr(r, "known_analog", None)),
        model_score=(clean(model_scores.get(str(r.tile_id)), 4) if model_scores else None),
        place=places.name(r.lat, r.lon) if on_earth else None,
    ) for r in hits.itertuples()]
    src_row = src.meta.iloc[i]
    write_json(out / "analogs" / f"{site['id']}.json", dict(
        site_id=site["id"],
        src_tile=dict(tile_id=src_row.tile_id, lat=clean(src_row.lat, 3),
                      lon=clean(src_row.lon, 3)),
        results=results,
    ))
    return results


def export_twins(site: dict, src: analog.BodyIndex, dst: analog.BodyIndex,
                 results: list[dict], pairs: int, out: Path,
                 with_climate: bool) -> list[str]:
    """Report cards for the pairs the demo opens, climate baked in so judging
    needs no NASA POWER call. Leads with candidates that are not known sites."""
    if site["body"] == "earth":
        return []   # breakdown() is Moon/Mars-vs-Earth; reverse pairs are not report cards
    ranked = sorted(results, key=lambda r: r["known_analog"] is not None)[:pairs]
    i = src.nearest_tile(site["lat"], site["lon"])
    moon_row = src.meta.iloc[i]
    visual = dst.shade @ src.shade[i]
    written = []
    for hit in ranked:
        j = int(np.flatnonzero(dst.meta.tile_id.values == hit["tile_id"])[0])
        earth_row = dst.meta.iloc[j].copy()
        earth_row["visual_cos_scaled"] = float((visual < visual[j]).mean())

        climate = None
        if with_climate:
            try:
                climate = analog.earth_climate(round(float(earth_row.lat), 2),
                                               round(float(earth_row.lon), 2))
            except (requests.RequestException, KeyError, ValueError) as e:
                print(f"  ! NASA POWER failed for {hit['tile_id']}: {e}")

        rows = analog.breakdown(moon_row, earth_row, climate)
        rows = rows.astype(object).where(pd.notna(rows), None)
        tests = fieldtest.what_to_test(rows, body="mars" if site["body"] == "mars" else "moon")
        path = out / "twins" / f"{site['id']}__{hit['tile_id']}.json"
        v = verdict.verdict(rows, tests)
        prose = verdict_prose().get(path.stem)
        if v and prose:
            v["prose"] = prose   # reviewed LLM text from scripts/07_verdicts.py (#51)
        write_json(path, dict(
            site_id=site["id"],
            # the source tile, Moon or Mars; it keeps the `moon` key for the
            # report-card contract, and `body` says which world it is
            moon={"body": site["body"],
                  **{c: clean(moon_row[c], 4) for c in moon_row.index if c not in ("z", "y", "x")}},
            earth={**{c: clean(earth_row[c], 4) for c in earth_row.index},
                   "visual_cos_scaled": clean(earth_row.visual_cos_scaled, 4),
                   "place": places.name(float(earth_row.lat), float(earth_row.lon))},
            climate=None if climate is None else {k: clean(v, 3) for k, v in climate.items()},
            breakdown=[dict(dimension=r.dimension, id=slug(r.dimension),
                            moon=clean(r.moon), earth=clean(r.earth),
                            match=clean(r.match, 4), note=r.note, kind=r.kind,
                            basis=getattr(r, "basis", None))
                       for r in rows.itertuples()],
            field_tests=tests,
            verdict=v,
            model_score=hit.get("model_score"),
        ))
        written.append(path.name)
    return written


def export_traps(sources: list[tuple[str, analog.BodyIndex]], earth: analog.BodyIndex,
                 sites: list[dict], by_body: dict, out: Path) -> int:
    """traps.json (#30): lookalikes an image-only AI would pick that fail physics.

    {stats: [...per Moon or Mars body], traps: [strongest, one per tile], by_site: {...}}
    Each trap's model score is the #29 score for its own body's target.
    """
    scores = {body: load_model_scores(MODEL_SCORE_COLUMN[body]) for body, _ in sources}
    if all(v is None for v in scores.values()):
        print("  - no data/index/earth_scores.parquet (#29), traps carry no model score")

    found, stats = [], []
    for body, idx in sources:
        f, s = traps.scan(idx, earth, body, model_scores=scores[body])
        found += f
        stats.append(s)
        print(f"  traps: {s['traps']}/{s['lookalikes_checked']} {body} lookalikes fail a physics "
              f"check ({s['trap_rate']:.0%}); by reason {s['by_reason']}")

    by_site = {}
    for site in sites:
        src = by_body.get(site["body"])
        if site.get("is_known_analog") or not site.get("in_index") or src is None or site["body"] == "earth":
            continue
        i = src.nearest_tile(site["lat"], site["lon"])
        by_site[site["id"]] = traps.traps_for_tile(src, i, earth, site["body"],
                                                   model_scores=scores.get(site["body"]))

    return write_json(out / "traps.json", dict(stats=stats, traps=traps.pick(found), by_site=by_site))


def export_portfolios(sites: list[dict], earth: analog.BodyIndex, by_body: dict,
                      out: Path) -> list[str]:
    """portfolio/{site_id}.json (#31): the fewest Earth sites that together
    cover every dimension of one Moon or Mars target."""
    written = []
    for site in sites:
        src = by_body.get(site["body"])
        if site["body"] == "earth" or not site.get("in_index") or src is None:
            continue
        i = src.nearest_tile(site["lat"], site["lon"])
        payload = portfolio.build_portfolio(src, i, earth)
        write_json(out / "portfolio" / f"{site['id']}.json",
                   dict(site_id=site["id"], site_name=site["name"], body=site["body"], **payload))
        written.append(site["id"])
    print(f"  portfolios: {len(written)} Moon and Mars targets")
    return written


def export_candidates(out: Path) -> int | None:
    """candidates.json: {target: [...]} from data/index/candidates_{target}.json (#29)."""
    payload = {}
    for target in ("moon", "mars", "all"):
        path = C.INDEX / f"candidates_{target}.json"
        if path.exists():
            payload[target] = json.loads(path.read_text())
    name_places((c["lat"], c["lon"]) for rows in payload.values() for c in rows)
    for rows in payload.values():
        for c in rows:
            c["place"] = places.name(c["lat"], c["lon"])
    if not payload:
        print("  - no data/index/candidates_*.json yet (#29), skipping candidates.json")
        return None
    return write_json(out / "candidates.json", payload)


def export_radar(sites: list[dict], out: Path) -> int | None:
    """radar.json: Mini-RF CPR per lunar site (#17), keyed by the site ids the
    app routes on. Names come from sites.py, so map them through slug()."""
    path = C.INDEX / "moon_site_cpr.json"
    if not path.exists():
        print("  - no data/index/moon_site_cpr.json yet (#17), skipping radar.json")
        return None
    raw = json.loads(path.read_text())
    ids = {s["id"] for s in sites}
    payload = {slug(name): {k: clean(v, 4) if isinstance(v, float) else v for k, v in row.items()}
               for name, row in raw.items() if slug(name) in ids}
    return write_json(out / "radar.json", payload)


def export_close_study(sites: list[dict], by_body: dict, earth: analog.BodyIndex,
                       results_by_site: dict[str, list[dict]], out: Path,
                       with_climate: bool) -> int | None:
    """close_study.json + one full report card per #19 pair.

    Reads data/index/close_study.json (scripts/04_radar.py close-study). Each
    pair's twins/{site}__{tile}.json is (re)written with a `close_study` block:
    radar on both bodies, 30 m slope, a picture, and why the pair was picked.
    The card is written even when the pair is outside the site's top --pairs.
    """
    path = C.INDEX / "close_study.json"
    if not path.exists():
        print("  - no data/index/close_study.json yet (#19), skipping close_study.json")
        return None
    pairs = json.loads(path.read_text())
    by_name = {s["name"]: s for s in sites}
    index = []
    for pair in pairs:
        site = by_name[pair["site"]]
        results = results_by_site.get(site["id"]) or []
        new = [r for r in results if r["known_analog"] is None]
        rank = next((k + 1 for k, r in enumerate(new) if r["tile_id"] == pair["earth_tile_id"]), None)
        hit = next((r for r in results if r["tile_id"] == pair["earth_tile_id"]),
                   dict(tile_id=pair["earth_tile_id"], known_analog=None, model_score=None))
        if hit["known_analog"] is not None:
            print(f"  ! {pair['earth_tile_id']} is now near a known analog; check the #19 pick")
        name, = export_twins(site, by_body[site["body"]], earth, [hit], 1, out, with_climate)

        pic = pair.get("picture")
        if pic:
            src_pic = C.INDEX / "close_study" / pic["file"]
            if src_pic.exists():
                (out / "close_study").mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src_pic, out / "close_study" / pic["file"])
                pic = dict(pic, url=f"/data/close_study/{pic['file']}")
            else:
                pic = None
        block = dict(
            id=pair["id"], headline=pair["headline"], earth_name=pair["earth_name"],
            why_picked=pair["why_picked"], rank_among_new=rank,
            nearest_known=nearest_known(pair["earth_lat"], pair["earth_lon"]),
            box=pair["box"], radar=pair["radar"], earth_slope_30m=pair["earth_slope_30m"],
            picture=pic,
        )
        card_path = out / "twins" / name
        card = json.loads(card_path.read_text())
        card["close_study"] = block
        write_json(card_path, card)
        index.append(dict(block, site_id=site["id"], site_name=site["name"], site_body=site["body"],
                          earth_tile_id=pair["earth_tile_id"], earth_lat=clean(pair["earth_lat"], 3),
                          earth_lon=clean(pair["earth_lon"], 3), twin=f"/data/twins/{name}",
                          model_score=hit.get("model_score")))
    print(f"  close study: {len(index)} pairs")
    return write_json(out / "close_study.json", index)


def nearest_known(lat: float, lon: float) -> dict:
    """The closest well-studied analog site and its distance: the evidence for "new"."""
    name, (la, lo) = min(KNOWN_EARTH_ANALOGS.items(),
                         key=lambda kv: analog.haversine_deg(lat, lon, *kv[1]))
    return dict(name=name, km=round(float(analog.haversine_deg(lat, lon, la, lo)) * C.EARTH_KM_PER_DEG))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=C.ROOT / "web" / "public" / "data")
    ap.add_argument("--k", type=int, default=200, help="analogs per site (default 200)")
    ap.add_argument("--pairs", type=int, default=3, help="report cards per site (default 3)")
    ap.add_argument("--no-climate", action="store_true",
                    help="skip NASA POWER; twins get no climate rows")
    ap.add_argument("--geocode", action="store_true",
                    help="look up Earth place names missing from analogatlas/place_names.json "
                         "(OpenStreetMap Nominatim, 1 request/s); without it the cache is only read")
    args = ap.parse_args()
    global GEOCODE
    GEOCODE = args.geocode

    missing = [b for b in ("moon", "earth") if not (C.INDEX / f"{b}_meta.parquet").exists()]
    if missing:
        sys.exit(f"No index for {', '.join(missing)} in {C.INDEX}. "
                 "Build it first (scripts/01_tiles.py, scripts/02_features.py).")

    # load_index checks row counts and the tile_id order stamp (#12)
    try:
        moon, earth = analog.load_index("moon"), analog.load_index("earth")
        # The south pole is optional: without it the Artemis regions export
        # with in_index=false and no analogs, which is the pre-#26 behaviour.
        polar = (analog.load_index("moon_polar")
                 if (C.INDEX / "moon_polar_meta.parquet").exists() else None)
        # Mars is optional too (docs/MARS-PLAN.md): without it the Mars sites
        # export with in_index=false and no analogs.
        mars = (analog.load_index("mars")
                if (C.INDEX / "mars_meta.parquet").exists() else None)
    except analog.IndexMismatchError as e:
        sys.exit(f"index is inconsistent: {e} - do not export it")
    earth.meta = annotate_known(earth.meta)
    print(f"moon: {len(moon.meta)} tiles, earth: {len(earth.meta)} tiles, "
          f"moon_polar: {len(polar.meta) if polar else 0} tiles, "
          f"mars: {len(mars.meta) if mars else 0} tiles")

    out: Path = args.out
    in_index = lambda lat: abs(lat) <= C.MOON_MAX_ABS_LAT                       # noqa: E731
    polar_in_index = lambda lat: polar is not None and lat <= C.MOON_POLAR_MAX_LAT  # noqa: E731
    mars_in_index = lambda lat: mars is not None and abs(lat) <= 60.0           # noqa: E731
    sites = build_sites(in_index, polar_in_index, mars_in_index)
    write_json(out / "sites.json", sites)

    sample_climate = None
    if not args.no_climate:
        try:
            sample_climate = analog.earth_climate(-24.08, -69.92)   # Atacama
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"! NASA POWER unavailable, exporting without climate rows: {e}")
    write_json(out / "dimensions.json", build_dimensions(moon, earth, sample_climate, polar, mars))

    bodies = ([("moon", moon), ("earth", earth)] + ([("moon_polar", polar)] if polar else [])
              + ([("mars", mars)] if mars else []))
    for body, idx in bodies:
        export_tiles(idx, body, out)

    by_body = {"moon": moon, "moon_polar": polar, "mars": mars, "earth": earth}
    model_scores = {body: load_model_scores(col) for body, col in MODEL_SCORE_COLUMN.items()}
    cards = 0
    off_index = []
    results_by_site: dict[str, list[dict]] = {}
    for site in sites:
        if site.get("is_known_analog"):
            continue        # reference points on the map, not search targets
        src = by_body[site["body"]]
        dst = moon if site["body"] == "earth" else earth
        if src is None:
            off_index.append(site)
            continue
        results = export_analogs(site, src, dst, args.k, out,
                                 model_scores=model_scores.get(site["body"]) if dst is earth else None)
        if results is None:
            off_index.append(site)
            continue
        results_by_site[site["id"]] = results
        cards += len(export_twins(site, src, dst, results, args.pairs, out,
                                  with_climate=not args.no_climate))

    export_traps([("moon", moon)] + ([("moon_polar", polar)] if polar else [])
                 + ([("mars", mars)] if mars else []),
                 earth, sites, by_body, out)
    export_portfolios(sites, earth, by_body, out)

    export_candidates(out)
    export_radar(sites, out)
    export_close_study(sites, by_body, earth, results_by_site, out, with_climate=not args.no_climate)

    # the tier rule, for the methodology page (#50)
    write_json(out / "verdict.json", dict(rule=verdict.RULE, holds=verdict.HOLDS,
                                          strong=verdict.STRONG, moderate=verdict.MODERATE))

    src_validation = C.INDEX / "validation.json"
    if src_validation.exists():
        write_json(out / "validation.json", json.loads(src_validation.read_text()))
    else:
        print("  - no data/index/validation.json yet (#16), skipping validation.json")

    written = sorted(p for p in out.rglob("*.json") if p.is_file())
    total = sum(p.stat().st_size for p in written)
    print(f"wrote {len(written)} files to {out} - {len(sites)} sites, "
          f"{cards} report cards, {total / 1e6:.2f} MB")

    base_done = sum(1 for s in sites
                    if s.get("is_base_region") and s["in_index"])
    print(f"{base_done}/{len(MOON_BASE_REGIONS)} Artemis base regions have analogs")
    mars_done = sum(1 for s in sites if s["body"] == "mars" and s["in_index"])
    print(f"{mars_done}/{len(MARS_SITES)} Mars sites have analogs"
          + ("" if mars else " (no Mars index yet: scripts/02_features.py mars, #38)"))

    if off_index:
        # The headline finding, not a footnote: these are the sites the
        # challenge title is about, and today we can say nothing about them.
        base = [s["id"] for s in off_index if s["is_base_region"]]
        off_index = [s for s in off_index if s["body"] != "mars" or mars is not None]
        print(f"\n! {len(off_index)} sites are outside the index and got no analogs.")
        if base:
            print(f"! {len(base)} of them are Artemis candidate base regions: "
                  f"{', '.join(base)}")
            print("! Build the polar index too (scripts/01_tiles.py moon_polar, "
                  "then scripts/02_features.py moon_polar) -- see #26.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
