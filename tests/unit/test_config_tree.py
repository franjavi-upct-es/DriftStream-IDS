# tests/unit/test_config_tree.py
"""Every Hydra group option and experiment composes (ROADMAP T0.4)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from omegaconf import DictConfig

pytestmark = pytest.mark.unit

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"

GROUPS = (
    "dataset",
    "features",
    "learner",
    "detector",
    "oracle",
    "selector",
    "policy",
    "evaluation",
    "stream",
)


def _options(group: str) -> list[str]:
    return sorted(p.stem for p in (CONFIG_DIR / group).glob("*.yaml"))


def _experiments() -> list[str]:
    return _options("experiment")


@pytest.fixture(autouse=True)
def _hydra() -> Iterator[None]:
    GlobalHydra.instance().clear()
    with initialize_config_dir(config_dir=str(CONFIG_DIR), version_base="1.3"):
        yield
    GlobalHydra.instance().clear()


def test_root_config_composes_with_documented_defaults() -> None:
    cfg = compose(config_name="config")
    assert cfg.experiment == "adhoc"
    assert cfg.seed == 0
    assert cfg.dataset.name == "cicids2017"
    assert cfg.detector.kind == "supervised"
    assert 0 < cfg.oracle.budget <= 1  # budgets are fractions


@pytest.mark.parametrize(
    ("group", "option"),
    [(g, o) for g in GROUPS for o in _options(g)],
    ids=str,
)
def test_every_group_option_composes(group: str, option: str) -> None:
    cfg = compose(config_name="config", overrides=[f"{group}={option}"])
    assert isinstance(cfg[group], DictConfig)


@pytest.mark.parametrize("name", _experiments())
def test_every_experiment_composes_and_names_itself(name: str) -> None:
    cfg = compose(config_name="config", overrides=[f"experiment={name}"])
    assert cfg.experiment == name


def test_every_experiment_has_a_card(repo_root: Path) -> None:
    cards = repo_root / "docs" / "experiment_cards"
    for name in _experiments():
        card = cards / f"{name.split('_')[0]}.md"
        assert card.is_file(), f"missing experiment card for {name}"
