"""The Mars counterpart columns on Earth (#39). Earth Engine is stubbed: these
check the bookkeeping (order, missing values, resume hook), not the data."""
from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd
import pytest

from analogatlas import analog


@pytest.fixture
def earth_ee(monkeypatch):
    """earth_ee with a fake `ee` that answers reduceRegions from a table."""
    answers = {"a": {"albedo": 0.4, "dust_aod": 0.25}, "b": {"albedo": None, "dust_aod": 0.01},
               "c": {"albedo": 0.13, "dust_aod": 0.02}}

    class FC:
        def __init__(self, feats):
            self.feats = feats

    class Image:
        def reduceRegions(self, fc, *_a, **_k):
            feats = [{"properties": {"tile_id": f, **answers[f]}} for f in reversed(fc.feats) if f != "c"]
            return types.SimpleNamespace(getInfo=lambda: {"features": feats})

    fake = types.SimpleNamespace(
        FeatureCollection=FC, Feature=lambda _geom, props: props["tile_id"],
        Geometry=types.SimpleNamespace(Rectangle=lambda *a, **k: None),
        Reducer=types.SimpleNamespace(mean=lambda: None))
    monkeypatch.setitem(sys.modules, "ee", fake)
    from analogatlas import earth_ee as mod
    monkeypatch.setattr(mod, "init", lambda: fake)
    monkeypatch.setattr(mod, "_counterpart_image", lambda: Image())
    return mod


def _grid(ids):
    return pd.DataFrame(dict(tile_id=ids, lat_min=0.0, lat_max=1.0, lon_min=0.0, lon_max=1.0))


def test_counterparts_come_back_in_grid_order_with_gaps_as_nan(earth_ee):
    """Earth Engine returns features in its own order and drops tiles with no
    data ("c" here); a null property ("b" albedo) must become NaN, not 0."""
    out = earth_ee.mars_counterparts(_grid(["c", "a", "b"]), batch=2, workers=1)
    assert list(out.columns) == ["albedo", "dust_aod"]
    assert len(out) == 3
    assert np.isnan(out.albedo[0]) and np.isnan(out.dust_aod[0])        # c: dropped
    assert out.albedo[1] == 0.4 and out.dust_aod[1] == 0.25             # a
    assert np.isnan(out.albedo[2]) and out.dust_aod[2] == 0.01          # b


def test_each_finished_batch_is_handed_to_on_chunk(earth_ee):
    seen = []
    earth_ee.mars_counterparts(_grid(["a", "b"]), batch=1, workers=1, on_chunk=seen.extend)
    assert sorted(r["tile_id"] for r in seen) == ["a", "b"]


def test_empty_grid_makes_no_request(earth_ee):
    assert earth_ee.mars_counterparts(_grid([])).empty


def test_lst_mean_matches_what_the_report_card_falls_back_to(earth_ee):
    """analog.earth_mean_c derives the same number when lst_mean_c is absent,
    so cards built before and after #39 agree."""
    meta = pd.DataFrame(dict(lst_day_c=[42.0, -12.0], lst_night_c=[8.0, -24.0]))
    mean = earth_ee.mean_surface_c(meta)
    assert list(mean) == [25.0, -18.0]
    assert list(analog.earth_mean_c(meta)) == [25.0, -18.0]
    meta["lst_mean_c"] = mean
    assert list(analog.earth_mean_c(meta)) == [25.0, -18.0]
