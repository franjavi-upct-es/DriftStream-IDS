# src/driftstream/analysis/eda.py
"""Exploratory statistics of processed datasets (ROADMAP T2.7).

Pure functions over a processed frame; the notebooks in ``notebooks/``
only call them and draw. They describe what the theory needs from each
stream: the arrival rate ``λ(t)``, the attack share over time, when each
family appears, and how much the feature distributions move between
periods (virtual drift, ARCHITECTURE.md §3.5).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

__all__ = [
    "arrival_rate",
    "attack_share",
    "family_timeline",
    "feature_shift",
    "period_keys",
]


def _bins(event_time: pd.Series, bin_seconds: float) -> pd.Series:
    if bin_seconds <= 0:
        raise ValueError(f"bin_seconds must be > 0, got {bin_seconds}")
    bins: pd.Series = np.floor(event_time / bin_seconds) * bin_seconds
    return bins


def arrival_rate(df: pd.DataFrame, bin_seconds: float = 3600.0) -> pd.Series:
    """Flows per second of event time in each non-empty bin.

    Args:
        df: Processed frame with ``event_time``.
        bin_seconds: Bin width, seconds.

    Returns:
        Rate indexed by the UTC start of each bin.
    """
    bins = _bins(df["event_time"], bin_seconds)
    rate = bins.groupby(bins).size() / bin_seconds
    rate.index = pd.to_datetime(rate.index, unit="s", utc=True)
    rate.name = "flows_per_s"
    return rate


def attack_share(df: pd.DataFrame, bin_seconds: float = 3600.0) -> pd.Series:
    """Share of attack flows in each non-empty bin.

    Args:
        df: Processed frame with ``event_time`` and ``y``.
        bin_seconds: Bin width, seconds.

    Returns:
        Share in [0, 1] indexed by the UTC start of each bin.
    """
    bins = _bins(df["event_time"], bin_seconds)
    share = df["y"].groupby(bins).mean()
    share.index = pd.to_datetime(share.index, unit="s", utc=True)
    share.name = "attack_share"
    return share


def family_timeline(df: pd.DataFrame) -> pd.DataFrame:
    """First and last appearance and size of each attack family.

    Args:
        df: Processed frame with ``event_time``, ``y`` and ``family``.

    Returns:
        One row per attack family, ordered by first appearance, with UTC
        ``first``/``last`` timestamps, ``n_flows`` and ``duration_s``.
    """
    attacks = df.loc[df["y"] == 1]
    out: pd.DataFrame = attacks.groupby("family")["event_time"].agg(
        ["min", "max", "size"]
    )
    out.columns = pd.Index(["first", "last", "n_flows"])
    out["duration_s"] = out["last"] - out["first"]
    out = out.sort_values(by="first")
    for col in ("first", "last"):
        out[col] = pd.to_datetime(out[col], unit="s", utc=True)
    return out


def period_keys(df: pd.DataFrame, period: str = "month") -> pd.Series:
    """Calendar period (UTC) of every flow: ``"day"`` or ``"month"``."""
    fmt = {"day": "%Y-%m-%d", "month": "%Y-%m"}[period]
    keys = pd.to_datetime(df["event_time"], unit="s", utc=True).dt.strftime(fmt)
    return pd.Series(keys.to_numpy(), index=df.index, name=period)


def feature_shift(
    df: pd.DataFrame,
    features: Sequence[str],
    *,
    period: str = "month",
    max_samples: int = 20_000,
    seed: int = 0,
) -> pd.DataFrame:
    """Two-sample KS statistic of each feature, per period vs. the first.

    A large statistic means the feature's marginal distribution moved:
    virtual drift that an unsupervised detector could see. Periods are
    subsampled to ``max_samples`` flows so the cost stays bounded.

    Args:
        df: Processed frame.
        features: Numeric feature columns.
        period: ``"day"`` or ``"month"``.
        max_samples: Maximum flows per period in each test.
        seed: Subsampling seed.

    Returns:
        Frame indexed by period with one column per feature (the first
        period is the reference and has statistic 0).
    """
    rng = np.random.default_rng(seed)
    keys = period_keys(df, period)
    periods = sorted(keys.unique())
    if not periods:
        return pd.DataFrame(columns=list(features))

    def sample(key: str) -> pd.DataFrame:
        part = df.loc[keys == key, list(features)]
        if len(part) > max_samples:
            part = part.iloc[rng.choice(len(part), max_samples, replace=False)]
        return part

    ref = sample(periods[0])
    rows = {}
    for key in periods:
        cur = sample(key)
        rows[key] = {
            f: 0.0
            if key == periods[0]
            else float(ks_2samp(ref[f], cur[f]).statistic)
            for f in features
        }
    return pd.DataFrame.from_dict(rows, orient="index")
