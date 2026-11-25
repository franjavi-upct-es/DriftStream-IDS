# tests/unit/test_adwin_replay.py
"""ADWIN replay: River parity of the cut rule, n* monotonicity, MC check."""

from __future__ import annotations

import math
import random
from itertools import pairwise

import numpy as np
import pytest
from river.drift import ADWIN

from driftstream.theory.adwin_replay import (
    ADWINParams,
    bucket_boundaries,
    cut_threshold,
    n_star,
    n_star_by_phase,
    simulate_detection,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------
# A pure-Python port of ADWIN that uses `cut_threshold`. If it raises
# alarms on exactly the same indices as River's (Rust) ADWIN, then the cut
# test, the bucket layout and the check clock replayed by `n_star` are the
# ones River really uses.
# --------------------------------------------------------------------------
class _Row:
    def __init__(self, cap: int) -> None:
        self.tot = [0.0] * (cap + 1)
        self.var = [0.0] * (cap + 1)
        self.n = 0

    def insert(self, t: float, v: float) -> None:
        self.tot[self.n], self.var[self.n] = t, v
        self.n += 1

    def drop(self, k: int) -> None:
        self.tot = self.tot[k:] + [0.0] * k
        self.var = self.var[k:] + [0.0] * k
        self.n -= k


class _PortADWIN:
    def __init__(self, p: ADWINParams) -> None:
        self.p = p
        self.reset()

    def reset(self) -> None:
        self.rows = [_Row(self.p.max_buckets)]
        self.total = self.var = self.width = 0.0
        self.tick = 0

    def update(self, x: float) -> bool:
        self.rows[0].insert(x, 0.0)
        if self.width > 0:
            mu = self.total / self.width
            self.var += self.width * (x - mu) ** 2 / (self.width + 1)
        self.width += 1
        self.total += x
        self._compress()
        return self._detect()

    def _compress(self) -> None:
        idx = 0
        while idx < len(self.rows):
            b = self.rows[idx]
            if b.n != self.p.max_buckets + 1:
                break
            if idx + 1 == len(self.rows):
                self.rows.append(_Row(self.p.max_buckets))
            nb, n = self.rows[idx + 1], 2.0**idx
            temp = n * n * (b.tot[0] / n - b.tot[1] / n) ** 2 / (2 * n)
            nb.insert(b.tot[0] + b.tot[1], b.var[0] + b.var[1] + temp)
            b.drop(2)
            if nb.n <= self.p.max_buckets:
                break
            idx += 1

    def _delete(self) -> None:
        b, n = self.rows[-1], 2.0 ** (len(self.rows) - 1)
        u, v = b.tot[0], b.var[0]
        self.width -= n
        self.total -= u
        mu_w = self.total / self.width
        self.var -= v + n * self.width * (u / n - mu_w) ** 2 / (n + self.width)
        b.drop(1)
        if b.n == 0:
            self.rows.pop()

    def _detect(self) -> bool:
        change = False
        self.tick += 1
        lw = self.p.min_window_length
        if self.tick % self.p.clock or self.width <= self.p.grace_period:
            return False
        reduce = True
        while reduce:
            reduce = stop = False
            n0, n1, u0, u1 = 0.0, self.width, 0.0, self.total
            for idx in range(len(self.rows) - 1, -1, -1):
                if stop:
                    break
                b = self.rows[idx]
                for k in range(b.n):
                    n2 = 2.0**idx
                    n0, n1 = n0 + n2, n1 - n2
                    u0, u1 = u0 + b.tot[k], u1 - b.tot[k]
                    if n1 == 0:
                        stop = True
                        break
                    if n0 < lw or n1 < lw:
                        continue
                    eps = cut_threshold(
                        n0, n1, self.width, self.var / self.width, self.p
                    )
                    if abs(u0 / n0 - u1 / n1) > eps:
                        reduce = change = True
                        self._delete()
                        stop = True
                        break
        return change


def _stream(seed: int) -> list[float]:
    rng = random.Random(seed)
    out: list[float] = []
    # Distinct error rates per segment, so every stream has real changes.
    for p in rng.sample([0.05, 0.1, 0.3, 0.5], k=4):
        n = rng.randint(300, 2500)
        out += [1.0 if rng.random() < p else 0.0 for _ in range(n)]
    return out


PARAMS = [
    ADWINParams(),
    ADWINParams(clock=1),
    ADWINParams(delta=0.02, clock=8),
    ADWINParams(min_window_length=20, grace_period=50),
]


@pytest.mark.parametrize("params", PARAMS, ids=repr)
@pytest.mark.parametrize("seed", range(3))
def test_port_raises_alarms_on_the_same_indices_as_river(
    params: ADWINParams, seed: int
) -> None:
    river = ADWIN(
        delta=params.delta,
        clock=params.clock,
        max_buckets=params.max_buckets,
        min_window_length=params.min_window_length,
        grace_period=params.grace_period,
    )
    port = _PortADWIN(params)
    a_river: list[int] = []
    a_port: list[int] = []
    reset_next = False
    for i, x in enumerate(_stream(seed)):
        river.update(x)
        if river.drift_detected:
            a_river.append(i)
        if reset_next:  # River's wrapper resets on the next update
            port.reset()
            reset_next = False
        if port.update(x):
            a_port.append(i)
            reset_next = True
    assert a_river, "stream should contain detectable changes"
    assert a_port == a_river


# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------
def test_cut_threshold_matches_hand_computation() -> None:
    p = ADWINParams(delta=0.002, min_window_length=5)
    n0, n1, w, var = 1000.0, 100.0, 1100.0, 0.09
    dp = math.log(2 * math.log(w) / 0.002)
    m_inv = 1 / (n0 - 4) + 1 / (n1 - 4)
    expected = math.sqrt(2 * m_inv * var * dp) + 2 / 3 * dp * m_inv
    assert cut_threshold(n0, n1, w, var, p) == pytest.approx(expected)


def test_cut_threshold_rejects_short_subwindows() -> None:
    with pytest.raises(ValueError, match="min_window_length"):
        cut_threshold(3, 100, 103, 0.1, ADWINParams())


def test_bucket_boundaries_cover_the_window_from_the_oldest_item() -> None:
    splits = bucket_boundaries(1000)
    assert splits == sorted(splits)
    assert splits[0] > 0 and splits[-1] < 1000
    # Recent items sit in size-1 buckets: the newest splits are 1 apart.
    assert splits[-1] - splits[-2] == 1


def test_params_validation() -> None:
    with pytest.raises(ValueError, match="delta"):
        ADWINParams(delta=1.5)


# --------------------------------------------------------------------------
# n* properties (ROADMAP T1.2 acceptance)
# --------------------------------------------------------------------------
def test_no_change_never_fires() -> None:
    assert math.isinf(n_star(0.1, 0.1, 1000))


@pytest.mark.parametrize("n_pre", [500, 5000])
def test_n_star_decreases_with_the_error_jump(n_pre: int) -> None:
    values = [n_star(0.05, 0.05 + d, n_pre) for d in (0.05, 0.1, 0.2, 0.3)]
    assert all(a >= b for a, b in pairwise(values))
    assert values[0] > values[-1]


def test_n_star_increases_as_delta_decreases() -> None:
    values = [
        n_star(0.05, 0.2, 5000, ADWINParams(delta=d))
        for d in (0.2, 0.02, 0.002, 0.0002)
    ]
    assert all(a <= b for a, b in pairwise(values))
    assert values[0] < values[-1]


def test_n_star_has_one_value_per_clock_phase() -> None:
    phases = n_star_by_phase(0.05, 0.25, 2000, ADWINParams(clock=16))
    assert len(phases) == 16
    assert all(math.isfinite(v) and v > 0 for v in phases)


def test_n_star_is_censored_beyond_the_horizon() -> None:
    assert math.isinf(n_star(0.10, 0.11, 1000, max_post=500))


def test_mean_field_matches_river_monte_carlo() -> None:
    rng = np.random.default_rng(7)
    mc = simulate_detection(0.05, 0.25, 5000, n_trials=120, rng=rng)
    assert mc.censored_fraction == 0.0
    assert n_star(0.05, 0.25, 5000) == pytest.approx(mc.mean, rel=0.2)


def test_vectorised_cut_agrees_with_scalar_cut_threshold() -> None:
    from driftstream.theory.adwin_replay import _fires  # noqa: PLC0415

    p = ADWINParams()
    rng = np.random.default_rng(3)
    for _ in range(50):
        width = int(rng.integers(200, 20_000))
        drift_at = float(rng.integers(50, width - 10))
        e0, e1 = sorted(rng.uniform(0.0, 0.6, size=2))
        splits = np.array(
            [c for c in bucket_boundaries(width) if 5 <= c <= width - 5],
            dtype=float,
        )
        mean_w = (e0 * drift_at + e1 * (width - drift_at)) / width
        scalar = False
        for c in splits:
            n1 = width - c
            pre0, pre1 = min(c, drift_at), max(drift_at - c, 0.0)
            m0 = (e0 * pre0 + e1 * (c - pre0)) / c
            m1 = (e0 * pre1 + e1 * (n1 - pre1)) / n1
            eps = cut_threshold(c, n1, width, mean_w * (1 - mean_w), p)
            scalar = scalar or abs(m0 - m1) > eps
        vec = _fires(width, np.array([drift_at]), e0, e1, splits, p)
        assert bool(vec[0]) == scalar
