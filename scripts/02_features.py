"""Step 2: physical statistics + CLIP embeddings for every downloaded tile.

    python scripts/02_features.py            # both bodies
    python scripts/02_features.py earth      # one body

Writes data/index/{body}_meta.parquet, {body}_shade.npy, {body}_img.npy
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import config as C, rasters  # noqa: E402
from analogatlas.analog import write_order_stamp  # noqa: E402
from analogatlas.embed import embed_images, normalize_shade  # noqa: E402
from analogatlas.tiles import tile_path  # noqa: E402

BATCH = 64


def colour_stats(paths):
    """Greenness (excess-green index) and brightness of the true-colour tile."""
    g, b = [], []
    for p in paths:
        a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) / 255
        g.append(float((2 * a[..., 1] - a[..., 0] - a[..., 2]).mean()))
        b.append(float(a.mean()))
    return g, b


def embed_all(paths, shade):
    """shade=True: contrast-normalise, then average over four rotations."""
    out = []
    for i in tqdm(range(0, len(paths), BATCH), desc=f"embed ({'shade' if shade else 'img'})"):
        ims = [Image.open(p) for p in paths[i:i + BATCH]]
        if shade:
            ims = [normalize_shade(im) for im in ims]
        out.append(embed_images(ims, rotations=shade))
    return np.concatenate(out).astype(np.float16)


for body in sys.argv[1:] or ["moon", "earth"]:
    grid = pd.read_parquet(C.INDEX / f"{body}_grid.parquet")
    have = grid.tile_id.map(lambda t: tile_path(body, "img", t).exists() and tile_path(body, "shade", t).exists())
    grid = grid[have].reset_index(drop=True)
    print(f"{body}: {len(grid)} tiles with both layers")

    meta = rasters.moon_physical(grid) if body == "moon" else rasters.earth_physical(grid)
    if body == "earth":
        meta["greenness"], meta["brightness"] = colour_stats([tile_path(body, "img", t) for t in grid.tile_id])
    meta.to_parquet(C.INDEX / f"{body}_meta.parquet")

    np.save(C.INDEX / f"{body}_shade.npy", embed_all([tile_path(body, "shade", t) for t in grid.tile_id], True))
    np.save(C.INDEX / f"{body}_img.npy", embed_all([tile_path(body, "img", t) for t in grid.tile_id], False))
    assert len(np.load(C.INDEX / f"{body}_shade.npy")) == len(np.load(C.INDEX / f"{body}_img.npy")) == len(meta)
    # meta and both matrices were built from the same `grid` order; record it so
    # load_index() can refuse a re-sorted meta later (issue #12)
    write_order_stamp(body, meta)
    print(f"{body}: done")
