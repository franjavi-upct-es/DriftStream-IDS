# tests/integration/test_etl_kyoto_small.py
"""Kyoto 2006+ PySpark ETL on the format-faithful fixture (T2.6)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator

import numpy as np
import pandas as pd
import pytest

from conftest import KYOTO_DAYS, KYOTO_ROWS_PER_DAY
from driftstream.data.loaders import load_frame
from driftstream.data.splits import WarmupSpec
from driftstream.etl.spark_kyoto_etl import (
    LEAKAGE_COLUMNS,
    discover_day_files,
    run_kyoto_etl,
)
from driftstream.etl.validate import validate_dataset

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("java") is None, reason="PySpark needs a Java runtime"
    ),
]
pyspark = pytest.importorskip("pyspark")

WARMUP = WarmupSpec(first_days=30)


@pytest.fixture(scope="module")
def spark() -> Iterator[object]:
    from driftstream.etl.spark_kyoto_etl import build_spark  # noqa: PLC0415

    session = build_spark("local[2]", driver_memory="1g")
    yield session
    session.stop()


@pytest.fixture(scope="module")
def processed(kyoto_raw_dir, spark, tmp_path_factory):
    out = tmp_path_factory.mktemp("kyoto_out")
    report = run_kyoto_etl(
        kyoto_raw_dir,
        out,
        start="2007-01",
        end="2007-03",
        warmup=WARMUP,
        target_sessions=10**9,
        spark=spark,
    )
    return out, report, load_frame(out)


def test_output_validates(processed) -> None:
    out, _, _ = processed
    report = validate_dataset("kyoto2006", out, warmup=WARMUP)
    assert report.ok, report.failures


def test_invalid_rows_dropped_and_counted(processed) -> None:
    _, report, df = processed
    assert report.files == len(KYOTO_DAYS)
    assert report.rows_read == len(KYOTO_DAYS) * KYOTO_ROWS_PER_DAY
    assert (report.invalid_label, report.invalid_time) == (1, 1)
    assert report.sampling_fraction == 1.0
    assert len(df) == report.rows_read - 2
    assert "2007-02-03" in report.missing_days


def test_leakage_columns_absent(processed) -> None:
    _, _, df = processed
    joined = " ".join(df.columns)
    for raw in LEAKAGE_COLUMNS:
        key = raw.lower().replace(" ", "_")
        assert key not in joined
    assert {"c_service", "c_flag", "c_protocol"} <= set(df.columns)
    assert "f_destination_port_number" in df.columns


def test_labels_and_families(processed) -> None:
    _, _, df = processed
    assert set(df["family"]) == {"BENIGN", "KNOWN", "UNKNOWN"}
    assert ((df["y"] == 1) == (df["family"] != "BENIGN")).all()


def test_start_time_is_converted_from_jst_to_utc(
    processed, kyoto_raw_dir
) -> None:
    _, _, df = processed
    first = next(kyoto_raw_dir.rglob("20070101.txt"))
    fields = first.read_text().splitlines()[0].split("\t")
    local = pd.Timestamp(f"2007-01-01 {fields[22]}", tz="Asia/Tokyo")
    expected = local.tz_convert("UTC").timestamp()
    match = df[np.isclose(df["event_time"], expected)]
    assert not match.empty


def test_sampling_is_deterministic_and_targets_size(
    kyoto_raw_dir, spark, tmp_path
) -> None:
    runs = []
    for i in range(2):
        out = tmp_path / f"run{i}"
        run_kyoto_etl(
            kyoto_raw_dir,
            out,
            start="2007-01",
            end="2007-03",
            warmup=WARMUP,
            target_sessions=200,
            sample_seed=7,
            spark=spark,
        )
        runs.append(load_frame(out))
    pd.testing.assert_frame_equal(runs[0], runs[1])
    assert 150 <= len(runs[0]) <= 250
    etl = json.loads((tmp_path / "run0" / "etl_report.json").read_text())
    assert etl["sampling_fraction"] < 1.0


def test_window_filters_files(kyoto_raw_dir) -> None:
    files = discover_day_files(kyoto_raw_dir, "2007-02", "2007-02")
    assert all(p.name.startswith("200702") for p in files)
    assert len(files) == 4
