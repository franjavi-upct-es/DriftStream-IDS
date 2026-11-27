# src/driftstream/etl/writer.py
"""Shared output stage of both ETL pipelines.

Both datasets end up as one time-sorted pandas frame that goes through the
same steps, so the processed layout is identical whatever engine produced
it (pandas for CIC-IDS2017, PySpark for Kyoto 2006+):

1. stable sort by ``event_time`` and dense ``flow_id`` (0 .. n-1);
2. canonical dtypes (``float32`` numeric features, ``int8`` label);
3. Parquet partitioned by ``day`` or ``month`` (zstd, ~128k-row groups);
4. ``feature_profile.json`` and ``CHECKSUMS.sha256`` side files.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from driftstream.data.download import sha256_file
from driftstream.data.features import build_profiles, write_profiles
from driftstream.data.loaders import FLOWS_DIR
from driftstream.data.schema import (
    categorical_columns,
    numeric_columns,
    require_columns,
)

__all__ = ["FLOWS_DIR", "finalise_frame", "write_dataset"]

ROW_GROUP_SIZE = 131_072
Partition = Literal["day", "month"]


def finalise_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by event time, assign ``flow_id`` and cast canonical dtypes.

    The sort is stable, so ties keep their input order (deterministic for
    a deterministic input order).

    Args:
        df: Frame with ``event_time``, ``y``, ``family``, ``label_raw`` and
            feature columns; any existing ``flow_id`` is replaced.

    Returns:
        A new frame, ``flow_id`` first, ready to write.
    """
    out = df.sort_values("event_time", kind="mergesort").reset_index(drop=True)
    out = out.drop(columns=["flow_id"], errors="ignore")
    out.insert(0, "flow_id", np.arange(len(out), dtype=np.int64))
    out["event_time"] = out["event_time"].astype(np.float64)
    out["y"] = out["y"].astype(np.int8)
    for col in ("family", "label_raw"):
        out[col] = out[col].astype(str)
    for col in numeric_columns(out.columns):
        out[col] = out[col].astype(np.float32)
    for col in categorical_columns(out.columns):
        out[col] = out[col].astype(str)
    require_columns(out)
    return out


def _partition_values(event_time: pd.Series, partition: Partition) -> pd.Series:
    ts = pd.to_datetime(event_time, unit="s", utc=True)
    fmt = "%Y-%m-%d" if partition == "day" else "%Y-%m"
    return ts.dt.strftime(fmt)


def write_dataset(
    df: pd.DataFrame,
    dataset: str,
    out_dir: Path,
    partition: Partition,
    extra_files: dict[str, object] | None = None,
) -> Path:
    """Write a finalised frame and its side files.

    Any previous ``flows.parquet`` directory is replaced, so a re-run never
    mixes old and new partitions.

    Args:
        df: Output of :func:`finalise_frame`.
        dataset: Dataset name (selects the feature profiles).
        out_dir: ``data/processed/<dataset>``.
        partition: ``"day"`` (CIC) or ``"month"`` (Kyoto).
        extra_files: JSON side files to write, ``{file name: payload}``.

    Returns:
        Path of the ``flows.parquet`` directory.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    flows = out_dir / FLOWS_DIR
    if flows.exists():
        shutil.rmtree(flows)
    keys = _partition_values(df["event_time"], partition)
    # Keys are increasing because df is time-sorted, so partition order on
    # disk is also time order.
    for key in pd.unique(keys):
        part = df[keys == key]
        part_dir = flows / f"{partition}={key}"
        part_dir.mkdir(parents=True)
        table = pa.Table.from_pandas(part, preserve_index=False)
        pq.write_table(
            table,
            part_dir / "part-0.parquet",
            compression="zstd",
            row_group_size=ROW_GROUP_SIZE,
        )
    write_profiles(dataset, build_profiles(dataset, df.columns), out_dir)
    for name, payload in (extra_files or {}).items():
        (out_dir / name).write_text(
            json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
        )
    _write_checksums(out_dir)
    return flows


def _write_checksums(out_dir: Path) -> None:
    lines = [
        f"{sha256_file(p)}  {p.relative_to(out_dir).as_posix()}"
        for p in sorted(out_dir.rglob("*"))
        if p.is_file() and p.name != "CHECKSUMS.sha256"
    ]
    (out_dir / "CHECKSUMS.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
