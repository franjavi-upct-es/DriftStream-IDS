# tests/property/test_theory_floor.py
"""Property: no policy of the model beats the recovery floor (H3)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from driftstream.theory.bounds import (
    LabelOrigin,
    recovery_floor,
    tau_rec_burst,
    tau_rec_continuous,
    tau_rec_on_detect,
    tau_rec_periodic,
)

pytestmark = pytest.mark.property

delays = st.floats(0, 7 * 86_400)
budgets = st.floats(1e-4, 1.0)
rates = st.floats(0.1, 1e4)
labels = st.floats(0, 1e5)
tau = st.floats(0, 1e6)
capacity = st.floats(0, 1e5)


@settings(max_examples=300, deadline=None)
@given(
    d=delays,
    b=budgets,
    lam=rates,
    m=labels,
    t=tau,
    c=capacity,
    k=st.floats(1, 100),
    h=st.floats(0, 1e6),
    origin=st.sampled_from(list(LabelOrigin)),
    period=st.floats(1, 1e6),
)
def test_every_policy_respects_the_floor(
    d: float,
    b: float,
    lam: float,
    m: float,
    t: float,
    c: float,
    k: float,
    h: float,
    origin: LabelOrigin,
    period: float,
) -> None:
    floor = recovery_floor(d, m, b, lam, bucket_capacity=c)
    tol = 1e-6 * (1 + floor)
    assert tau_rec_continuous(d, m, b, lam) >= floor - tol
    assert tau_rec_periodic(d, m, b, lam, period) >= floor - tol
    assert tau_rec_on_detect(t, d, m, b, lam, origin=origin) >= floor - tol
    burst = tau_rec_burst(
        t, d, m, b, lam, burst_factor=k, burst_horizon=h, bucket_capacity=c
    )
    assert burst >= floor - tol


@settings(max_examples=200, deadline=None)
@given(d=delays, extra=st.floats(1, 1e5), b=budgets, lam=rates, m=labels)
def test_floor_is_increasing_in_delay(
    d: float, extra: float, b: float, lam: float, m: float
) -> None:
    lo = recovery_floor(d, m, b, lam)
    hi = recovery_floor(d + extra, m, b, lam)
    assert hi - lo == pytest.approx(extra, rel=1e-9, abs=1e-6)
