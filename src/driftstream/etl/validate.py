# src/driftstream/etl/validate.py
"""Post-ETL validation of a processed dataset (T2.5).

Every check returns a failure message or ``None``; all checks run, so a
single report lists every problem. The checks cover the invariants the
simulator and the analysis rely on (ARCHITECTURE.md §15.4): canonical
schema, dense ``flow_id``, monotonic event time, label consistency, no
leakage columns, finite features, warm-up presence, onset plausibility,
partition consistency and file checksums.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from driftstream.core.errors import DataValidationError, SchemaError
from driftstream.data.download import sha256_file
from driftstream.data.features import PROFILE_FILE, load_profile
from driftstream.data.loaders import partition_files
from driftstream.data.schema import (
    LABEL_COLUMNS,
    REQUIRED_COLUMNS,
    feature_columns,
    normalise_name,
    numeric_columns,
    require_columns,
)
from driftstream.data.splits import WarmupSpec, warmup_mask
from driftstream.etl.onsets import ONSETS_FILE
from driftstream.etl.stats import STATS_FILE

__all__ = ["FORBIDDEN", "ValidationReport", "validate_dataset"]

#: Raw column names that must never reach the processed table.
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "cicids2017": (
        "id",
        "Flow ID",
        "Src IP",
        "Src Port",
        "Dst IP",
        "Timestamp",
    ),
    "kyoto2006": (
        "IDS detection",
        "Malware detection",
        "Ashula detection",
        "Source IP Address",
        "Source Port Number",
        "Destination IP Address",
    ),
}
REQUIRED_FILES = (PROFILE_FILE, ONSETS_FILE, STATS_FILE, "etl_report.json")


@dataclass(slots=True)
class ValidationReport:
    """Outcome of :func:`validate_dataset`.

    Attributes:
        dataset: Dataset name.
        n_rows: Rows in the processed table.
        passed: Names of the checks that passed.
        failures: Check name → failure message.
    """

    dataset: str
    n_rows: int = 0
    passed: list[str] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Whether every check passed."""
        return not self.failures

    def raise_if_failed(self) -> None:
        """Raise :class:`DataValidationError` listing every failure."""
        if self.failures:
            raise DataValidationError(
                [f"{k}: {v}" for k, v in self.failures.items()]
            )


def _load(dataset_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    frames, keys = [], []
    for path in partition_files(dataset_dir):
        part = pd.read_parquet(path)
        keys.extend([path.parent.name.split("=", 1)[1]] * len(part))
        frames.append(part)
    return pd.concat(frames, ignore_index=True), keys


def validate_dataset(  # noqa: PLR0915 (a flat list of checks)
    dataset: str, dataset_dir: Path, *, warmup: WarmupSpec
) -> ValidationReport:
    """Run every post-ETL check on a processed dataset.

    Args:
        dataset: ``cicids2017`` or ``kyoto2006``.
        dataset_dir: ``data/processed/<dataset>``.
        warmup: Warm-up slice definition.

    Returns:
        The report (call :meth:`ValidationReport.raise_if_failed` to fail
        hard).
    """
    if dataset not in FORBIDDEN:
        raise SchemaError(f"unknown dataset {dataset!r}")
    dataset_dir = Path(dataset_dir)
    report = ValidationReport(dataset)
    df, part_keys = _load(dataset_dir)
    report.n_rows = len(df)
    t = df["event_time"].to_numpy()

    def check(name: str, fn: Callable[[], str | None]) -> None:
        try:
            msg = fn()
        except Exception as err:
            msg = f"{type(err).__name__}: {err}"
        if msg:
            report.failures[name] = msg
        else:
            report.passed.append(name)

    def files() -> str | None:
        missing = [f for f in REQUIRED_FILES if not (dataset_dir / f).is_file()]
        return f"missing side files {missing}" if missing else None

    def schema() -> str | None:
        require_columns(df)
        return None

    def flow_ids() -> str | None:
        ok = np.array_equal(df["flow_id"].to_numpy(), np.arange(len(df)))
        return None if ok else "flow_id is not 0..n-1 in file order"

    def time_order() -> str | None:
        if not np.isfinite(t).all():
            return "non-finite event_time"
        bad = int((np.diff(t) < 0).sum())
        return f"{bad} decreasing event_time steps" if bad else None

    def labels() -> str | None:
        y = df["y"].to_numpy()
        if not np.isin(y, [0, 1]).all():
            return "y outside {0, 1}"
        benign = (df["family"] == "BENIGN").to_numpy()
        bad = int(((y == 0) != benign).sum())
        if bad:
            return f"{bad} rows where y disagrees with family"
        if y.min() == y.max():
            return "only one class present"
        return None

    def no_leakage() -> str | None:
        banned = {normalise_name(c) for c in FORBIDDEN[dataset]}
        # Canonical columns are ours (``flow_id`` is not the raw
        # ``Flow ID``); everything else is checked by name and feature name.
        found = [
            c
            for c in df.columns
            if c not in REQUIRED_COLUMNS
            and (c in banned or (c[:2] in {"f_", "c_"} and c[2:] in banned))
        ]
        label_feats = [
            c for c in feature_columns(df.columns) if c in LABEL_COLUMNS
        ]
        found += label_feats
        return f"leakage columns present: {found}" if found else None

    def finite_features() -> str | None:
        num = df[numeric_columns(df.columns)].to_numpy(dtype=np.float64)
        bad = int((~np.isfinite(num)).sum())
        return f"{bad} non-finite feature values" if bad else None

    def warmup_present() -> str | None:
        warm = warmup_mask(t, warmup)
        if not warm.any():
            return "warm-up slice is empty"
        if warm.all():
            return "warm-up covers the whole stream"
        return None

    def partitions() -> str | None:
        fmt = "%Y-%m-%d" if dataset == "cicids2017" else "%Y-%m"
        actual = pd.to_datetime(t, unit="s", utc=True).strftime(fmt)
        bad = int((np.asarray(actual) != np.asarray(part_keys)).sum())
        return f"{bad} rows in the wrong partition" if bad else None

    def profiles() -> str | None:
        for name in ("default", "strict"):
            prof = load_profile(dataset_dir, name)
            absent = [c for c in prof.columns if c not in df.columns]
            if absent:
                return f"profile {name} lists absent columns {absent}"
        return None

    def onsets() -> str | None:
        payload = json.loads((dataset_dir / ONSETS_FILE).read_text())
        fams = payload["families"]
        observed = set(df.loc[df["y"] == 1, "family"].unique())
        if set(fams) != observed:
            return f"onset families {sorted(fams)} != data {sorted(observed)}"
        wrong = [
            f for f, e in fams.items() if e.get("on_expected_day") is False
        ]
        return f"families not on their expected day: {wrong}" if wrong else None

    def checksums() -> str | None:
        listing = dataset_dir / "CHECKSUMS.sha256"
        if not listing.is_file():
            return "CHECKSUMS.sha256 missing"
        bad = []
        for line in listing.read_text().splitlines():
            digest, rel = line.split(maxsplit=1)
            path = dataset_dir / rel
            if not path.is_file() or sha256_file(path) != digest:
                bad.append(rel)
        return f"checksum mismatch: {bad}" if bad else None

    for name, fn in [
        ("files", files),
        ("schema", schema),
        ("flow_ids", flow_ids),
        ("time_order", time_order),
        ("labels", labels),
        ("no_leakage", no_leakage),
        ("finite_features", finite_features),
        ("warmup", warmup_present),
        ("partitions", partitions),
        ("feature_profiles", profiles),
        ("onsets", onsets),
        ("checksums", checksums),
    ]:
        check(name, fn)
    return report
