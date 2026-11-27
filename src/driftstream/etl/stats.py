# src/driftstream/etl/stats.py
"""Dataset statistics written to ``stats.json`` (T2.5).

The statistics feed the theory (``λ`` per period), the data cards and the
EDA notebooks: counts per period and family, class ratio per period, the
arrival rate and the warm-up size.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from driftstream.data.splits import WarmupSpec, warmup_mask

__all__ = ["STATS_FILE", "compute_stats"]

STATS_FILE = "stats.json"
Period = Literal["day", "month"]
RateBin = Literal["hour", "day"]

_BIN_SECONDS = {"hour": 3600.0, "day": 86_400.0}


def compute_stats(
    df: pd.DataFrame,
    *,
    warmup: WarmupSpec,
    period: Period = "day",
    rate_bin: RateBin = "hour",
) -> dict[str, object]:
    """Compute summary statistics of a processed table.

    Args:
        df: Processed table (``event_time``, ``y``, ``family``).
        warmup: Warm-up slice definition.
        period: Grouping for counts and class ratios.
        rate_bin: Bin width for the arrival rate ``λ``.

    Returns:
        JSON-serialisable statistics. Rates are flows per second of event
        time, averaged within each non-empty bin.
    """
    t = df["event_time"].to_numpy()
    ts = pd.to_datetime(t, unit="s", utc=True)
    fmt = "%Y-%m-%d" if period == "day" else "%Y-%m"
    keys = pd.Series(ts.strftime(fmt), index=df.index)
    counts = (
        df.groupby([keys, df["family"]])
        .size()
        .unstack(fill_value=0)
        .astype(int)
    )
    per_period = {
        str(k): {str(f): int(v) for f, v in row.items() if v}
        for k, row in counts.iterrows()
    }
    ratio = df.groupby(keys)["y"].mean()
    width = _BIN_SECONDS[rate_bin]
    bins = np.floor(t / width) * width
    rate = pd.Series(1.0, index=bins).groupby(level=0).sum() / width
    warm = warmup_mask(t, warmup)
    span = float(t.max() - t.min()) if len(t) else 0.0
    return {
        "n_flows": len(df),
        "n_attack": int(df["y"].sum()),
        "attack_share": float(df["y"].mean()) if len(df) else 0.0,
        "families": {
            str(k): int(v) for k, v in df["family"].value_counts().items()
        },
        "first_event_utc": ts.min().isoformat() if len(t) else None,
        "last_event_utc": ts.max().isoformat() if len(t) else None,
        "span_seconds": span,
        "mean_rate_flows_per_s": float(len(t) / span) if span > 0 else None,
        "warmup": {
            "n_flows": int(warm.sum()),
            "n_attack": int(df.loc[warm, "y"].sum()),
        },
        f"counts_per_{period}": per_period,
        f"attack_share_per_{period}": {
            str(k): float(v) for k, v in ratio.items()
        },
        f"rate_per_{rate_bin}": {
            pd.Timestamp(float(k), unit="s", tz="UTC").isoformat(): float(v)
            for k, v in zip(rate.index.to_numpy(), rate.to_numpy(), strict=True)
        },
    }
