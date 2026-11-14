"""Step 3: precompute the demo path as static JSON.

    python scripts/03_export.py                  # -> web/public/data/
    python scripts/03_export.py --no-climate     # skip the NASA POWER calls
    python scripts/03_export.py --out /tmp/data  # somewhere else

Everything the demo opens is written here, so judging never depends on the API
being up (ARCHITECTURE.md §1, §4.2). The API still serves free-text and image
search, which need CLIP at request time and cannot be precomputed.

Reads data/index/ and writes, under --out:

    sites.json                     targets and known Earth analogs
    dimensions.json                the report card's dimensions
    tiles/{body}.json              per-tile geometry + features for the map
    analogs/{site_id}.json         top-k Earth analogs per site (or Moon, reversed)
    twins/{site}__{tile}.json      report cards, climate baked in
    validation.json                copied from data/index/ if #16 has produced it
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import analog, config as C  # noqa: E402
from analogatlas.sites import (  # noqa: E402
    EARTH_PRESETS, KNOWN_EARTH_ANALOGS, MOON_BASE_REGIONS, MOON_SITES,
)
from api.indices import annotate_known  # noqa: E402  (shared so the export and API agree)

TILE_COLUMNS = ["tile_id", "lat", "lon", "lat_min", "lat_max", "lon_min", "lon_max",
                "slope_med", "relief_km", "elev_km"]


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


def build_sites(moon_in_index) -> list[dict]:
    """Every target and known analog, with ids the frontend routes on.

    Moon base regions are poleward of 80°S while the index stops at 60°S, so
    they are exported with `in_index: false`. Without that flag `nearest_tile`
    would quietly clamp to the index edge and we would publish analogs for a
    place 25° away from the one named. Resolved by #6.
    """
    out: list[dict] = []
    for name, (lat, lon) in MOON_BASE_REGIONS.items():
        out.append(dict(id=slug(name), body="moon", name=name, lat=lat, lon=lon,
                        is_base_region=True, in_index=bool(moon_in_index(lat)),
                        tile_url=moon_trek_tile_url(lat, lon),
                        blurb="Artemis candidate landing region."))
    for name, (lat, lon) in MOON_SITES.items():
        out.append(dict(id=slug(name), body="moon", name=name, lat=lat, lon=lon,
                        is_base_region=False, in_index=bool(moon_in_index(lat)),
                        tile_url=moon_trek_tile_url(lat, lon)))
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
                     climate: dict | None) -> list[dict]:
    """Derived from what `analog.breakdown()` actually returns, not hand-listed,
    so rows added there (#20) appear here without a second list to maintain."""
    moon_row = moon.meta.iloc[0]
    earth_row = earth.meta.iloc[0].copy()
    earth_row["visual_cos_scaled"] = 0.5
    rows = analog.breakdown(moon_row, earth_row, climate)
    out = []
    for row in rows.itertuples():
        out.append(dict(
            id=slug(row.dimension), label=row.dimension, note=row.note,
            # breakdown() marks each row's kind (#20); group on it, never on
            # match == 0, which a real comparison can also score.
            kind=row.kind,
            earth_cannot_reproduce=row.kind == "earth_limit",
            no_earth_equivalent=row.kind == "no_equivalent",
        ))
    return out


# ------------------------------------------------------------- exports ------
def export_tiles(idx: analog.BodyIndex, body: str, out: Path) -> int:
    cols = [c for c in TILE_COLUMNS if c in idx.meta.columns]
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
        rows.append(tile)
    return write_json(out / "tiles" / f"{body}.json", rows)


def export_analogs(site: dict, src: analog.BodyIndex, dst: analog.BodyIndex,
                   k: int, out: Path) -> list[dict] | None:
    """Top-k cross-body analogs for one site. None when the site is off-index."""
    if not site["in_index"]:
        return None
    i = src.nearest_tile(site["lat"], site["lon"])
    hits = analog.cross_body(src, i, dst, k=k)
    hits = hits[np.isfinite(hits.score.values)]
    results = [dict(
        tile_id=r.tile_id, lat=clean(r.lat, 3), lon=clean(r.lon, 3),
        score=clean(r.score, 4),
        visual_cos_scaled=clean(r.visual_cos_scaled, 4),
        physical=clean(r.physical, 4),
        known_analog=clean(getattr(r, "known_analog", None)),
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
    if site["body"] != "moon":
        return []   # breakdown() is Moon-vs-Earth; reverse pairs are not report cards
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
        path = out / "twins" / f"{site['id']}__{hit['tile_id']}.json"
        write_json(path, dict(
            site_id=site["id"],
            moon={c: clean(moon_row[c], 4) for c in moon_row.index if c not in ("z", "y", "x")},
            earth={**{c: clean(earth_row[c], 4) for c in earth_row.index},
                   "visual_cos_scaled": clean(earth_row.visual_cos_scaled, 4)},
            climate=None if climate is None else {k: clean(v, 3) for k, v in climate.items()},
            breakdown=[dict(dimension=r.dimension, id=slug(r.dimension),
                            moon=clean(r.moon), earth=clean(r.earth),
                            match=clean(r.match, 4), note=r.note, kind=r.kind)
                       for r in rows.itertuples()],
        ))
        written.append(path.name)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=C.ROOT / "web" / "public" / "data")
    ap.add_argument("--k", type=int, default=200, help="analogs per site (default 200)")
    ap.add_argument("--pairs", type=int, default=3, help="report cards per site (default 3)")
    ap.add_argument("--no-climate", action="store_true",
                    help="skip NASA POWER; twins get no climate rows")
    args = ap.parse_args()

    missing = [b for b in ("moon", "earth") if not (C.INDEX / f"{b}_meta.parquet").exists()]
    if missing:
        sys.exit(f"No index for {', '.join(missing)} in {C.INDEX}. "
                 "Build it first (scripts/01_tiles.py, scripts/02_features.py).")

    # load_index checks row counts and the tile_id order stamp (#12)
    try:
        moon, earth = analog.load_index("moon"), analog.load_index("earth")
    except analog.IndexMismatchError as e:
        sys.exit(f"index is inconsistent: {e} - do not export it")
    earth.meta = annotate_known(earth.meta)
    print(f"moon: {len(moon.meta)} tiles, earth: {len(earth.meta)} tiles")

    out: Path = args.out
    in_index = lambda lat: abs(lat) <= C.MOON_MAX_ABS_LAT   # noqa: E731
    sites = build_sites(in_index)
    write_json(out / "sites.json", sites)

    sample_climate = None
    if not args.no_climate:
        try:
            sample_climate = analog.earth_climate(-24.08, -69.92)   # Atacama
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"! NASA POWER unavailable, exporting without climate rows: {e}")
    write_json(out / "dimensions.json", build_dimensions(moon, earth, sample_climate))

    for body, idx in (("moon", moon), ("earth", earth)):
        export_tiles(idx, body, out)

    cards = 0
    off_index = []
    for site in sites:
        if site.get("is_known_analog"):
            continue        # reference points on the map, not search targets
        src, dst = (moon, earth) if site["body"] == "moon" else (earth, moon)
        results = export_analogs(site, src, dst, args.k, out)
        if results is None:
            off_index.append(site)
            continue
        cards += len(export_twins(site, src, dst, results, args.pairs, out,
                                  with_climate=not args.no_climate))

    src_validation = C.INDEX / "validation.json"
    if src_validation.exists():
        write_json(out / "validation.json", json.loads(src_validation.read_text()))
    else:
        print("  - no data/index/validation.json yet (#16), skipping validation.json")

    written = sorted(p for p in out.rglob("*.json") if p.is_file())
    total = sum(p.stat().st_size for p in written)
    print(f"wrote {len(written)} files to {out} - {len(sites)} sites, "
          f"{cards} report cards, {total / 1e6:.2f} MB")

    if off_index:
        # The headline finding, not a footnote: these are the sites the
        # challenge title is about, and today we can say nothing about them.
        base = [s["id"] for s in off_index if s["is_base_region"]]
        print(f"\n! {len(off_index)} sites are outside the index "
              f"(|lat| > {C.MOON_MAX_ABS_LAT:.0f}°) and got no analogs.")
        if base:
            print(f"! {len(base)} of them are Artemis candidate base regions: "
                  f"{', '.join(base)}")
            print("! Until the polar index exists (#6), the demo answers "
                  "'analogs for lunar terrain', not 'for Moon-base sites'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
