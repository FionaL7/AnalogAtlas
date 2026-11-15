"""Radar roughness (CPR) data: find, download, and summarise (#17, #18).

    python scripts/04_radar.py download-minirf          # Moon CPR map, 265 MB
    python scripts/04_radar.py moon-sites               # CPR for every Moon site
    python scripts/04_radar.py find-rcm 54.56 -63.43    # free RCM scenes over a point
    python scripts/04_radar.py download-rcm <item-id> <folder-name>
    python scripts/04_radar.py close-study              # the #19 pairs: radar, slope, picture

Moon: NASA LRO Mini-RF global CPR mosaic (PDS). Earth: Canada's RCM CEOS-ARD
on AWS open data (no account; Canada south of ~70N; a sample of dates, not
every 12 days). Reading RCM GeoTIFFs needs rasterio: on Windows machines with
Application Control, run in Docker (see .claude/skills/radar-roughness).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import config as C  # noqa: E402
from analogatlas import radar  # noqa: E402
from analogatlas.sites import MOON_BASE_REGIONS, MOON_SITES  # noqa: E402
from analogatlas import closestudy as CS  # noqa: E402

MINIRF_URL = ("https://pds-geosciences.wustl.edu/lro/lro-l-mrflro-5-global-mosaic-v1/"
              "lromrf_1001/data/32ppd/global_cpr_32ppd_simp_0c")
RCM_STAC = "https://eodms-sgdot.nrcan-rncan.gc.ca/search/collections/rcm-ard"
# per scene we only need these (RRRL and the angle images are not used for CPR)
RCM_ASSETS = {"rr": "scene_RR.tif", "rl": "scene_RL.tif", "data_mask": "scene_bitmask.tif",
              "metadata": "scene_product.xml", "thumbnail": "scene_RR_quickLook.png"}


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  have {dest.name}")
        return
    print(f"  downloading {dest.name} ...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


def download_minirf() -> None:
    for ext in (".lbl", ".img"):
        download(MINIRF_URL + ext, radar.MINIRF_DIR / Path(MINIRF_URL + ext).name)


def moon_sites(half_km: float = 15.0) -> None:
    grid = radar.minirf_cpr()
    out = {}
    print(f"{'site':46s} {'CPR med':>8s} {'p90':>6s} {'cover':>6s}")
    for name, (lat, lon) in {**MOON_BASE_REGIONS, **MOON_SITES}.items():
        s = radar.minirf_box(*radar.box_around(lat, lon, half_km, C.MOON_KM_PER_DEG), grid=grid)
        out[name] = dict(lat=lat, lon=lon, box_half_km=half_km, **s.as_dict())
        med = "none" if s.cpr_median is None else f"{s.cpr_median:.2f}"
        p90 = "" if s.cpr_p90 is None else f"{s.cpr_p90:.2f}"
        print(f"{name[:46]:46s} {med:>8s} {p90:>6s} {s.coverage:6.0%}")
    path = C.INDEX / "moon_site_cpr.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(f"wrote {path}")


def find_rcm(lat: float, lon: float) -> None:
    """Scenes whose footprint contains the point. Pages through a 2x3 deg box."""
    url = f"{RCM_STAC}/items?bbox={lon-1.5},{lat-1},{lon+1.5},{lat+1}&limit=200"
    hits = []
    while url:
        d = fetch_json(url)
        hits += [f for f in d["features"]
                 if f["bbox"][0] <= lon <= f["bbox"][2] and f["bbox"][1] <= lat <= f["bbox"][3]]
        url = next((link["href"] for link in d.get("links", []) if link.get("rel") == "next"), None)
    print(f"{len(hits)} RCM scenes contain ({lat}, {lon})")
    for f in sorted(hits, key=lambda f: f["properties"]["datetime"]):
        print(f"  {f['properties']['datetime'][:10]}  {f['id']}")
    if not hits:
        print("  None in the free archive. Options: order via EODMS, or Sentinel-1 (VH/VV, not CPR).")


def download_rcm(item_id: str, folder: str) -> None:
    f = fetch_json(f"{RCM_STAC}/items/{item_id}")
    dest = C.RAW / "rcm" / folder
    for key, name in RCM_ASSETS.items():
        if key in f["assets"]:
            download(f["assets"][key]["href"], dest / name)
    (dest / "stac_item.json").write_text(json.dumps(f, indent=1))
    print(f"scene in {dest} ({f['properties']['datetime'][:10]})")


def close_study() -> None:
    """Measure every pair in closestudy.PAIRS -> data/index/close_study.json,
    plus one Sentinel-2 picture per pair in data/index/close_study/.

    Needs rasterio and pandas (Docker on rishabh-win, see the skill), the
    Mini-RF map, and the RCM scenes named in PAIRS (download-rcm)."""
    import pandas as pd
    earth = pd.read_parquet(C.INDEX / "earth_meta.parquet").set_index("tile_id")
    moon_sites = {**MOON_BASE_REGIONS, **MOON_SITES}
    out = []
    for pair in CS.PAIRS:
        row = earth.loc[pair["earth_tile_id"]]
        tile = dict(tile_id=pair["earth_tile_id"], lat=float(row.lat), lon=float(row.lon))
        box = CS.earth_box(tile)
        site_lat, site_lon = moon_sites[pair["site"]]
        print(f"{pair['id']}: {pair['site']} <-> {pair['earth_name']}")

        moon = CS.moon_roughness((site_lat, site_lon))
        s1 = CS.s1_roughness(box, pair["s1_dates"])
        cpr = CS.rcm_roughness(box, pair["rcm_scenes"]) if pair.get("rcm_scenes") else None
        slope = CS.dem_slope(box)
        pic = CS.s2_picture(box, pair["s2_dates"], CS.OUT_DIR / f"{pair['id']}_s2.jpg")
        fmt = lambda r: "none" if r is None or r.cpr_median is None else f"{r.cpr_median:.3f} ({r.coverage:.0%})"  # noqa: E731
        print(f"  Moon CPR {fmt(moon)} | Earth CPR {fmt(cpr)} | Earth S1 VH/VV {fmt(s1)} | "
              f"30 m slope {slope['slope_med']} deg | picture {pic and pic['date']}")

        out.append(dict(
            **{k: v for k, v in pair.items() if k not in ("s1_dates", "s2_dates", "rcm_scenes")},
            site_lat=site_lat, site_lon=site_lon,
            earth_lat=tile["lat"], earth_lon=tile["lon"],
            box=dict(half_km=CS.HALF_KM, lat_min=box[0], lat_max=box[1], lon_min=box[2], lon_max=box[3]),
            radar=dict(
                moon=dict(moon.as_dict(), box_half_km=CS.HALF_KM),
                earth_cpr=None if cpr is None else dict(cpr.as_dict(), box_half_km=CS.HALF_KM,
                                                        scenes=pair["rcm_scenes"]),
                earth_s1=dict(s1.as_dict(), box_half_km=CS.HALF_KM, dates=pair["s1_dates"]),
            ),
            earth_slope_30m=slope,
            picture=pic,
        ))
    CS.OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"wrote {CS.OUT_JSON}")


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if cmd == "download-minirf":
        download_minirf()
    elif cmd == "moon-sites":
        moon_sites()
    elif cmd == "find-rcm" and len(args) == 2:
        find_rcm(float(args[0]), float(args[1]))
    elif cmd == "download-rcm" and len(args) == 2:
        download_rcm(*args)
    elif cmd == "close-study":
        close_study()
    else:
        sys.exit(__doc__)
