# src/driftstream/data/schema.py
"""Canonical schema of processed flow tables (ARCHITECTURE.md §8.2).

Every processed dataset is one time-ordered table with these columns:

========== ========= ===================================================
Column     Type      Meaning
========== ========= ===================================================
flow_id    int64     Dense id assigned after time-sorting (0 .. n-1)
event_time float64   Epoch seconds, UTC
y          int8      Ground truth: 0 benign, 1 attack
family     string    Normalised family name (``BENIGN`` for benign)
label_raw  string    Original label, for traceability
f_*        numeric   Numeric features (``float32``)
c_*        string    Categorical features
========== ========= ===================================================

plus dataset-specific metadata columns that are **never** features (for
example ``attempted_category`` in CIC-IDS2017). Partition columns
(``day`` for CIC, ``month`` for Kyoto) exist only in the Parquet layout.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd

from driftstream.core.errors import SchemaError

__all__ = [
    "CATEGORICAL_PREFIX",
    "LABEL_COLUMNS",
    "NUMERIC_PREFIX",
    "REQUIRED_COLUMNS",
    "categorical_columns",
    "feature_columns",
    "normalise_name",
    "numeric_columns",
    "require_columns",
]

NUMERIC_PREFIX = "f_"
CATEGORICAL_PREFIX = "c_"

#: Columns every processed table must have, with their pandas dtype kind.
REQUIRED_COLUMNS: dict[str, str] = {
    "flow_id": "i",
    "event_time": "f",
    "y": "i",
    "family": "O",
    "label_raw": "O",
}

#: Columns that carry ground truth: only the oracle and the evaluator may
#: read them (ARCHITECTURE.md §3.2).
LABEL_COLUMNS: frozenset[str] = frozenset(
    {"y", "family", "label_raw", "attempted_category"}
)


def normalise_name(raw: str) -> str:
    """Turn a raw column name into ``snake_case``.

    Args:
        raw: Column name as found in the raw file, e.g. ``"Down/Up Ratio"``.

    Returns:
        Lower-case name with non-alphanumerics collapsed to ``_``, e.g.
        ``"down_up_ratio"``.
    """
    name = re.sub(r"[^0-9a-zA-Z]+", "_", raw.strip()).strip("_").lower()
    if not name:
        raise SchemaError(f"column name {raw!r} has no alphanumerics")
    return name


def numeric_columns(columns: Iterable[str]) -> list[str]:
    """Return the numeric feature columns (``f_*``) in their order."""
    return [c for c in columns if c.startswith(NUMERIC_PREFIX)]


def categorical_columns(columns: Iterable[str]) -> list[str]:
    """Return the categorical feature columns (``c_*``) in their order."""
    return [c for c in columns if c.startswith(CATEGORICAL_PREFIX)]


def feature_columns(columns: Iterable[str]) -> list[str]:
    """Return every feature column (numeric first, then categorical)."""
    cols = list(columns)
    return numeric_columns(cols) + categorical_columns(cols)


def require_columns(df: pd.DataFrame) -> None:
    """Check that ``df`` has the canonical columns with the right kinds.

    Args:
        df: Processed table.

    Raises:
        SchemaError: If a required column is missing, has the wrong dtype
            kind, or a feature column shadows a label column.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"missing required columns: {missing}")
    for col, kind in REQUIRED_COLUMNS.items():
        actual = df[col].dtype.kind
        if kind == "O":
            ok = actual in {"O", "U", "T"} or pd.api.types.is_string_dtype(
                df[col]
            )
        else:
            ok = actual == kind
        if not ok:
            raise SchemaError(f"{col}: expected kind {kind!r}, got {actual!r}")
    leaked = [c for c in feature_columns(df.columns) if c in LABEL_COLUMNS]
    if leaked:
        raise SchemaError(f"label columns used as features: {leaked}")
