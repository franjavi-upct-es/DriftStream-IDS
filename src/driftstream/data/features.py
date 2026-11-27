# src/driftstream/data/features.py
"""Feature profiles: ``default`` and ``strict`` (ARCHITECTURE.md §8.4).

``strict`` removes the port and protocol features, which can act as
shortcuts in lab datasets (Arp et al. 2022): ablation A-FEAT. Profiles are
computed by the ETL from the processed columns and stored in
``feature_profile.json`` next to the data, so every run reads exactly the
same feature list.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from driftstream.core.errors import SchemaError
from driftstream.data.schema import categorical_columns, numeric_columns

__all__ = [
    "PROFILE_FILE",
    "SHORTCUT_FEATURES",
    "FeatureProfile",
    "build_profiles",
    "load_profile",
    "write_profiles",
]

PROFILE_FILE = "feature_profile.json"

#: Features removed by the ``strict`` profile, per dataset.
SHORTCUT_FEATURES: dict[str, frozenset[str]] = {
    "cicids2017": frozenset({"f_dst_port", "f_protocol"}),
    "kyoto2006": frozenset({"f_destination_port_number"}),
}


@dataclass(frozen=True, slots=True)
class FeatureProfile:
    """Ordered feature lists of one profile.

    Attributes:
        name: Profile name (``default`` or ``strict``).
        numeric: Numeric feature columns (``f_*``).
        categorical: Categorical feature columns (``c_*``).
    """

    name: str
    numeric: tuple[str, ...]
    categorical: tuple[str, ...]

    @property
    def columns(self) -> tuple[str, ...]:
        """All feature columns, numeric first."""
        return self.numeric + self.categorical


def build_profiles(
    dataset: str, columns: Iterable[str]
) -> dict[str, FeatureProfile]:
    """Derive the ``default`` and ``strict`` profiles from table columns.

    Args:
        dataset: Dataset name (key of :data:`SHORTCUT_FEATURES`).
        columns: Columns of the processed table.

    Returns:
        Profiles keyed by name.

    Raises:
        SchemaError: If the dataset is unknown or a shortcut feature the
            ``strict`` profile should remove is absent (a renamed column
            would otherwise silently weaken the ablation).
    """
    if dataset not in SHORTCUT_FEATURES:
        raise SchemaError(f"no feature profiles defined for {dataset!r}")
    cols = list(columns)
    num, cat = numeric_columns(cols), categorical_columns(cols)
    shortcuts = SHORTCUT_FEATURES[dataset]
    absent = sorted(shortcuts - set(cols))
    if absent:
        raise SchemaError(f"shortcut features missing from table: {absent}")
    return {
        "default": FeatureProfile("default", tuple(num), tuple(cat)),
        "strict": FeatureProfile(
            "strict",
            tuple(c for c in num if c not in shortcuts),
            tuple(c for c in cat if c not in shortcuts),
        ),
    }


def write_profiles(
    dataset: str, profiles: dict[str, FeatureProfile], out_dir: Path
) -> Path:
    """Write ``feature_profile.json`` into ``out_dir``.

    Args:
        dataset: Dataset name.
        profiles: Output of :func:`build_profiles`.
        out_dir: Processed dataset directory.

    Returns:
        Path of the written file.
    """
    payload = {
        "dataset": dataset,
        "strict_removes": sorted(SHORTCUT_FEATURES[dataset]),
        "profiles": {
            name: {
                "numeric": list(p.numeric),
                "categorical": list(p.categorical),
            }
            for name, p in profiles.items()
        },
    }
    path = out_dir / PROFILE_FILE
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_profile(dataset_dir: Path, name: str = "default") -> FeatureProfile:
    """Load one profile from a processed dataset directory.

    Args:
        dataset_dir: ``data/processed/<dataset>``.
        name: Profile name.

    Returns:
        The profile.

    Raises:
        SchemaError: If the file or the profile does not exist.
    """
    path = Path(dataset_dir) / PROFILE_FILE
    if not path.is_file():
        raise SchemaError(f"{path} not found: run the ETL first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        spec = payload["profiles"][name]
    except KeyError as err:
        raise SchemaError(f"unknown feature profile {name!r}") from err
    return FeatureProfile(
        name, tuple(spec["numeric"]), tuple(spec["categorical"])
    )
