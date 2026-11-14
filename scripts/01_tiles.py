"""Step 1: build the Moon/Earth tile grids and download image tiles.

    python scripts/01_tiles.py            # both bodies
    python scripts/01_tiles.py moon       # one body
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import config as C, tiles  # noqa: E402

bodies = sys.argv[1:] or ["moon", "earth"]
C.INDEX.mkdir(parents=True, exist_ok=True)
for body in bodies:
    grid = tiles.moon_grid() if body == "moon" else tiles.earth_grid()
    grid.to_parquet(C.INDEX / f"{body}_grid.parquet")
    print(f"{body}: {len(grid)} tiles")
    failed = tiles.fetch_tiles(grid)
    print(f"{body}: {len(failed)} failures")
    for f in failed[:20]:
        print("  ", f)
