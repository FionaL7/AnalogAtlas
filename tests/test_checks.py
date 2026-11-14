"""Shared environment checks (#33): one definition for search and traps."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analogatlas.checks import env_flags, push_down_mask


def test_flags_and_push_down():
    meta = pd.DataFrame(dict(
        ice_frac=[0.9, 0.0, 0.0, 0.0, np.nan],
        veg_frac=[0.0, 0.0, 0.1, 0.0, np.nan],
        ndvi=[0.0, 0.05, 0.6, 0.1, np.nan],
        water_frac=[0.0, 0.0, 0.0, 0.0, np.nan],
        aridity=[10.0, 0.1, 0.4, 2.0, np.nan],
    ), index=["ice", "desert", "green", "wet", "unknown"])
    f = env_flags(meta)
    assert f.loc["ice", "ice"] and not f.loc["ice", "wet_climate"]
    assert f.loc["green", "vegetation"]          # by greenness alone
    assert f.loc["wet", "wet_climate"]
    assert not f.loc["desert"].any() and not f.loc["unknown"].any()
    # wet climate is a trap reason, not a push-down
    assert list(push_down_mask(meta)) == [True, False, True, False, False]


def test_missing_columns_flag_nothing():
    meta = pd.DataFrame(dict(slope_med=[1.0, 2.0]))
    assert not env_flags(meta).to_numpy().any()
    assert not push_down_mask(meta).any()
