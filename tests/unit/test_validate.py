# tests/unit/test_validate.py
"""Post-ETL validation catches each broken invariant."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftstream.core.errors import DataValidationError
from driftstream.data.loaders import load_frame
from driftstream.data.splits import WarmupSpec
from driftstream.etl.cicids2017 import EXPECTED_DAY
from driftstream.etl.onsets import compute_onsets
from driftstream.etl.stats import compute_stats
from driftstream.etl.validate import validate_dataset
from driftstream.etl.writer import finalise_frame, write_dataset

pytestmark = pytest.mark.unit

WARMUP = WarmupSpec(days=("2017-07-03",))
T0 = pd.Timestamp("2017-07-03 12:00", tz="UTC").timestamp()


def _frame() -> pd.DataFrame:
    n = 40
    t = T0 + np.concatenate([np.arange(20) * 60.0, 86_400 + np.arange(20) * 60])
    y = np.r_[np.zeros(20), np.zeros(10), np.ones(10)].astype(np.int8)
    family = np.where(y == 1, "SSH-Patator", "BENIGN")
    return pd.DataFrame(
        {
            "event_time": t,
            "y": y,
            "family": family,
            "label_raw": family,
            "f_dst_port": np.full(n, 22.0),
            "f_protocol": np.full(n, 6.0),
            "f_x": np.linspace(0, 1, n),
        }
    )


def _write(df: pd.DataFrame, out: Path) -> Path:
    fin = finalise_frame(df)
    write_dataset(
        fin,
        "cicids2017",
        out,
        partition="day",
        extra_files={
            "etl_report.json": {},
            "drift_onsets.json": compute_onsets(
                fin, warmup=WARMUP, min_flows=1, expected_day=EXPECTED_DAY
            ),
            "stats.json": compute_stats(fin, warmup=WARMUP),
        },
    )
    return out


def test_clean_dataset_passes(tmp_path: Path) -> None:
    report = validate_dataset(
        "cicids2017", _write(_frame(), tmp_path), warmup=WARMUP
    )
    assert report.ok, report.failures
    report.raise_if_failed()


def _corrupt(tmp_path: Path, mutate) -> dict[str, str]:
    out = _write(_frame(), tmp_path)
    part = sorted(out.rglob("part-0.parquet"))[-1]
    df = pd.read_parquet(part)
    mutate(df)
    df.to_parquet(part, index=False)
    return validate_dataset("cicids2017", out, warmup=WARMUP).failures


def test_detects_decreasing_time(tmp_path: Path) -> None:
    def mutate(df: pd.DataFrame) -> None:
        df.loc[df.index[-1], "event_time"] = df["event_time"].iloc[0] - 1

    failures = _corrupt(tmp_path, mutate)
    assert "time_order" in failures and "checksums" in failures


def test_detects_leaked_identifier(tmp_path: Path) -> None:
    failures = _corrupt(tmp_path, lambda df: df.insert(5, "f_src_port", 1.0))
    assert "no_leakage" in failures


def test_detects_non_finite_features(tmp_path: Path) -> None:
    def mutate(df: pd.DataFrame) -> None:
        df.loc[df.index[0], "f_x"] = np.inf

    assert "finite_features" in _corrupt(tmp_path, mutate)


def test_detects_label_family_disagreement(tmp_path: Path) -> None:
    def mutate(df: pd.DataFrame) -> None:
        df.loc[df.index[0], "y"] = 1

    failures = _corrupt(tmp_path, mutate)
    assert "labels" in failures
    with pytest.raises(DataValidationError):
        validate_dataset(
            "cicids2017", tmp_path, warmup=WARMUP
        ).raise_if_failed()


def test_detects_family_on_wrong_day(tmp_path: Path) -> None:
    df = _frame()
    df.loc[df["y"] == 1, "family"] = "DDoS"  # DDoS belongs to Friday
    df["label_raw"] = df["family"]
    out = _write(df, tmp_path)
    failures = validate_dataset("cicids2017", out, warmup=WARMUP).failures
    assert "onsets" in failures
    assert len(load_frame(out)) == 40
