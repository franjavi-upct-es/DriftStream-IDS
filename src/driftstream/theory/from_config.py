# src/driftstream/theory/from_config.py
"""Map a resolved run configuration to :class:`TheoryInputs`.

The configuration fixes the *design* factors (``D``, ``B``, ``rho``,
``C``, detector and policy parameters). The *data* quantities
(``lambda``, ``eps0``, ``eps1``, ``m_a``, the pre-drift label count and
the KS distance between score distributions) are not in the config: they
are measured on the stream (E0 calibration runs, ETL statistics) and
passed explicitly as :class:`StreamQuantities`.

The mapping reads plain mappings (``OmegaConf.to_container`` output), so
this module stays free of Hydra.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from driftstream.theory.adwin_replay import ADWINParams, n_star
from driftstream.theory.bounds import TheoryInputs, ks_post_fraction

__all__ = ["StreamQuantities", "inputs_from_config", "random_share"]

# Default KS parameters (configs/detector/ks_scores.yaml), used for the
# unsupervised prediction when the configured detector is not KS.
_KS_DEFAULTS = {
    "w_ref": 5000,
    "w_test": 1000,
    "check_every": 500,
    "alpha": 0.001,
    "persistence": 2,
}


@dataclass(frozen=True, slots=True)
class StreamQuantities:
    """Measured properties of the stream around one drift.

    Attributes:
        rate: Flow arrival rate ``lambda``, flows/s.
        eps0: Pre-drift error rate of the pre-drift model, fraction.
        eps1: Post-drift error rate of the pre-drift model, fraction.
        m_a: Post-drift labels the learner needs, labels.
        n_pre_flows: Flows seen by the detector before the drift.
        ks_distance: Population KS distance between pre- and post-drift
            score distributions, in [0, 1] (``None``: not predicted).
        n_flows: Flows in the streaming phase, for normalised regret.
    """

    rate: float
    eps0: float
    eps1: float
    m_a: float
    n_pre_flows: int
    ks_distance: float | None = None
    n_flows: int = 1


def random_share(selector: Mapping[str, Any]) -> float:
    """Return ``rho``, the random share of the budget, for a selector.

    Args:
        selector: The ``selector`` config node.

    Returns:
        1.0 for ``random``, 0.0 for ``uncertainty`` and ``rho`` for
        ``hybrid``.
    """
    target = str(selector.get("_target_", ""))
    if target.endswith("RandomSelector"):
        return 1.0
    if target.endswith("UncertaintySelector"):
        return 0.0
    return float(selector.get("rho", 1.0))


def _adwin_params(detector: Mapping[str, Any]) -> ADWINParams:
    keys = ADWINParams.__dataclass_fields__
    kwargs = {k: detector[k] for k in keys if k in detector}
    return ADWINParams(**kwargs)


def inputs_from_config(
    cfg: Mapping[str, Any], stream: StreamQuantities
) -> TheoryInputs:
    """Build the model inputs for one configuration.

    Args:
        cfg: Resolved configuration as a plain mapping.
        stream: Measured stream quantities.

    Returns:
        Inputs for :func:`driftstream.theory.bounds.predict`. For
        log-normal delays ``delay`` is the mean and ``delay_sigma`` the
        shape (theory.md §5.5).
    """
    oracle = cfg["oracle"]
    budget = float(oracle["budget"])
    rho = random_share(cfg["selector"])
    detector = cfg["detector"]
    kind = detector.get("kind")

    labels_pre = rho * budget * stream.n_pre_flows
    if kind == "supervised" and labels_pre >= 1:
        ns = n_star(
            stream.eps0, stream.eps1, round(labels_pre), _adwin_params(detector)
        )
    else:
        ns = math.inf

    ks = {**_KS_DEFAULTS, **(detector if kind == "unsupervised" else {})}
    ks_c = (
        ks_post_fraction(
            stream.ks_distance,
            float(ks["alpha"]),
            int(ks["w_ref"]),
            int(ks["w_test"]),
        )
        if stream.ks_distance is not None
        else math.inf
    )
    policy = cfg.get("policy", {})
    delay_cfg = oracle["delay"]
    lognormal = str(delay_cfg.get("_target_", "")).endswith("LogNormalDelay")
    sigma = float(delay_cfg.get("sigma", 1.0)) if lognormal else 0.0
    return TheoryInputs(
        delay=float(oracle["delay"]["mean_seconds"]),
        budget=budget,
        rho=rho,
        rate=stream.rate,
        eps0=stream.eps0,
        eps1=stream.eps1,
        m_a=stream.m_a,
        n_star=ns,
        ks_c=ks_c,
        ks_w_test=int(ks["w_test"]),
        ks_check_every=int(ks["check_every"]),
        ks_persistence=int(ks["persistence"]),
        m_min=float(policy.get("m_min", 0.0)),
        period=float(policy.get("period_seconds", 3600.0)),
        burst_factor=float(policy.get("factor", 5.0)),
        burst_horizon=float(policy.get("horizon_seconds", 3600.0)),
        bucket_capacity=float(oracle.get("bucket_capacity", 50.0)),
        n_flows=stream.n_flows,
        delay_sigma=sigma,
    )
