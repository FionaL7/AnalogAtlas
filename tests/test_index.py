"""Issue #12: load_index refuses an index whose rows no longer line up."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from analogatlas import config as C
from analogatlas.analog import IndexMismatchError, load_index

from .conftest import write_index


@pytest.fixture
def moon_index(tmp_path, monkeypatch):
    d = tmp_path / "index"
    meta = write_index(d, bodies=("moon",))["moon"]
    monkeypatch.setattr(C, "INDEX", d)
    return d, meta


def test_aligned_index_loads(moon_index):
    d, meta = moon_index
    idx = load_index("moon")
    assert list(idx.meta.tile_id) == list(meta.tile_id)
    assert len(idx.shade) == len(idx.img) == len(meta)


def test_reordered_meta_is_rejected(moon_index):
    """Same rows, same count, different order: the silent-wrong-analogs case."""
    d, meta = moon_index
    meta.iloc[::-1].reset_index(drop=True).to_parquet(d / "moon_meta.parquet")
    with pytest.raises(IndexMismatchError, match="row order changed"):
        load_index("moon")


def test_swapping_two_rows_is_rejected(moon_index):
    d, meta = moon_index
    order = np.arange(len(meta))
    order[[3, 4]] = order[[4, 3]]
    meta.iloc[order].reset_index(drop=True).to_parquet(d / "moon_meta.parquet")
    with pytest.raises(IndexMismatchError):
        load_index("moon")


@pytest.mark.parametrize("matrix", ["shade", "img"])
def test_length_mismatch_is_rejected(moon_index, matrix):
    d, _ = moon_index
    np.save(d / f"moon_{matrix}.npy", np.load(d / f"moon_{matrix}.npy")[:-1])
    with pytest.raises(IndexMismatchError, match="rows differ"):
        load_index("moon")


def test_old_index_without_stamp_loads_with_a_warning(moon_index, caplog):
    """Indexes built before the stamp existed still load, but say so."""
    d, meta = moon_index
    (d / "moon_order.json").unlink()
    with caplog.at_level(logging.WARNING, logger="analogatlas"):
        idx = load_index("moon")
    assert len(idx.meta) == len(meta)
    assert "row order not verified" in caplog.text


def test_reordered_meta_without_stamp_still_loads(moon_index):
    """Documents the limit: with no stamp, only lengths can be checked."""
    d, meta = moon_index
    (d / "moon_order.json").unlink()
    meta.iloc[::-1].to_parquet(d / "moon_meta.parquet")
    assert isinstance(load_index("moon").meta, pd.DataFrame)
