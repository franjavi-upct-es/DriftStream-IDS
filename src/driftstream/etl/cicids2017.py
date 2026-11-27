# src/driftstream/etl/cicids2017.py
"""CIC-IDS2017 (improved, DistriNet) raw CSVs → canonical Parquet (T2.2).

Input format, checked against the dataset authors' labelling code
(``GintsEngelen/CNS2022_Code``, 2026-11-25): one CSV per weekday
(``monday.csv`` … ``friday.csv``); an ``id`` column; identifiers
``Flow ID``, ``Src IP``, ``Src Port``, ``Dst IP``; ``Timestamp`` in **UTC
with microsecond precision**; CICFlowMeter features; ``Label``, with
``"<attack> - Attempted"`` for attack flows without a malicious payload;
and ``Attempted Category`` (-1 for non-attempted flows).

Steps (ARCHITECTURE.md §8.3): timestamp and day checks → label mapping
with ``attempted_policy`` → identifier removal → numeric coercion
(``Infinity`` → NaN) → exact-duplicate removal within the same second →
median imputation fitted on the **warm-up slice only** → time sort,
``flow_id``, Parquet by day, side files.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from driftstream.core.errors import (
    DataValidationError,
    SchemaError,
    UnknownLabelError,
)
from driftstream.data.schema import NUMERIC_PREFIX, normalise_name
from driftstream.data.splits import WarmupSpec, warmup_mask
from driftstream.etl.onsets import compute_onsets
from driftstream.etl.stats import compute_stats
from driftstream.etl.writer import finalise_frame, write_dataset

__all__ = [
    "CAPTURE_DAYS",
    "EXPECTED_DAY",
    "FAMILIES",
    "CicEtlReport",
    "discover_day_files",
    "map_label",
    "run_cic_etl",
]

log = logging.getLogger(__name__)
AttemptedPolicy = Literal["benign", "attack", "drop"]

#: UTC capture day of each weekday file (Sharafaldin et al. 2018).
CAPTURE_DAYS: dict[str, str] = {
    "monday": "2017-07-03",
    "tuesday": "2017-07-04",
    "wednesday": "2017-07-05",
    "thursday": "2017-07-06",
    "friday": "2017-07-07",
}

#: Canonical attack families and the day they are expected on.
EXPECTED_DAY: dict[str, str] = {
    "FTP-Patator": "2017-07-04",
    "SSH-Patator": "2017-07-04",
    "DoS Slowloris": "2017-07-05",
    "DoS Slowhttptest": "2017-07-05",
    "DoS Hulk": "2017-07-05",
    "DoS GoldenEye": "2017-07-05",
    "Heartbleed": "2017-07-05",
    "Web Attack - Brute Force": "2017-07-06",
    "Web Attack - XSS": "2017-07-06",
    "Web Attack - SQL Injection": "2017-07-06",
    "Infiltration": "2017-07-06",
    "Infiltration - Portscan": "2017-07-06",
    "Botnet": "2017-07-07",
    "Portscan": "2017-07-07",
    "DDoS": "2017-07-07",
}
FAMILIES: tuple[str, ...] = ("BENIGN", *EXPECTED_DAY)

#: Spellings used by other releases (original CIC, WTMC 2021) → canonical.
_ALIASES: dict[str, str] = {
    "benign": "BENIGN",
    "bot": "Botnet",
    "portscan": "Portscan",
    "dos slowhttptest": "DoS Slowhttptest",
    "web attack brute force": "Web Attack - Brute Force",
    "web attack xss": "Web Attack - XSS",
    "web attack sql injection": "Web Attack - SQL Injection",
}
_CANONICAL = {
    re.sub(r"[^a-z0-9]+", " ", f.lower()).strip(): f for f in FAMILIES
}
_ATTEMPTED = re.compile(r"\s*-\s*attempted\s*$", re.IGNORECASE)

#: Identifier columns dropped before modelling (never features).
IDENTIFIERS: tuple[str, ...] = ("id", "Flow ID", "Src IP", "Src Port", "Dst IP")
#: Fraction of rows allowed outside their file's UTC day.
DAY_TOLERANCE = 1e-3


def map_label(raw: str) -> tuple[str, bool]:
    """Return ``(canonical family, attempted?)`` for a raw label.

    Args:
        raw: Value of the ``Label`` column.

    Returns:
        The canonical family name and whether the flow is "Attempted".

    Raises:
        UnknownLabelError: If the label is not a known family.
    """
    text = raw.strip()
    attempted = bool(_ATTEMPTED.search(text))
    base = _ATTEMPTED.sub("", text)
    key = re.sub(r"[^a-z0-9]+", " ", base.lower()).strip()
    family = _CANONICAL.get(key) or _ALIASES.get(key)
    if family is None:
        raise UnknownLabelError(f"unknown CIC-IDS2017 label {raw!r}")
    if attempted and family == "BENIGN":
        raise UnknownLabelError(f"benign flows cannot be attempted: {raw!r}")
    return family, attempted


def discover_day_files(raw_dir: Path) -> dict[str, Path]:
    """Find the five weekday CSVs anywhere under ``raw_dir``.

    Args:
        raw_dir: Directory the archive was extracted into.

    Returns:
        Weekday name → CSV path.

    Raises:
        SchemaError: If a weekday is missing or matched twice.
    """
    found: dict[str, list[Path]] = {d: [] for d in CAPTURE_DAYS}
    for path in sorted(Path(raw_dir).rglob("*.csv")):
        stem = path.stem.lower()
        for day in CAPTURE_DAYS:
            if stem.startswith(day):
                found[day].append(path)
    problems = {d: p for d, p in found.items() if len(p) != 1}
    if problems:
        raise SchemaError(f"expected one CSV per weekday, got {problems}")
    return {d: p[0] for d, p in found.items()}


@dataclass(slots=True)
class CicEtlReport:
    """What the ETL did, written to ``etl_report.json``.

    Attributes:
        rows_read: Rows per weekday file.
        rows_off_day: Rows outside their file's UTC day (dropped).
        attempted: "Attempted" rows per family before the policy.
        attempted_policy: Policy applied to "Attempted" rows.
        duplicates_removed: Exact duplicates within the same second.
        nan_imputed: NaN/inf values imputed, per feature.
        imputation_medians: Warm-up medians used, per feature.
        rows_written: Rows in the processed table.
    """

    rows_read: dict[str, int] = field(default_factory=dict)
    rows_off_day: dict[str, int] = field(default_factory=dict)
    attempted: dict[str, int] = field(default_factory=dict)
    attempted_policy: str = "benign"
    duplicates_removed: int = 0
    nan_imputed: dict[str, int] = field(default_factory=dict)
    imputation_medians: dict[str, float] = field(default_factory=dict)
    rows_written: int = 0


def _read_day(path: Path) -> pd.DataFrame:
    try:
        df: pd.DataFrame = pd.read_csv(path, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:  # older releases were written in cp1252
        df = pd.read_csv(path, encoding="cp1252", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    for col in ("Timestamp", "Label"):
        if col not in df.columns:
            raise SchemaError(f"{path.name}: missing column {col!r}")
    return df


def _transform_day(
    df: pd.DataFrame, day: str, report: CicEtlReport
) -> pd.DataFrame:
    ts = pd.to_datetime(df["Timestamp"], utc=True, format="ISO8601")
    event_time = ts.astype("int64").to_numpy() / 1e9
    on_day = (ts.dt.strftime("%Y-%m-%d") == CAPTURE_DAYS[day]).to_numpy()
    off = int((~on_day).sum())
    report.rows_off_day[day] = off
    if off > DAY_TOLERANCE * len(df):
        raise DataValidationError(
            [
                f"{day}: {off} of {len(df)} timestamps are not on "
                f"{CAPTURE_DAYS[day]} UTC (timezone or AM/PM problem?)"
            ]
        )
    mapped = [map_label(str(v)) for v in df["Label"]]
    family = np.array([m[0] for m in mapped], dtype=object)
    attempted = np.array([m[1] for m in mapped], dtype=bool)
    if "Attempted Category" in df.columns:
        category = (
            pd.to_numeric(df["Attempted Category"], errors="coerce")
            .fillna(-1)
            .astype(np.int8)
            .to_numpy()
        )
    else:  # older releases: derive from the label
        category = np.where(attempted, 0, -1).astype(np.int8)

    drop = {*IDENTIFIERS, "Timestamp", "Label", "Attempted Category"}
    features = {}
    for col in df.columns:
        if col in drop:
            continue
        values = pd.to_numeric(df[col], errors="coerce").astype(np.float64)
        values = values.replace([np.inf, -np.inf], np.nan)
        features[NUMERIC_PREFIX + normalise_name(col)] = values.to_numpy()
    out = pd.DataFrame(features)
    out.insert(0, "event_time", event_time)
    out.insert(1, "family", family)
    out.insert(2, "label_raw", df["Label"].astype(str).str.strip().to_numpy())
    out.insert(3, "attempted", attempted)
    out.insert(4, "attempted_category", category)
    return out.loc[on_day].reset_index(drop=True)


def _apply_attempted_policy(
    df: pd.DataFrame, policy: AttemptedPolicy, report: CicEtlReport
) -> pd.DataFrame:
    att = df["attempted"].to_numpy()
    counts = df.loc[att, "family"].value_counts()
    report.attempted = {str(k): int(v) for k, v in counts.items()}
    report.attempted_policy = policy
    if policy == "drop":
        df = df.loc[~att].reset_index(drop=True)
    elif policy == "benign":
        df.loc[att, "family"] = "BENIGN"
    elif policy != "attack":
        raise ValueError(f"unknown attempted_policy {policy!r}")
    df["y"] = (df["family"] != "BENIGN").astype(np.int8)
    return df.drop(columns=["attempted"])


def _dedup(df: pd.DataFrame, report: CicEtlReport) -> pd.DataFrame:
    feats = [c for c in df.columns if c.startswith(NUMERIC_PREFIX)]
    second = np.floor(df["event_time"].to_numpy())
    key = df[[*feats, "label_raw"]].assign(_second=second)
    dup = key.duplicated(keep="first").to_numpy()
    report.duplicates_removed = int(dup.sum())
    return df.loc[~dup].reset_index(drop=True)


def _impute(
    df: pd.DataFrame, warmup: WarmupSpec, report: CicEtlReport
) -> pd.DataFrame:
    feats = [c for c in df.columns if c.startswith(NUMERIC_PREFIX)]
    warm = warmup_mask(df["event_time"].to_numpy(), warmup)
    if not warm.any():
        raise DataValidationError(["warm-up slice is empty"])
    medians = df.loc[warm, feats].median(skipna=True)
    for col in feats:
        n = int(df[col].isna().sum())
        if n:
            report.nan_imputed[col] = n
        med = float(medians[col]) if pd.notna(medians[col]) else 0.0
        report.imputation_medians[col] = med
        df[col] = df[col].fillna(med)
    return df


def run_cic_etl(
    raw_dir: Path,
    out_dir: Path,
    *,
    warmup: WarmupSpec,
    attempted_policy: AttemptedPolicy = "benign",
    dedup: bool = True,
    min_family_flows: int = 1000,
) -> CicEtlReport:
    """Run the CIC-IDS2017 ETL end to end.

    Args:
        raw_dir: Directory holding the weekday CSVs (searched recursively).
        out_dir: ``data/processed/cicids2017``.
        warmup: Warm-up slice used to fit the imputation medians.
        attempted_policy: ``benign`` (default, as the dataset authors
            recommend), ``attack`` or ``drop`` (ablation A-ATT).
        dedup: Remove exact duplicates within the same second.
        min_family_flows: Eligibility threshold for per-onset analysis
            (pre-registration §4.2, OD-4).

    Returns:
        The ETL report (also written to ``etl_report.json``).
    """
    report = CicEtlReport()
    frames = []
    for day, path in discover_day_files(raw_dir).items():
        raw = _read_day(path)
        report.rows_read[day] = len(raw)
        frames.append(_transform_day(raw, day, report))
        log.info("%s: %d rows", day, len(raw))
    df = pd.concat(frames, ignore_index=True)
    df = _apply_attempted_policy(df, attempted_policy, report)
    if dedup:
        df = _dedup(df, report)
    df = _impute(df, warmup, report)
    df = finalise_frame(df)
    report.rows_written = len(df)
    onsets = compute_onsets(
        df, warmup=warmup, min_flows=min_family_flows, expected_day=EXPECTED_DAY
    )
    write_dataset(
        df,
        "cicids2017",
        out_dir,
        partition="day",
        extra_files={
            "etl_report.json": asdict(report),
            "drift_onsets.json": onsets,
            "stats.json": compute_stats(df, warmup=warmup),
        },
    )
    return report
