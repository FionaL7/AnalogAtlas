"""Step 2: physical statistics + CLIP embeddings for every downloaded tile.

    python scripts/02_features.py            # every body
    python scripts/02_features.py earth      # one body
    python scripts/02_features.py moon_polar # the south pole (#26)
    python scripts/02_features.py earth --meta-only   # redo features, keep embeddings

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


PHYSICAL = {"moon": rasters.moon_physical, "moon_polar": rasters.moon_polar_physical,
            "earth": rasters.earth_physical}


def has_content(paths, min_frac=0.05):
    """Whether a chip carries real imagery rather than empty shadow/no-data.

    The LROC NAC polar mosaic covers only 85.5-90 S, and much of the pole is
    in genuine darkness, so many polar chips are blank. Flagging them lets
    free-text search skip them instead of matching on black.
    """
    return [bool((np.asarray(Image.open(p).convert("L")) > 8).mean() >= min_frac) for p in paths]


args = sys.argv[1:]
meta_only = "--meta-only" in args
for body in [a for a in args if not a.startswith("--")] or list(PHYSICAL):
    grid = pd.read_parquet(C.INDEX / f"{body}_grid.parquet")
    have = grid.tile_id.map(lambda t: tile_path(body, "img", t).exists() and tile_path(body, "shade", t).exists())
    grid = grid[have].reset_index(drop=True)
    print(f"{body}: {len(grid)} tiles with both layers")

    meta = PHYSICAL[body](grid)
    if body == "earth":
        meta["greenness"], meta["brightness"] = colour_stats([tile_path(body, "img", t) for t in grid.tile_id])
        if C.EE_PROJECT:
            from analogatlas import earth_ee
            meta = pd.concat([meta, earth_ee.environment(grid)], axis=1)
    if body == "moon_polar":
        meta["has_img"] = has_content([tile_path(body, "img", t) for t in grid.tile_id])
        print(f"{body}: {int(meta.has_img.sum())}/{len(meta)} tiles have usable NAC imagery")
    if meta_only:
        old = pd.read_parquet(C.INDEX / f"{body}_meta.parquet")
        assert old.tile_id.tolist() == meta.tile_id.tolist(), "tile set changed: run without --meta-only"
        meta.to_parquet(C.INDEX / f"{body}_meta.parquet")
        write_order_stamp(body, meta)              # order unchanged (asserted above)
        print(f"{body}: meta rewritten, embeddings kept")
        continue
    meta.to_parquet(C.INDEX / f"{body}_meta.parquet")

    np.save(C.INDEX / f"{body}_shade.npy", embed_all([tile_path(body, "shade", t) for t in grid.tile_id], True))
    np.save(C.INDEX / f"{body}_img.npy", embed_all([tile_path(body, "img", t) for t in grid.tile_id], False))
    assert len(np.load(C.INDEX / f"{body}_shade.npy")) == len(np.load(C.INDEX / f"{body}_img.npy")) == len(meta)
    # meta and both matrices were built from the same `grid` order; record it so
    # load_index() can refuse a re-sorted meta later (issue #12)
    write_order_stamp(body, meta)
    print(f"{body}: done")
