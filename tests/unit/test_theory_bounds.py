# tests/unit/test_theory_bounds.py
"""Analytic bounds: hand-computed values and edge cases (ROADMAP T1.3)."""

from __future__ import annotations

import math

import pytest

from driftstream.theory.bounds import (
    LabelOrigin,
    TheoryInputs,
    collection_time,
    ks_critical_value,
    ks_post_fraction,
    label_rate,
    predict,
    recovery_floor,
    regret,
    regret_per_1000,
    tau_det_sup,
    tau_det_unsup,
    tau_rec_burst,
    tau_rec_continuous,
    tau_rec_on_detect,
    tau_rec_periodic,
)

pytestmark = pytest.mark.unit

LAM = 10.0  # flows/s


def test_label_rate() -> None:
    assert label_rate(0.01, LAM) == pytest.approx(0.1)
    assert label_rate(0.01, LAM, share=0.5) == pytest.approx(0.05)
    with pytest.raises(ValueError, match="fraction"):
        label_rate(1.5, LAM)


def test_tau_det_sup_hand_value() -> None:
    # D + n* / (rho B lambda) = 600 + 50 / 0.05
    assert tau_det_sup(600, 50, 0.01, LAM, rho=0.5) == pytest.approx(1600)


def test_tau_det_sup_edge_cases() -> None:
    assert tau_det_sup(0, 50, 1.0, LAM) == pytest.approx(5.0)  # D=0, B=1
    assert math.isinf(tau_det_sup(0, 50, 0.0, LAM))  # no labels
    assert math.isinf(tau_det_sup(0, math.inf, 0.1, LAM))  # never fires


def test_ks_critical_value_hand_value() -> None:
    c = math.sqrt(-math.log(0.0005) / 2) * math.sqrt(6000 / 5e6)
    assert ks_critical_value(0.001, 5000, 1000) == pytest.approx(c)


def test_ks_post_fraction_and_undetectable_drift() -> None:
    crit = ks_critical_value(0.001, 5000, 1000)
    assert ks_post_fraction(0.5, 0.001, 5000, 1000) == pytest.approx(crit / 0.5)
    assert math.isinf(ks_post_fraction(0.0, 0.001, 5000, 1000))  # SEA
    assert math.isinf(ks_post_fraction(0.01, 0.001, 5000, 1000))


def test_tau_det_unsup_expected_and_worst() -> None:
    exp = tau_det_unsup(LAM, 1000, 500, 2, 0.2)
    worst = tau_det_unsup(LAM, 1000, 500, 2, 0.2, phase="worst")
    assert exp == pytest.approx((200 + 1.5 * 500) / LAM)
    assert worst == pytest.approx((200 + 2 * 500) / LAM)
    assert math.isinf(tau_det_unsup(LAM, 1000, 500, 2, math.inf))


def test_collection_time_without_and_with_burst() -> None:
    assert collection_time(500, 0.01, LAM) == pytest.approx(5000)
    assert collection_time(0, 0.0, LAM) == 0.0
    assert math.isinf(collection_time(1, 0.0, LAM))
    # k=5, C=50: burst exhausted after 50 / (4 * 0.1) = 125 s (62.5 labels
    # queried at 0.5/s), then 437.5 labels at 0.1/s.
    t = collection_time(
        500, 0.01, LAM, burst_factor=5, burst_horizon=3600, bucket_capacity=50
    )
    assert t == pytest.approx(125 + 437.5 / 0.1)


def test_burst_gain_is_bounded_by_bucket_capacity() -> None:
    plain = collection_time(500, 0.01, LAM)
    for k in (2, 5, 10, 100):
        burst = collection_time(
            500,
            0.01,
            LAM,
            burst_factor=k,
            burst_horizon=1e9,
            bucket_capacity=50,
        )
        assert plain - burst == pytest.approx(50 / (0.01 * LAM))


def test_recovery_floor_hand_value_and_capacity() -> None:
    assert recovery_floor(1800, 500, 0.01, LAM) == pytest.approx(6800)
    assert recovery_floor(1800, 500, 0.01, LAM, 50) == pytest.approx(6300)
    assert recovery_floor(0, 500, 1.0, LAM) == pytest.approx(50)  # B = 1


def test_on_detect_origins() -> None:
    kw = {"delay": 600.0, "m": 100.0, "budget": 0.01, "rate": LAM}
    # change point: max(tau, 0 + 600 + 1000)
    assert tau_rec_on_detect(
        300, origin=LabelOrigin.CHANGE_POINT, **kw
    ) == pytest.approx(1600)
    # alarm: 300 + 600 + 1000
    assert tau_rec_on_detect(
        300, origin=LabelOrigin.ALARM, **kw
    ) == pytest.approx(1900)
    # arrivals after the alarm: tau = 1600 -> 1000 + 600 + 1000
    assert tau_rec_on_detect(
        1600, origin=LabelOrigin.AFTER_ALARM_ARRIVALS, **kw
    ) == pytest.approx(2600)
    assert math.isinf(tau_rec_on_detect(math.inf, **kw))


def test_m_min_dominates_when_larger() -> None:
    a = tau_rec_on_detect(0, 0, 100, 0.01, LAM, origin=LabelOrigin.ALARM)
    b = tau_rec_on_detect(
        0, 0, 100, 0.01, LAM, origin=LabelOrigin.ALARM, m_min=500
    )
    assert (a, b) == (pytest.approx(1000), pytest.approx(5000))


def test_burst_never_removes_the_delay() -> None:
    rec = tau_rec_burst(
        100,
        7200,
        500,
        0.01,
        LAM,
        burst_factor=10,
        burst_horizon=1e9,
        bucket_capacity=1e9,
    )
    assert rec >= 100 + 7200


def test_continuous_and_periodic() -> None:
    assert tau_rec_continuous(0, 500, 0.01, LAM) == pytest.approx(5000)
    assert tau_rec_periodic(0, 500, 0.01, LAM, 3600) == pytest.approx(6800)
    assert tau_rec_periodic(
        0, 500, 0.01, LAM, 3600, phase="worst"
    ) == pytest.approx(8600)
    with pytest.raises(ValueError, match="period"):
        tau_rec_periodic(0, 500, 0.01, LAM, 0)


def test_regret_is_linear_in_recovery_time() -> None:
    assert regret(LAM, 0.2, 1000) == pytest.approx(2000)
    assert regret_per_1000(LAM, 0.2, 1000, 100_000) == pytest.approx(20)
    assert math.isinf(regret(LAM, 0.2, math.inf))
    assert regret(LAM, 0.0, 1000) == 0.0


def _inputs(delay: float) -> TheoryInputs:
    return TheoryInputs(
        delay=delay,
        budget=0.01,
        rho=0.5,
        rate=LAM,
        eps0=0.05,
        eps1=0.25,
        m_a=500,
        n_star=92.5,
        ks_c=ks_post_fraction(0.3, 0.001, 5000, 1000),
        m_min=500,
        n_flows=200_000,
    )


def test_predict_slope_in_delay_is_one_for_every_policy() -> None:
    p0, p1 = predict(_inputs(0)), predict(_inputs(1000))
    assert p1.tau_det_sup - p0.tau_det_sup == pytest.approx(1000)
    assert p1.tau_det_unsup == pytest.approx(p0.tau_det_unsup)  # H2
    for name, rec in p1.tau_rec.items():
        assert rec - p0.tau_rec[name] == pytest.approx(1000), name


def test_predict_respects_the_floor_and_serialises() -> None:
    p = predict(_inputs(1800))
    assert all(v >= p.floor - 1e-9 for v in p.tau_rec.values())
    assert set(p.to_dict()) >= {"tau_rec", "regret_per_1000", "floor"}


def test_lognormal_floor_is_below_the_constant_floor() -> None:
    from driftstream.theory.bounds import (  # noqa: PLC0415
        recovery_floor_lognormal,
    )

    const = recovery_floor(1800, 500, 0.01, LAM)
    for sigma in (0.25, 1.0, 2.0):
        ln = recovery_floor_lognormal(1800, sigma, 500, 0.01, LAM)
        assert ln < const
    # A tiny sigma converges to the constant-delay floor.
    tight = recovery_floor_lognormal(1800, 1e-4, 500, 0.01, LAM)
    assert tight == pytest.approx(const, rel=1e-3)


def test_lognormal_floor_edge_cases() -> None:
    from driftstream.theory.bounds import (  # noqa: PLC0415
        recovery_floor_lognormal,
    )

    assert recovery_floor_lognormal(1800, 1.0, 40, 0.01, LAM, 50) == 0.0
    assert math.isinf(recovery_floor_lognormal(1800, 1.0, 500, 0.0, LAM))
    with pytest.raises(ValueError, match="log-normal"):
        recovery_floor_lognormal(0, 1.0, 500, 0.01, LAM)
