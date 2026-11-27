# tests/integration/test_etl_cic_small.py
"""CIC-IDS2017 ETL on the format-faithful fixture (ROADMAP T2.6)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import CIC_DAYS, CIC_DUPLICATES_PER_DAY
from driftstream.core.errors import DataValidationError
from driftstream.data.features import load_profile
from driftstream.data.loaders import load_frame
from driftstream.data.splits import WarmupSpec
from driftstream.etl.cicids2017 import run_cic_etl
from driftstream.etl.validate import validate_dataset

pytestmark = pytest.mark.integration

WARMUP = WarmupSpec(days=("2017-07-03", "2017-07-04"))


@pytest.fixture(scope="module")
def processed(cic_raw_dir: Path, tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("cic_out")
    report = run_cic_etl(cic_raw_dir, out, warmup=WARMUP)
    return out, report, load_frame(out)


def test_output_validates(processed) -> None:
    out, _, _ = processed
    report = validate_dataset("cicids2017", out, warmup=WARMUP)
    assert report.ok, report.failures
    assert len(report.passed) == 12


def test_counts_duplicates_and_attempted(processed) -> None:
    _, report, df = processed
    raw_total = sum(sum(c.values()) for _, c in CIC_DAYS.values())
    assert report.duplicates_removed == CIC_DUPLICATES_PER_DAY * len(CIC_DAYS)
    assert report.rows_written == raw_total == len(df)
    assert report.attempted == {
        "FTP-Patator": 3,
        "DoS Slowhttptest": 5,
        "Web Attack - XSS": 4,
        "Botnet": 6,
    }
    # attempted_policy = benign: attempted rows are benign, label kept
    att = df["label_raw"].str.endswith("- Attempted")
    assert (df.loc[att, "y"] == 0).all()
    assert (df.loc[att, "family"] == "BENIGN").all()


def test_identifiers_dropped_and_time_sorted(processed) -> None:
    _, _, df = processed
    for col in (
        "id",
        "flow_id_raw",
        "src_ip",
        "f_src_port",
        "f_id",
        "timestamp",
    ):
        assert col not in df.columns
    assert np.all(np.diff(df["event_time"].to_numpy()) >= 0)
    assert df["flow_id"].tolist() == list(range(len(df)))


def test_imputation_uses_warmup_medians_only(processed, cic_raw_dir) -> None:
    _, report, df = processed
    assert report.nan_imputed["f_flow_bytes_s"] > 0

    def median_of(days: set[str]) -> float:
        raw = pd.concat(
            [
                pd.read_csv(p)
                for p in sorted(cic_raw_dir.rglob("*.csv"))
                if p.stem in days
            ]
        ).drop_duplicates()  # fixture duplicates are exact row copies
        vals = pd.to_numeric(raw["Flow Bytes/s"], errors="coerce")
        return float(vals.replace([np.inf, -np.inf], np.nan).median())

    warm = median_of({"monday", "tuesday"})
    every = median_of({"monday", "tuesday", "wednesday", "thursday", "friday"})
    assert warm != pytest.approx(every)  # the choice of slice matters
    assert report.imputation_medians["f_flow_bytes_s"] == pytest.approx(warm)
    assert np.isfinite(df["f_flow_bytes_s"]).all()


def test_onsets_on_expected_days_and_eligibility(processed) -> None:
    out, _, _ = processed
    onsets = json.loads((out / "drift_onsets.json").read_text())["families"]
    assert all(e["on_expected_day"] for e in onsets.values())
    assert onsets["FTP-Patator"]["in_warmup"] is True
    assert onsets["DoS Hulk"]["in_warmup"] is False
    # min_family_flows = 1000: nothing in the tiny fixture is eligible
    assert not any(e["eligible_per_onset"] for e in onsets.values())


def test_strict_profile_removes_port_and_protocol(processed) -> None:
    out, _, _ = processed
    default, strict = load_profile(out, "default"), load_profile(out, "strict")
    assert {"f_dst_port", "f_protocol"} <= set(default.numeric)
    assert set(default.numeric) - set(strict.numeric) == {
        "f_dst_port",
        "f_protocol",
    }


@pytest.mark.parametrize(
    ("policy", "delta_attack"), [("attack", 18), ("drop", 0)]
)
def test_attempted_policies(
    cic_raw_dir: Path, tmp_path: Path, processed, policy: str, delta_attack: int
) -> None:
    _, base_report, base = processed
    report = run_cic_etl(
        cic_raw_dir, tmp_path, warmup=WARMUP, attempted_policy=policy
    )
    df = load_frame(tmp_path)
    assert df["y"].sum() == base["y"].sum() + delta_attack
    if policy == "drop":
        assert report.rows_written == base_report.rows_written - 18


def test_off_day_timestamps_fail_loudly(
    cic_raw_dir: Path, tmp_path: Path
) -> None:
    raw = tmp_path / "raw"
    shutil.copytree(cic_raw_dir, raw)
    path = next(raw.rglob("monday.csv"))
    df = pd.read_csv(path)
    df["Timestamp"] = df["Timestamp"].str.replace("2017-07-03", "2017-07-02")
    df.to_csv(path, index=False)
    with pytest.raises(DataValidationError, match="AM/PM"):
        run_cic_etl(raw, tmp_path / "out", warmup=WARMUP)
