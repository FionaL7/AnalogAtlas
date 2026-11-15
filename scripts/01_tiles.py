"""Step 1: build the tile grids and download image tiles.

    python scripts/01_tiles.py              # every body
    python scripts/01_tiles.py moon         # one body
    python scripts/01_tiles.py moon_polar   # the south pole (issue #26)
    python scripts/01_tiles.py mars         # Mars (issue #37)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import config as C, tiles  # noqa: E402

GRIDS = {"moon": tiles.moon_grid, "moon_polar": tiles.moon_polar_grid,
         "mars": tiles.mars_grid, "earth": tiles.earth_grid}

bodies = sys.argv[1:] or list(GRIDS)
C.INDEX.mkdir(parents=True, exist_ok=True)
for body in bodies:
    grid = GRIDS[body]()
    grid.to_parquet(C.INDEX / f"{body}_grid.parquet")
    print(f"{body}: {len(grid)} tiles")
    failed = tiles.fetch_tiles(grid)
    print(f"{body}: {len(failed)} failures")
    for f in failed[:20]:
        print("  ", f)
