# tests/conftest.py
"""Shared pytest fixtures for the DriftStream-IDS test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path of the repository root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def config_dir(repo_root: Path) -> Path:
    """Absolute path of the Hydra config tree."""
    return repo_root / "configs"
