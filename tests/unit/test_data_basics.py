# tests/unit/test_data_basics.py
"""Schema helpers, subsampling, warm-up splits and feature profiles."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftstream.core.errors import SchemaError
from driftstream.data.features import (
    build_profiles,
    load_profile,
    write_profiles,
)
from driftstream.data.schema import (
    feature_columns,
    normalise_name,
    require_columns,
)
from driftstream.data.splits import WarmupSpec, warmup_mask
from driftstream.data.subsample import keep_mask, uniform_hash

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Flow Duration", "flow_duration"),
        ("Down/Up Ratio", "down_up_ratio"),
        (" Fwd Packet Length Max ", "fwd_packet_length_max"),
        ("Dst host same src port rate", "dst_host_same_src_port_rate"),
    ],
)
def test_normalise_name(raw: str, expected: str) -> None:
    assert normalise_name(raw) == expected


def test_normalise_name_rejects_empty() -> None:
    with pytest.raises(SchemaError):
        normalise_name(" / ")


def _canonical() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "flow_id": np.arange(3, dtype=np.int64),
            "event_time": [1.0, 2.0, 3.0],
            "y": np.array([0, 1, 0], dtype=np.int8),
            "family": ["BENIGN", "DDoS", "BENIGN"],
            "label_raw": ["BENIGN", "DDoS", "BENIGN"],
            "f_a": [0.1, 0.2, 0.3],
            "c_b": ["x", "y", "z"],
        }
    )


def test_require_columns_accepts_canonical_frame() -> None:
    df = _canonical()
    require_columns(df)
    assert feature_columns(df.columns) == ["f_a", "c_b"]


def test_require_columns_rejects_missing_and_wrong_kinds() -> None:
    with pytest.raises(SchemaError, match="missing"):
        require_columns(_canonical().drop(columns=["y"]))
    bad = _canonical().assign(event_time=["a", "b", "c"])
    with pytest.raises(SchemaError, match="event_time"):
        require_columns(bad)


def test_uniform_hash_is_deterministic_and_seed_dependent() -> None:
    keys = np.arange(1000)
    a, b = uniform_hash(keys, 3), uniform_hash(keys, 3)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, uniform_hash(keys, 4))
    assert ((a >= 0) & (a < 1)).all()


def test_keep_mask_rate_and_nesting() -> None:
    keys = np.arange(200_000)
    small, large = keep_mask(keys, 0.1, 0), keep_mask(keys, 0.25, 0)
    assert small.mean() == pytest.approx(0.1, abs=0.005)
    assert large.mean() == pytest.approx(0.25, abs=0.005)
    assert not (small & ~large).any()  # kept at 10 % => kept at 25 %
    with pytest.raises(ValueError, match="fraction"):
        keep_mask(keys, 1.5, 0)


def test_warmup_by_days_and_by_first_days() -> None:
    t = (
        pd.to_datetime(
            ["2017-07-03 12:00", "2017-07-04 23:59", "2017-07-05 00:00"],
            utc=True,
        )
        .astype("int64")
        .to_numpy()
        / 1e9
    )
    by_days = WarmupSpec(days=("2017-07-03", "2017-07-04"))
    assert warmup_mask(t, by_days).tolist() == [True, True, False]
    first = WarmupSpec(first_days=1)
    assert warmup_mask(t, first).tolist() == [True, False, False]


def test_warmup_spec_from_config() -> None:
    assert WarmupSpec.from_config({"days": 30}).first_days == 30
    assert WarmupSpec.from_config({"days": ["2017-07-03"]}).days == (
        "2017-07-03",
    )
    with pytest.raises(ValueError, match="exactly one"):
        WarmupSpec()


def test_profiles_strict_removes_shortcuts(tmp_path) -> None:
    cols = ["flow_id", "f_dst_port", "f_protocol", "f_flow_duration"]
    profiles = build_profiles("cicids2017", cols)
    assert profiles["default"].numeric == (
        "f_dst_port",
        "f_protocol",
        "f_flow_duration",
    )
    assert profiles["strict"].numeric == ("f_flow_duration",)
    write_profiles("cicids2017", profiles, tmp_path)
    assert load_profile(tmp_path, "strict") == profiles["strict"]


def test_profiles_fail_when_a_shortcut_feature_is_renamed() -> None:
    with pytest.raises(SchemaError, match="shortcut"):
        build_profiles("cicids2017", ["f_destination_port", "f_protocol"])
