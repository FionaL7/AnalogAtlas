"""Step 6: add the Mars counterpart columns to the Earth index (#39).

    python scripts/06_earth_columns.py            # all tiles, resumes if stopped
    python scripts/06_earth_columns.py --check    # only print the sanity checks

Adds to data/index/earth_meta.parquet, without touching row order:
    albedo       MODIS white-sky shortwave albedo, 0-1 (2020-22)
    dust_aod     MERRA-2 dust optical depth (2020-22)
    lst_mean_c   mean of the MODIS day and night surface temperatures, deg C

Needs Earth Engine (EE_PROJECT in .env). Takes about an hour. Progress is
saved to data/index/_earth_counterparts.partial.parquet, so a stopped run
picks up where it left off. Afterwards:
    python scripts/data.py push index/earth_meta.parquet
"""
import sys
import threading
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import analog, config as C, earth_ee  # noqa: E402

META = C.INDEX / "earth_meta.parquet"
PARTIAL = C.INDEX / "_earth_counterparts.partial.parquet"
COLS = earth_ee.COUNTERPART_COLUMNS


def nearest(meta: pd.DataFrame, lat: float, lon: float) -> pd.Series:
    d = analog.haversine_deg(meta.lat.values, meta.lon.values, lat, lon)
    return meta.iloc[int(d.argmin())]


def check(meta: pd.DataFrame) -> None:
    """Print coverage and a few places whose answer is known in advance."""
    for c in COLS + ["lst_mean_c"]:
        s = meta[c]
        print(f"  {c:11s} {s.notna().mean():6.1%} filled   min {s.min():.3f}  "
              f"median {s.median():.3f}  max {s.max():.3f}")
    places = {"Sahara (Tibesti)": (21.0, 17.5), "Atacama": (-24.1, -69.9), "Amazon": (-3.5, -62.3),
              "Taklamakan": (39.0, 83.0), "McMurdo Dry Valleys": (-77.5, 162.0),
              "Greenland ice sheet": (72.0, -40.0), "Devon Island": (75.4, -89.7)}
    print(f"  {'place':22s} {'albedo':>7s} {'dust_aod':>9s} {'lst_mean_c':>11s}")
    for name, (lat, lon) in places.items():
        r = nearest(meta, lat, lon)
        print(f"  {name:22s} {r.albedo:7.2f} {r.dust_aod:9.3f} {r.lst_mean_c:11.1f}")


def main() -> None:
    meta = pd.read_parquet(META)
    if "--check" in sys.argv:
        return check(meta)

    done = pd.read_parquet(PARTIAL) if PARTIAL.exists() else pd.DataFrame(columns=["tile_id"] + COLS)
    todo = meta[~meta.tile_id.isin(done.tile_id)]
    print(f"earth: {len(meta)} tiles, {len(done)} already done, {len(todo)} to do")

    lock = threading.Lock()
    rows: list[dict] = done.to_dict("records")

    def save(new: list[dict]) -> None:
        with lock:
            rows.extend(new)
            pd.DataFrame(rows).to_parquet(PARTIAL)

    earth_ee.mars_counterparts(todo[["tile_id", "lat_min", "lat_max", "lon_min", "lon_max"]],
                               on_chunk=save)

    got = pd.DataFrame(rows).drop_duplicates("tile_id").set_index("tile_id").reindex(meta.tile_id)
    missing = int(got[COLS].isna().all(axis=1).sum())
    for c in COLS:
        meta[c] = got[c].to_numpy()
    meta["lst_mean_c"] = earth_ee.mean_surface_c(meta)

    # Row order must not move: the embeddings are paired with it by position.
    before = pd.read_parquet(META, columns=["tile_id"])
    assert list(before.tile_id) == list(meta.tile_id), "row order changed"
    meta.to_parquet(META)
    analog.load_index("earth")          # re-checks the order stamp
    PARTIAL.unlink(missing_ok=True)
    print(f"wrote {META.name}: +{', '.join(COLS + ['lst_mean_c'])} ({missing} tiles with no data)")
    check(meta)


if __name__ == "__main__":
    main()
