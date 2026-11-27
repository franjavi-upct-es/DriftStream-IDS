# src/driftstream/data/splits.py
"""Warm-up / streaming split (ARCHITECTURE.md §8.5).

The warm-up slice is fully labelled and used offline: to fit the initial
model and, in ETL, to compute imputation statistics. Nothing computed on
the warm-up slice may look at the streaming phase.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

__all__ = ["WarmupSpec", "warmup_mask"]

_DAY = 86_400.0


@dataclass(frozen=True, slots=True)
class WarmupSpec:
    """How to select the warm-up slice.

    Exactly one of the two attributes is set.

    Attributes:
        days: Explicit UTC calendar days (``YYYY-MM-DD``), e.g. Monday and
            Tuesday for CIC-IDS2017.
        first_days: The first N days after the earliest event (Kyoto).
    """

    days: tuple[str, ...] | None = None
    first_days: int | None = None

    def __post_init__(self) -> None:
        if (self.days is None) == (self.first_days is None):
            raise ValueError("set exactly one of days and first_days")
        if self.first_days is not None and self.first_days < 1:
            raise ValueError("first_days must be >= 1")

    @classmethod
    def from_config(cls, warmup: dict[str, object]) -> WarmupSpec:
        """Build from a dataset config's ``warmup`` node.

        Args:
            warmup: ``{"days": [...]}`` or ``{"days": N}``.

        Returns:
            The spec (a list means explicit days, an int means first N).
        """
        days = warmup.get("days")
        if isinstance(days, int):
            return cls(first_days=days)
        if isinstance(days, Sequence) and not isinstance(days, str):
            return cls(days=tuple(str(d) for d in days))
        raise ValueError(f"unsupported warmup spec: {warmup!r}")


def warmup_mask(
    event_time: NDArray[np.float64] | pd.Series, spec: WarmupSpec
) -> NDArray[np.bool_]:
    """Return which events belong to the warm-up slice.

    Args:
        event_time: Epoch seconds, UTC.
        spec: Warm-up definition.

    Returns:
        Boolean mask aligned with ``event_time``.
    """
    t = np.asarray(event_time, dtype=np.float64)
    if spec.days is not None:
        day = pd.to_datetime(t, unit="s", utc=True).strftime("%Y-%m-%d")
        mask: NDArray[np.bool_] = np.isin(np.asarray(day), spec.days)
        return mask
    assert spec.first_days is not None
    start = np.nanmin(t) if t.size else 0.0
    out: NDArray[np.bool_] = t < start + spec.first_days * _DAY
    return out
