# tests/unit/test_theory_from_config.py
"""Mapping resolved configs to theory inputs."""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from omegaconf import OmegaConf

from driftstream.theory.from_config import (
    StreamQuantities,
    inputs_from_config,
    random_share,
)

pytestmark = pytest.mark.unit

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
STREAM = StreamQuantities(
    rate=10.0,
    eps0=0.05,
    eps1=0.25,
    m_a=500,
    n_pre_flows=100_000,
    ks_distance=0.3,
    n_flows=200_000,
)


@pytest.fixture(autouse=True)
def _hydra() -> Iterator[None]:
    GlobalHydra.instance().clear()
    with initialize_config_dir(config_dir=str(CONFIG_DIR), version_base="1.3"):
        yield
    GlobalHydra.instance().clear()


def _cfg(*overrides: str) -> dict[str, Any]:
    plain = OmegaConf.to_container(
        compose(config_name="config", overrides=list(overrides)), resolve=True
    )
    assert isinstance(plain, dict)
    return {str(k): v for k, v in plain.items()}


@pytest.mark.parametrize(
    ("selector", "rho"),
    [("random", 1.0), ("uncertainty", 0.0), ("hybrid", 0.5)],
)
def test_random_share_per_selector(selector: str, rho: float) -> None:
    assert random_share(_cfg(f"selector={selector}")["selector"]) == rho


def test_design_factors_come_from_the_config() -> None:
    inp = inputs_from_config(
        _cfg("oracle.delay.mean_seconds=7200", "oracle.budget=0.05"), STREAM
    )
    assert (inp.delay, inp.budget, inp.rho) == (7200.0, 0.05, 0.5)
    assert inp.bucket_capacity == 50.0
    assert inp.m_min == 500.0
    assert math.isfinite(inp.n_star)  # default detector is ADWIN


def test_unsupervised_config_has_no_supervised_prediction() -> None:
    inp = inputs_from_config(_cfg("detector=ks_scores"), STREAM)
    assert math.isinf(inp.n_star)
    assert 0 < inp.ks_c < 1


def test_uncertainty_selector_starves_the_supervised_detector() -> None:
    inp = inputs_from_config(_cfg("selector=uncertainty"), STREAM)
    assert math.isinf(inp.n_star)  # rho = 0: no random labels (ADR-007)


def test_lognormal_oracle_lowers_the_predicted_floor() -> None:
    from driftstream.theory.bounds import predict  # noqa: PLC0415

    const = predict(inputs_from_config(_cfg(), STREAM))
    ln_inp = inputs_from_config(_cfg("oracle=lognormal"), STREAM)
    assert ln_inp.delay_sigma == 1.0
    assert predict(ln_inp).floor < const.floor
