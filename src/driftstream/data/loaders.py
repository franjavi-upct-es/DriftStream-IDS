# src/driftstream/data/loaders.py
"""Readers for processed datasets.

Phase 2 provides the table-level reader used by validation and the EDA
notebooks. The time-ordered ``Flow`` iterator used by the simulator is
added in Phase 3 (ROADMAP T3.8).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from driftstream.core.errors import SchemaError

__all__ = ["FLOWS_DIR", "load_frame", "partition_files"]

FLOWS_DIR = "flows.parquet"


def partition_files(dataset_dir: Path) -> list[Path]:
    """Return the Parquet part files in time order.

    Partition directories are named ``day=YYYY-MM-DD`` or ``month=YYYY-MM``,
    so lexicographic order is time order.

    Args:
        dataset_dir: ``data/processed/<dataset>``.

    Raises:
        SchemaError: If there is no processed data.
    """
    root = Path(dataset_dir) / FLOWS_DIR
    files = sorted(root.glob("*=*/part-*.parquet"))
    if not files:
        raise SchemaError(f"no processed data under {root}: run the ETL")
    return files


def load_frame(
    dataset_dir: Path, columns: Sequence[str] | None = None
) -> pd.DataFrame:
    """Load a processed dataset as one time-ordered frame.

    Args:
        dataset_dir: ``data/processed/<dataset>``.
        columns: Optional subset of columns.

    Returns:
        The concatenated partitions, in time order.
    """
    cols = list(columns) if columns is not None else None
    tables = [
        pq.read_table(p, columns=cols) for p in partition_files(dataset_dir)
    ]
    frame: pd.DataFrame = pa.concat_tables(tables).to_pandas()
    return frame
