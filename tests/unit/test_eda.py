# tests/unit/test_eda.py
"""EDA helpers on a small synthetic stream."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftstream.analysis import eda

pytestmark = pytest.mark.unit

T0 = pd.Timestamp("2007-01-01", tz="UTC").timestamp()


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 2000
    t = T0 + np.sort(rng.uniform(0, 60 * 86_400, n))  # two months
    second = t >= T0 + 31 * 86_400
    y = (rng.uniform(size=n) < np.where(second, 0.5, 0.1)).astype(np.int8)
    return pd.DataFrame(
        {
            "event_time": t,
            "y": y,
            "family": np.where(
                y == 1, np.where(second, "UNKNOWN", "KNOWN"), "BENIGN"
            ),
            "f_shift": rng.normal(np.where(second, 2.0, 0.0), 1.0),
            "f_stable": rng.normal(0.0, 1.0, n),
        }
    )


def test_arrival_rate_integrates_to_the_flow_count() -> None:
    df = _frame()
    rate = eda.arrival_rate(df, bin_seconds=86_400)
    assert rate.sum() * 86_400 == pytest.approx(len(df))
    with pytest.raises(ValueError, match="bin_seconds"):
        eda.arrival_rate(df, bin_seconds=0)


def test_attack_share_reflects_prior_drift() -> None:
    share = eda.attack_share(_frame(), bin_seconds=30 * 86_400)
    assert share.iloc[0] < 0.2
    assert share.iloc[-1] > 0.4


def test_family_timeline_orders_by_first_appearance() -> None:
    timeline = eda.family_timeline(_frame())
    assert list(timeline.index) == ["KNOWN", "UNKNOWN"]
    assert (timeline["duration_s"] >= 0).all()
    assert timeline["n_flows"].sum() == _frame()["y"].sum()


def test_feature_shift_flags_the_moving_feature() -> None:
    shift = eda.feature_shift(_frame(), ["f_shift", "f_stable"], period="month")
    assert list(shift.index) == ["2007-01", "2007-02", "2007-03"][: len(shift)]
    assert (shift.iloc[0] == 0).all()
    assert shift["f_shift"].iloc[1] > 0.5 > shift["f_stable"].iloc[1]
