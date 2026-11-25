# src/driftstream/theory/bounds.py
"""Analytic predictions of detection delay, recovery time and regret.

Implements the model of ``docs/theory.md`` (summary in ARCHITECTURE.md
§4). Conventions, used everywhere in this module:

* time is measured in **seconds of event time**, relative to the drift
  onset ``t0`` (so a delay ``tau`` means the event happens at
  ``t0 + tau``);
* ``rate`` is the flow arrival rate ``lambda`` in flows per second;
* ``budget`` (``B``) and ``rho`` are **fractions** in (0, 1];
* label counts (``n_star``, ``m``) are numbers of labels.

All functions are pure. They return ``math.inf`` when an event can never
happen under the model (for example a zero budget, or an unsupervised
test that cannot reject), so censoring is explicit rather than hidden.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Literal

__all__ = [
    "LabelOrigin",
    "Phase",
    "TheoryInputs",
    "TheoryPrediction",
    "collection_time",
    "ks_critical_value",
    "ks_post_fraction",
    "label_rate",
    "predict",
    "recovery_floor",
    "recovery_floor_lognormal",
    "regret",
    "regret_per_1000",
    "tau_det_sup",
    "tau_det_unsup",
    "tau_rec_burst",
    "tau_rec_continuous",
    "tau_rec_on_detect",
    "tau_rec_periodic",
]

Phase = Literal["expected", "worst"]


class LabelOrigin(StrEnum):
    """Which labelled flows a retraining policy may use after an alarm.

    The retraining set holds labels of flows with event time at least
    ``t0 + o``; the offset ``o`` depends on the change-time estimate the
    detector reports (theory.md §5.1).

    Attributes:
        CHANGE_POINT: ``o = 0``: the estimate equals the true onset.
        ALARM: ``o = tau_det``: only flows seen after the alarm.
        AFTER_ALARM_ARRIVALS: ``o = tau_det - D``: only labels that
            *arrive* after the alarm (ARCHITECTURE.md §4.4, ODS row).
    """

    CHANGE_POINT = "change_point"
    ALARM = "alarm"
    AFTER_ALARM_ARRIVALS = "after_alarm_arrivals"


def _check_fraction(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be a fraction in [0, 1], got {value}")


def _check_non_negative(name: str, value: float) -> None:
    if value < 0.0 or math.isnan(value):
        raise ValueError(f"{name} must be >= 0, got {value}")


def label_rate(budget: float, rate: float, share: float = 1.0) -> float:
    """Return the arrival rate of (a share of) the queried labels.

    Args:
        budget: Labelling budget ``B``, fraction of flows queried.
        rate: Flow arrival rate ``lambda``, flows/s.
        share: Share of the budget considered (``rho`` for the random
            substream), fraction.

    Returns:
        Labels per second of event time.
    """
    _check_fraction("budget", budget)
    _check_fraction("share", share)
    _check_non_negative("rate", rate)
    return share * budget * rate


def collection_time(
    m: float,
    budget: float,
    rate: float,
    *,
    burst_factor: float = 1.0,
    burst_horizon: float = 0.0,
    bucket_capacity: float = math.inf,
) -> float:
    """Time needed to *query* ``m`` labels from a given instant.

    Without a burst, labels are queried at ``B * lambda``. A burst raises
    the query rate to ``k * B * lambda`` for at most ``burst_horizon``
    seconds, but the token bucket (ADR-006) finances only
    ``bucket_capacity`` extra tokens: the burst ends early when the saved
    tokens run out, after ``C / ((k - 1) * B * lambda)`` seconds
    (theory.md §5.3). The bucket is assumed full when the burst starts.

    Args:
        m: Labels to collect.
        budget: Labelling budget ``B``, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.
        burst_factor: Query-rate multiplier ``k`` (>= 1).
        burst_horizon: Maximum burst duration ``H``, seconds.
        bucket_capacity: Token-bucket cap ``C``, tokens.

    Returns:
        Seconds until the ``m``-th label is queried (``inf`` if never).
    """
    _check_non_negative("m", m)
    _check_non_negative("burst_horizon", burst_horizon)
    _check_non_negative("bucket_capacity", bucket_capacity)
    if burst_factor < 1.0:
        raise ValueError(f"burst_factor must be >= 1, got {burst_factor}")
    base = label_rate(budget, rate)
    if m == 0.0:
        return 0.0
    if base == 0.0:
        return math.inf
    burst_len = 0.0
    if burst_factor > 1.0 and burst_horizon > 0.0:
        exhaust = bucket_capacity / ((burst_factor - 1.0) * base)
        burst_len = min(burst_horizon, exhaust)
    during = burst_factor * base * burst_len
    if m <= during:
        return m / (burst_factor * base)
    return burst_len + (m - during) / base


def tau_det_sup(
    delay: float,
    n_star: float,
    budget: float,
    rate: float,
    rho: float = 1.0,
) -> float:
    """Expected supervised detection delay (H1).

    ``E[tau_det_sup] = D + n* / (rho * B * lambda)``. The check-clock term
    of ARCHITECTURE.md §4.2 is already inside ``n_star`` when it comes from
    :func:`driftstream.theory.adwin_replay.n_star`.

    Args:
        delay: Mean verification delay ``D``, seconds.
        n_star: Post-drift random-substream labels needed to fire.
        budget: Labelling budget ``B``, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.
        rho: Random share of the budget, fraction.

    Returns:
        Seconds after the onset (``inf`` if the detector never fires).
    """
    _check_non_negative("delay", delay)
    _check_non_negative("n_star", n_star)
    lr = label_rate(budget, rate, rho)
    if math.isinf(n_star) or lr == 0.0:
        return math.inf
    return delay + n_star / lr


def ks_critical_value(alpha: float, n_ref: int, n_test: int) -> float:
    """Asymptotic critical value of the two-sample KS statistic.

    ``c(alpha) * sqrt((n + m) / (n * m))`` with
    ``c(alpha) = sqrt(-ln(alpha / 2) / 2)`` (Smirnov's limit law).

    Args:
        alpha: Significance level of one test, fraction.
        n_ref: Reference-window size, scores.
        n_test: Test-window size, scores.

    Returns:
        Rejection threshold on the KS statistic (dimensionless).
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    if n_ref < 1 or n_test < 1:
        raise ValueError("window sizes must be >= 1")
    c_alpha = math.sqrt(-math.log(alpha / 2.0) / 2.0)
    return c_alpha * math.sqrt((n_ref + n_test) / (n_ref * n_test))


def ks_post_fraction(
    ks_distance: float,
    alpha: float,
    w_ref: int,
    w_test: int,
) -> float:
    """Post-drift share of the test window needed to reject (``c_KS``).

    A test window holding a share ``f`` of post-drift scores follows the
    mixture ``f * F1 + (1 - f) * F0``, whose KS distance to ``F0`` is
    exactly ``f * d`` with ``d = sup |F1 - F0|``. Rejection (in
    expectation) needs ``f * d`` above the critical value (theory.md
    §4.2).

    Args:
        ks_distance: Population KS distance ``d`` between pre- and
            post-drift score distributions, in [0, 1].
        alpha: Significance level of one test, fraction.
        w_ref: Reference-window size, scores.
        w_test: Test-window size, scores.

    Returns:
        ``c_KS`` in (0, 1], or ``inf`` when even a fully post-drift window
        cannot reject (e.g. pure ``P(y|x)`` drift: ``d = 0``).
    """
    _check_fraction("ks_distance", ks_distance)
    crit = ks_critical_value(alpha, w_ref, w_test)
    if ks_distance == 0.0 or crit / ks_distance > 1.0:
        return math.inf
    return crit / ks_distance


def tau_det_unsup(
    rate: float,
    w_test: int,
    check_every: int,
    persistence: int,
    c_ks: float,
    phase: Phase = "expected",
) -> float:
    """Unsupervised (KS on scores) detection delay (H2).

    The test window must hold ``c_KS * w_test`` post-drift scores, then
    the next check must come (``k / 2`` expected, ``k`` worst case) and
    ``persistence - 1`` further checks must reject::

        expected: (c_KS * w_test + (p - 1/2) * k) / lambda
        worst:    (c_KS * w_test + p * k) / lambda   (ARCHITECTURE §4.3)

    The result does not depend on ``D`` or ``B``.

    Args:
        rate: Flow arrival rate ``lambda``, flows/s.
        w_test: Test-window size, scores.
        check_every: Arrivals between two tests ``k``.
        persistence: Consecutive rejections needed ``p`` (>= 1).
        c_ks: Post-drift share needed to reject (see
            :func:`ks_post_fraction`).
        phase: ``"expected"`` (uniform check phase) or ``"worst"``.

    Returns:
        Seconds after the onset (``inf`` if the test cannot reject).
    """
    _check_non_negative("rate", rate)
    if persistence < 1 or check_every < 1 or w_test < 1:
        raise ValueError("persistence, check_every and w_test must be >= 1")
    if math.isinf(c_ks) or rate == 0.0:
        return math.inf
    wait = 0.5 if phase == "expected" else 1.0
    arrivals = c_ks * w_test + (persistence - 1 + wait) * check_every
    return arrivals / rate


def recovery_floor(
    delay: float,
    m: float,
    budget: float,
    rate: float,
    bucket_capacity: float = 0.0,
) -> float:
    """Lower bound on recovery for any label-dependent adaptation (H3).

    The token bucket (ADR-006) allows at most ``B * lambda * t + C``
    queries in any interval of length ``t``, and no post-drift label is
    visible before ``t0 + D``. Hence, for every policy that waits for
    labels, including bursts (theory.md §5.2)::

        tau_rec >= D + max(m - C, 0) / (B * lambda)

    With ``C = 0`` this is ARCHITECTURE.md's ``D + m_a / (B * lambda)``.

    Args:
        delay: Mean verification delay ``D``, seconds.
        m: Post-drift labels needed to re-attain oracle-level error
            (``m_a``).
        budget: Labelling budget ``B``, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.
        bucket_capacity: Token-bucket cap ``C``, tokens.

    Returns:
        Seconds after the onset.
    """
    _check_non_negative("delay", delay)
    _check_non_negative("bucket_capacity", bucket_capacity)
    return delay + collection_time(max(m - bucket_capacity, 0.0), budget, rate)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _lognormal_partial_mean(t: float, mean: float, sigma: float) -> float:
    """``E[(t - delta)^+]`` for ``delta ~ LogNormal`` with the given mean."""
    if t <= 0.0:
        return 0.0
    mu = math.log(mean) - sigma**2 / 2.0
    z = (math.log(t) - mu) / sigma
    return t * _norm_cdf(z) - mean * _norm_cdf(z - sigma)


def recovery_floor_lognormal(
    delay: float,
    sigma: float,
    m: float,
    budget: float,
    rate: float,
    bucket_capacity: float = 0.0,
) -> float:
    """Expected recovery floor under log-normal verification delays.

    Labels queried at ``B * lambda`` from the onset are released after
    independent delays ``delta ~ LogNormal`` with mean ``D``. The expected
    number released by ``t`` is ``B * lambda * E[(t - delta)^+]``; the
    floor is the ``t`` at which it reaches ``max(m - C, 0)`` (theory.md
    §5.5). By Jensen's inequality it is **below** the constant-delay
    floor: heavy tails also mean that many labels arrive early.

    Args:
        delay: Mean verification delay ``D``, seconds (> 0).
        sigma: Log-normal shape parameter (> 0).
        m: Post-drift labels needed.
        budget: Labelling budget ``B``, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.
        bucket_capacity: Token-bucket cap ``C``, tokens.

    Returns:
        Seconds after the onset (expected-value floor, not a per-run bound).
    """
    if delay <= 0.0 or sigma <= 0.0:
        raise ValueError("delay and sigma must be > 0 for log-normal delays")
    target = max(m - bucket_capacity, 0.0)
    lr = label_rate(budget, rate)
    if target == 0.0:
        return 0.0
    if lr == 0.0:
        return math.inf
    goal = target / lr  # seconds of "released-label mass" needed
    lo, hi = 0.0, delay + goal
    while _lognormal_partial_mean(hi, delay, sigma) < goal:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _lognormal_partial_mean(mid, delay, sigma) < goal:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-9 * max(hi, 1.0):
            break
    return hi


def tau_rec_on_detect(
    tau_det: float,
    delay: float,
    m: float,
    budget: float,
    rate: float,
    *,
    origin: LabelOrigin = LabelOrigin.ALARM,
    m_min: float = 0.0,
    burst_factor: float = 1.0,
    burst_horizon: float = 0.0,
    bucket_capacity: float = math.inf,
) -> float:
    """Recovery time of a retrain-on-alarm policy (ODS, ODU, burst).

    Retraining needs ``max(m, m_min)`` labels of flows with event time
    ``>= t0 + o`` and cannot start before the alarm::

        tau_rec = max(tau_det, o + D + T_collect)

    where ``T_collect`` is the time to query the labels (a burst, if any,
    starts at the alarm and therefore only applies when ``o = tau_det``).

    Args:
        tau_det: Detection delay, seconds after the onset.
        delay: Mean verification delay ``D``, seconds.
        m: Labels needed to re-attain oracle-level error (``m_a``).
        budget: Labelling budget ``B``, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.
        origin: Which labelled flows the retraining may use.
        m_min: Policy minimum before retraining, labels.
        burst_factor: Query-rate multiplier ``k`` after the alarm.
        burst_horizon: Maximum burst duration ``H``, seconds.
        bucket_capacity: Token-bucket cap ``C``, tokens.

    Returns:
        Seconds after the onset (``inf`` if detection never happens).
    """
    _check_non_negative("delay", delay)
    if math.isinf(tau_det):
        return math.inf
    _check_non_negative("tau_det", tau_det)
    needed = max(m, m_min)
    if origin is LabelOrigin.CHANGE_POINT:
        offset = 0.0
    elif origin is LabelOrigin.ALARM:
        offset = tau_det
    else:
        offset = max(tau_det - delay, 0.0)
    burst = origin is LabelOrigin.ALARM
    t_collect = collection_time(
        needed,
        budget,
        rate,
        burst_factor=burst_factor if burst else 1.0,
        burst_horizon=burst_horizon if burst else 0.0,
        bucket_capacity=bucket_capacity,
    )
    return max(tau_det, offset + delay + t_collect)


def tau_rec_burst(
    tau_det_unsup_s: float,
    delay: float,
    m: float,
    budget: float,
    rate: float,
    *,
    burst_factor: float,
    burst_horizon: float,
    bucket_capacity: float,
    m_min: float = 0.0,
) -> float:
    """Recovery of ODU + budget burst (ARCHITECTURE.md §4.4, burst row).

    ``tau_det + D + T_collect(k, H, C)``: the burst speeds up label
    *collection*, never label *verification* (``D`` stays).

    Args:
        tau_det_unsup_s: Unsupervised detection delay, seconds.
        delay: Mean verification delay ``D``, seconds.
        m: Labels needed to re-attain oracle-level error.
        budget: Labelling budget ``B``, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.
        burst_factor: Query-rate multiplier ``k``.
        burst_horizon: Maximum burst duration ``H``, seconds.
        bucket_capacity: Token-bucket cap ``C``, tokens.
        m_min: Policy minimum before retraining, labels.

    Returns:
        Seconds after the onset.
    """
    return tau_rec_on_detect(
        tau_det_unsup_s,
        delay,
        m,
        budget,
        rate,
        origin=LabelOrigin.ALARM,
        m_min=m_min,
        burst_factor=burst_factor,
        burst_horizon=burst_horizon,
        bucket_capacity=bucket_capacity,
    )


def tau_rec_continuous(
    delay: float, m: float, budget: float, rate: float
) -> float:
    """Recovery of continuous online learning (ARF, no external reset).

    Every delayed label is learnt as soon as it arrives, so the
    ``C = 0`` floor is attained: ``D + m_ARF / (B * lambda)`` (``m_ARF``
    is ARF's own label need, estimated in E0).

    Args:
        delay: Mean verification delay ``D``, seconds.
        m: Labels ARF needs to re-attain oracle-level error.
        budget: Labelling budget ``B``, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.

    Returns:
        Seconds after the onset.
    """
    return recovery_floor(delay, m, budget, rate)


def tau_rec_periodic(
    delay: float,
    m: float,
    budget: float,
    rate: float,
    period: float,
    phase: Phase = "expected",
) -> float:
    """Recovery of a periodic retraining policy.

    The first retrain after ``m`` post-drift labels have arrived restores
    the model; retrains happen every ``period`` seconds with a phase
    independent of the onset, so the wait adds ``period / 2`` (expected)
    or ``period`` (worst). Assumes the retraining window keeps at least
    the ``m`` post-drift labels and that they dominate it.

    Args:
        delay: Mean verification delay ``D``, seconds.
        m: Labels needed to re-attain oracle-level error.
        budget: Labelling budget ``B``, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.
        period: Retraining period ``T``, seconds.
        phase: ``"expected"`` or ``"worst"``.

    Returns:
        Seconds after the onset.
    """
    if period <= 0.0:
        raise ValueError(f"period must be > 0, got {period}")
    wait = period / 2.0 if phase == "expected" else period
    return recovery_floor(delay, m, budget, rate) + wait


def regret(rate: float, d_eps: float, tau_rec: float) -> float:
    """Expected label-latency regret in excess errors (H4).

    Under abrupt drift (A1) the deployed model makes ``d_eps`` extra
    errors per flow until recovery: ``R = lambda * d_eps * tau_rec``.

    Args:
        rate: Flow arrival rate ``lambda``, flows/s.
        d_eps: Error jump ``eps1 - eps0``, fraction.
        tau_rec: Recovery time, seconds after the onset.

    Returns:
        Expected excess errors relative to the oracle.
    """
    _check_non_negative("rate", rate)
    _check_fraction("d_eps", d_eps)
    if math.isinf(tau_rec):
        return math.inf
    return rate * d_eps * tau_rec


def regret_per_1000(
    rate: float, d_eps: float, tau_rec: float, n_flows: int
) -> float:
    """Regret normalised per 1,000 streamed flows (ARCHITECTURE §4.5).

    Args:
        rate: Flow arrival rate ``lambda``, flows/s.
        d_eps: Error jump ``eps1 - eps0``, fraction.
        tau_rec: Recovery time, seconds after the onset.
        n_flows: Flows in the streaming phase of the run.

    Returns:
        Excess errors per 1,000 flows.
    """
    if n_flows < 1:
        raise ValueError("n_flows must be >= 1")
    return 1000.0 * regret(rate, d_eps, tau_rec) / n_flows


# --------------------------------------------------------------------------
# One-stop prediction for a configuration
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class TheoryInputs:
    """Everything the model needs for one configuration.

    Attributes:
        delay: Mean verification delay ``D``, seconds.
        budget: Labelling budget ``B``, fraction.
        rho: Random share of the budget, fraction.
        rate: Flow arrival rate ``lambda``, flows/s.
        eps0: Pre-drift error rate of the pre-drift model, fraction.
        eps1: Post-drift error rate of the pre-drift model, fraction.
        m_a: Post-drift labels the learner needs, labels.
        n_star: Post-drift random labels ADWIN needs, labels.
        ks_c: Post-drift share of the KS test window needed to reject
            (``inf`` if undetectable).
        ks_w_test: KS test-window size, scores.
        ks_check_every: Arrivals between KS tests.
        ks_persistence: Consecutive KS rejections needed.
        m_min: Policy minimum before retraining, labels.
        period: Periodic-policy period, seconds.
        burst_factor: Burst multiplier ``k``.
        burst_horizon: Burst horizon ``H``, seconds.
        bucket_capacity: Token-bucket cap ``C``, tokens.
        n_flows: Flows in the streaming phase (for normalised regret).
        delay_sigma: Log-normal shape of the delay; 0 means constant
            delays (A3). When > 0, the floor and the continuous policy
            use :func:`recovery_floor_lognormal`; the alarm-based
            policies keep the constant-delay approximation.
    """

    delay: float
    budget: float
    rho: float
    rate: float
    eps0: float
    eps1: float
    m_a: float
    n_star: float
    ks_c: float = math.inf
    ks_w_test: int = 1000
    ks_check_every: int = 500
    ks_persistence: int = 2
    m_min: float = 0.0
    period: float = 3600.0
    burst_factor: float = 5.0
    burst_horizon: float = 3600.0
    bucket_capacity: float = 50.0
    n_flows: int = 1
    delay_sigma: float = 0.0


@dataclass(frozen=True, slots=True)
class TheoryPrediction:
    """Predictions for one configuration (seconds after the onset).

    Attributes:
        tau_det_sup: Supervised (ADWIN) detection delay.
        tau_det_unsup: Unsupervised (KS) detection delay.
        floor: Recovery floor ``D + max(m_a - C, 0) / (B * lambda)``.
        tau_rec: Recovery time per policy.
        regret_per_1000: Regret per 1,000 flows per policy.
    """

    tau_det_sup: float
    tau_det_unsup: float
    floor: float
    tau_rec: dict[str, float]
    regret_per_1000: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly dict (``inf`` kept as ``float('inf')``)."""
        return asdict(self)


def predict(inp: TheoryInputs) -> TheoryPrediction:
    """Compute every prediction of theory.md for one configuration.

    Args:
        inp: Model inputs.

    Returns:
        Detection delays, the recovery floor, recovery time and regret
        for the policies ``continuous``, ``periodic``, ``on_detect_sup``,
        ``on_detect_unsup`` and ``budget_burst``.
    """
    d_eps = max(inp.eps1 - inp.eps0, 0.0)
    det_sup = tau_det_sup(inp.delay, inp.n_star, inp.budget, inp.rate, inp.rho)
    det_unsup = tau_det_unsup(
        inp.rate,
        inp.ks_w_test,
        inp.ks_check_every,
        inp.ks_persistence,
        inp.ks_c,
    )
    common = {"m_min": inp.m_min}
    if inp.delay_sigma > 0.0 and inp.delay > 0.0:
        floor = recovery_floor_lognormal(
            inp.delay,
            inp.delay_sigma,
            inp.m_a,
            inp.budget,
            inp.rate,
            inp.bucket_capacity,
        )
        continuous = recovery_floor_lognormal(
            inp.delay, inp.delay_sigma, inp.m_a, inp.budget, inp.rate
        )
    else:
        floor = recovery_floor(
            inp.delay, inp.m_a, inp.budget, inp.rate, inp.bucket_capacity
        )
        continuous = tau_rec_continuous(
            inp.delay, inp.m_a, inp.budget, inp.rate
        )
    rec = {
        "continuous": continuous,
        "periodic": tau_rec_periodic(
            inp.delay, inp.m_a, inp.budget, inp.rate, inp.period
        ),
        "on_detect_sup": tau_rec_on_detect(
            det_sup,
            inp.delay,
            inp.m_a,
            inp.budget,
            inp.rate,
            origin=LabelOrigin.AFTER_ALARM_ARRIVALS,
            **common,
        ),
        "on_detect_unsup": tau_rec_on_detect(
            det_unsup,
            inp.delay,
            inp.m_a,
            inp.budget,
            inp.rate,
            origin=LabelOrigin.ALARM,
            **common,
        ),
        "budget_burst": tau_rec_burst(
            det_unsup,
            inp.delay,
            inp.m_a,
            inp.budget,
            inp.rate,
            burst_factor=inp.burst_factor,
            burst_horizon=inp.burst_horizon,
            bucket_capacity=inp.bucket_capacity,
            **common,
        ),
    }
    reg = {
        k: regret_per_1000(inp.rate, d_eps, v, inp.n_flows)
        for k, v in rec.items()
    }
    return TheoryPrediction(
        tau_det_sup=det_sup,
        tau_det_unsup=det_unsup,
        floor=floor,
        tau_rec=rec,
        regret_per_1000=reg,
    )
