# src/driftstream/etl/onsets.py
"""Drift onsets: first appearance of each attack family (T2.5).

Onsets are **computed from the data**, never assumed. For CIC-IDS2017 the
first flow of each family is the onset `t0` used by the detection-delay
analysis. A family is *eligible* for per-onset analysis when it has at
least ``min_flows`` flows and its onset lies after the warm-up slice
(pre-registration §4.2, OD-4): families seen during warm-up are already
known to the initial model.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from driftstream.data.splits import WarmupSpec, warmup_mask

__all__ = ["ONSETS_FILE", "compute_onsets"]

ONSETS_FILE = "drift_onsets.json"


def compute_onsets(
    df: pd.DataFrame,
    *,
    warmup: WarmupSpec,
    min_flows: int,
    expected_day: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Compute per-family onsets from a processed table.

    Args:
        df: Processed table with ``event_time``, ``y`` and ``family``.
        warmup: Warm-up slice definition.
        min_flows: Minimum flows for per-onset eligibility.
        expected_day: Optional family → expected UTC day (``YYYY-MM-DD``),
            for the plausibility check of T2.5.

    Returns:
        JSON-serialisable mapping with one entry per attack family,
        ordered by onset time.
    """
    attacks = df.loc[df["y"].to_numpy() == 1, ["event_time", "family"]]
    warm = warmup_mask(df["event_time"].to_numpy(), warmup)
    warm_end = (
        float(df.loc[warm, "event_time"].max()) if warm.any() else -np.inf
    )
    grouped = attacks.groupby("family")["event_time"].agg(["min", "size"])
    families: dict[str, dict[str, object]] = {}
    for fam, row in grouped.sort_values("min").iterrows():
        t0 = float(row["min"])
        n = int(row["size"])
        day = pd.Timestamp(t0, unit="s", tz="UTC").strftime("%Y-%m-%d")
        in_warmup = t0 <= warm_end
        entry: dict[str, object] = {
            "onset_event_time": t0,
            "onset_utc": pd.Timestamp(t0, unit="s", tz="UTC").isoformat(),
            "day": day,
            "n_flows": n,
            "in_warmup": in_warmup,
            "eligible_per_onset": (n >= min_flows) and not in_warmup,
        }
        if expected_day is not None and fam in expected_day:
            entry["expected_day"] = expected_day[fam]
            entry["on_expected_day"] = day == expected_day[fam]
        families[str(fam)] = entry
    return {
        "onsets_known": expected_day is not None,
        "min_family_flows": min_flows,
        "warmup_end_event_time": None if warm_end == -np.inf else warm_end,
        "families": families,
    }
