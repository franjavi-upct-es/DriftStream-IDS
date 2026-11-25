# src/driftstream/theory/adwin_replay.py
"""Numerical number of post-drift labels ADWIN needs to fire (``n*``).

The prediction replays the exact decision rule of River's ``drift.ADWIN``
(River 0.27, Rust backend) instead of the first-order bound of the paper
(Bifet & Gavaldà 2007). Three properties of the implementation matter and
are reproduced here:

1. **Cut test.** A split of the window ``W`` into an older part ``W0``
   (``n0`` items) and a newer part ``W1`` (``n1`` items) signals a change
   when ``|mean(W0) - mean(W1)| > eps_cut`` with::

       delta' = ln(2 * ln|W| / delta)
       m_inv  = 1 / (n0 - L + 1) + 1 / (n1 - L + 1)
       eps_cut = sqrt(2 * m_inv * var_W * delta') + (2 / 3) * delta' * m_inv

   where ``L`` is ``min_window_length`` and ``var_W`` is the population
   variance of the whole window (``variance / width`` in River).
2. **Candidate splits.** Only bucket boundaries of the exponential
   histogram are tested (``max_buckets`` buckets per size, sizes 1, 2,
   4, ...). The boundaries depend on the window width only.
3. **Check clock.** Splits are tested only when the update counter is a
   multiple of ``clock`` and the width exceeds ``grace_period``.

``tests/unit/test_adwin_replay.py`` verifies (1)-(3) by running a pure
Python port that uses :func:`cut_threshold` side by side with River's
ADWIN and requiring identical alarm indices.

The **mean-field replay** (:func:`n_star`) feeds the rule with *expected*
statistics of a Bernoulli error stream that jumps from ``eps0`` to
``eps1`` after ``n_pre`` items, and averages over the unknown phase of the
check clock. :func:`simulate_detection` gives the Monte Carlo distribution
of the same quantity with River itself, which E0 uses to check the
prediction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "ADWINParams",
    "DetectionSample",
    "bucket_boundaries",
    "cut_threshold",
    "n_star",
    "n_star_by_phase",
    "simulate_detection",
]


@dataclass(frozen=True, slots=True)
class ADWINParams:
    """Parameters of River's ``drift.ADWIN`` (same names and defaults).

    Attributes:
        delta: Confidence parameter of the cut test (dimensionless).
        clock: Number of updates between two change checks.
        max_buckets: Buckets kept per bucket size before merging.
        min_window_length: Minimum size ``L`` of each sub-window, items.
        grace_period: Minimum window width before any check, items.
    """

    delta: float = 0.002
    clock: int = 32
    max_buckets: int = 5
    min_window_length: int = 5
    grace_period: int = 10

    def __post_init__(self) -> None:
        if not 0.0 < self.delta < 1.0:
            raise ValueError(f"delta must be in (0, 1), got {self.delta}")
        if self.clock < 1 or self.max_buckets < 1:
            raise ValueError("clock and max_buckets must be >= 1")
        if self.min_window_length < 1 or self.grace_period < 0:
            raise ValueError("invalid min_window_length or grace_period")


def cut_threshold(
    n0: float,
    n1: float,
    width: float,
    variance: float,
    params: ADWINParams,
) -> float:
    """Return River's ADWIN cut threshold ``eps_cut`` for one split.

    Args:
        n0: Items in the older sub-window ``W0``.
        n1: Items in the newer sub-window ``W1``.
        width: Items in the whole window (``n0 + n1``).
        variance: Population variance of the whole window, in squared
            units of the monitored value.
        params: ADWIN parameters.

    Returns:
        The threshold on ``|mean(W0) - mean(W1)|``, in units of the
        monitored value (error rate for error bits).

    Raises:
        ValueError: If a sub-window is shorter than ``min_window_length``
            or the window is too short for ``ln ln |W|`` to be defined.
    """
    lw = params.min_window_length
    if n0 < lw or n1 < lw:
        raise ValueError("sub-windows must hold >= min_window_length items")
    if width <= math.e:
        raise ValueError("window too short: ln(ln(width)) undefined")
    delta_prime = math.log(2.0 * math.log(width) / params.delta)
    m_inv = 1.0 / (n0 - lw + 1.0) + 1.0 / (n1 - lw + 1.0)
    return (
        math.sqrt(2.0 * m_inv * variance * delta_prime)
        + (2.0 / 3.0) * delta_prime * m_inv
    )


class _BucketCounts:
    """Count-only exponential histogram with River's merge rule.

    ``rows[i]`` is the number of buckets of size ``2**i``. The layout
    depends on the number of inserted items only, never on their values.
    """

    __slots__ = ("max_buckets", "rows", "width")

    def __init__(self, max_buckets: int) -> None:
        self.max_buckets = max_buckets
        self.rows: list[int] = [0]
        self.width = 0

    def insert(self) -> None:
        self.rows[0] += 1
        self.width += 1
        idx = 0
        while self.rows[idx] == self.max_buckets + 1:
            if idx + 1 == len(self.rows):
                self.rows.append(0)
            self.rows[idx] -= 2
            self.rows[idx + 1] += 1
            idx += 1

    def boundaries(self) -> list[int]:
        """Cumulative item counts of ``W0`` at every candidate split."""
        out: list[int] = []
        acc = 0
        for idx in range(len(self.rows) - 1, -1, -1):
            size = 1 << idx
            for _ in range(self.rows[idx]):
                acc += size
                out.append(acc)
        return out[:-1]  # the last boundary would leave W1 empty


def bucket_boundaries(width: int, max_buckets: int = 5) -> list[int]:
    """Return the candidate split points of a window of ``width`` items.

    Args:
        width: Number of items inserted since the last reset.
        max_buckets: River's ``max_buckets``.

    Returns:
        Sizes of ``W0`` (oldest items first) for every split River tests.
    """
    hist = _BucketCounts(max_buckets)
    for _ in range(width):
        hist.insert()
    return hist.boundaries()


def _fires(
    width: int,
    drift_at: NDArray[np.float64],
    eps0: float,
    eps1: float,
    splits: NDArray[np.float64],
    params: ADWINParams,
) -> NDArray[np.bool_]:
    """Cut test on expected statistics, vectorised over phases x splits.

    Uses the same formula as :func:`cut_threshold` (kept scalar there for
    readability and for the River parity test).

    Args:
        width: Current window width, items.
        drift_at: Drift position (pre-drift items) for each phase.
        eps0: Pre-drift error rate.
        eps1: Post-drift error rate.
        splits: Candidate ``W0`` sizes (valid for ``min_window_length``).
        params: ADWIN parameters.

    Returns:
        One boolean per phase: does any split fire?
    """
    d = drift_at[:, None]
    c = splits[None, :]
    n1 = width - c
    mean_w = (eps0 * d + eps1 * (width - d)) / width
    var_w = mean_w * (1.0 - mean_w)  # Bernoulli: population variance
    pre0 = np.minimum(c, d)
    mean0 = (eps0 * pre0 + eps1 * (c - pre0)) / c
    pre1 = np.maximum(d - c, 0.0)
    mean1 = (eps0 * pre1 + eps1 * (n1 - pre1)) / n1
    lw = params.min_window_length
    delta_prime = math.log(2.0 * math.log(width) / params.delta)
    m_inv = 1.0 / (c - lw + 1.0) + 1.0 / (n1 - lw + 1.0)
    eps_cut = (
        np.sqrt(2.0 * m_inv * var_w * delta_prime)
        + (2.0 / 3.0) * delta_prime * m_inv
    )
    fired: NDArray[np.bool_] = np.any(np.abs(mean0 - mean1) > eps_cut, axis=1)
    return fired


@lru_cache(maxsize=4096)
def n_star_by_phase(
    eps0: float,
    eps1: float,
    n_pre: int,
    params: ADWINParams = ADWINParams(),  # frozen, hashable: safe default
    max_post: int = 200_000,
) -> tuple[float, ...]:
    """Mean-field ``n*`` for every phase of the check clock.

    The detector has seen ``n_pre + j`` pre-drift items (``j`` = phase,
    ``0 <= j < clock``) when the error rate jumps from ``eps0`` to
    ``eps1``. Checks happen when the item counter is a multiple of
    ``clock``, as in River when no reset happened since the stream start.

    Args:
        eps0: Pre-drift error rate, in [0, 1].
        eps1: Post-drift error rate, in [0, 1].
        n_pre: Pre-drift items in the window (labels of the random
            substream received before the drift).
        params: ADWIN parameters.
        max_post: Censoring horizon, post-drift items.

    Returns:
        For each phase, the number of post-drift items at the first check
        that fires (``inf`` if none fires within ``max_post``).
    """
    if not (0.0 <= eps0 <= 1.0 and 0.0 <= eps1 <= 1.0):
        raise ValueError("error rates must be in [0, 1]")
    if n_pre < 1:
        raise ValueError("n_pre must be >= 1")
    clock = params.clock
    result = [math.inf] * clock
    if eps0 == eps1:
        return tuple(result)
    hist = _BucketCounts(params.max_buckets)
    pending = np.ones(clock, dtype=bool)
    drift_at = n_pre + np.arange(clock, dtype=np.float64)
    lw = params.min_window_length
    last = n_pre + clock - 1 + max_post
    for _ in range(last):
        hist.insert()
        w = hist.width
        if w % clock or w <= params.grace_period or w <= math.e:
            continue
        active = pending & (drift_at < w)
        if not active.any():
            continue
        raw = np.asarray(hist.boundaries(), dtype=np.float64)
        splits = raw[(raw >= lw) & (w - raw >= lw)]
        if splits.size == 0:
            continue
        idx = np.flatnonzero(active)
        hits = _fires(w, drift_at[idx], eps0, eps1, splits, params)
        for j in idx[hits]:
            result[j] = float(w - drift_at[j])
        pending[idx[hits]] = False
        if not pending.any():
            break
    return tuple(result)


def n_star(
    eps0: float,
    eps1: float,
    n_pre: int,
    params: ADWINParams | None = None,
    max_post: int = 200_000,
) -> float:
    """Expected post-drift labels before ADWIN fires (mean-field).

    The expectation is over a uniformly distributed phase of the check
    clock, so the result already includes the clock term ``c_clock`` of
    ARCHITECTURE.md §4.2.

    Args:
        eps0: Pre-drift error rate, in [0, 1].
        eps1: Post-drift error rate, in [0, 1].
        n_pre: Pre-drift items in the detector window, labels.
        params: ADWIN parameters (River defaults when ``None``).
        max_post: Censoring horizon, labels.

    Returns:
        Expected ``n*`` in labels, or ``inf`` if some phase never fires.
    """
    p = params if params is not None else ADWINParams()
    phases = n_star_by_phase(eps0, eps1, int(n_pre), p, max_post)
    return float(np.mean(phases))


@dataclass(frozen=True, slots=True)
class DetectionSample:
    """Monte Carlo outcome of :func:`simulate_detection`.

    Attributes:
        n_post: Post-drift items at the first alarm, one per trial
            (``inf`` when censored at ``max_post``).
        pre_drift_alarms: False alarms before the drift, one per trial.
    """

    n_post: NDArray[np.float64]
    pre_drift_alarms: NDArray[np.int64]

    @property
    def censored_fraction(self) -> float:
        """Share of trials without an alarm within the horizon."""
        return float(np.mean(~np.isfinite(self.n_post)))

    @property
    def median(self) -> float:
        """Median ``n*`` (``inf`` if at least half the trials censor)."""
        return float(np.median(self.n_post))

    @property
    def mean(self) -> float:
        """Mean ``n*`` over trials that fired."""
        fired = self.n_post[np.isfinite(self.n_post)]
        return float(fired.mean()) if fired.size else math.inf


def simulate_detection(
    eps0: float,
    eps1: float,
    n_pre: int,
    params: ADWINParams | None = None,
    *,
    n_trials: int = 200,
    max_post: int = 50_000,
    rng: np.random.Generator,
) -> DetectionSample:
    """Monte Carlo ``n*`` using River's own ADWIN on Bernoulli error bits.

    Each trial feeds ``n_pre`` bits with mean ``eps0`` and then bits with
    mean ``eps1`` until the first post-drift alarm or ``max_post`` bits.
    Pre-drift false alarms reset River's window, exactly as in a run.

    Args:
        eps0: Pre-drift error rate, in [0, 1].
        eps1: Post-drift error rate, in [0, 1].
        n_pre: Pre-drift bits per trial.
        params: ADWIN parameters (River defaults when ``None``).
        n_trials: Number of independent trials.
        max_post: Censoring horizon, post-drift bits.
        rng: Random generator (from ``driftstream.seeds``).

    Returns:
        Per-trial detection counts and pre-drift false alarms.
    """
    from river.drift import ADWIN  # noqa: PLC0415 (optional heavy import)

    p = params if params is not None else ADWINParams()
    n_post = np.full(n_trials, np.inf)
    false_alarms = np.zeros(n_trials, dtype=np.int64)
    for t in range(n_trials):
        det = ADWIN(
            delta=p.delta,
            clock=p.clock,
            max_buckets=p.max_buckets,
            min_window_length=p.min_window_length,
            grace_period=p.grace_period,
        )
        for bit in (rng.random(n_pre) < eps0).astype(float):
            det.update(bit)
            false_alarms[t] += int(det.drift_detected)
        post = (rng.random(max_post) < eps1).astype(float)
        for i, bit in enumerate(post, start=1):
            det.update(bit)
            if det.drift_detected:
                n_post[t] = float(i)
                break
    return DetectionSample(n_post=n_post, pre_drift_alarms=false_alarms)
