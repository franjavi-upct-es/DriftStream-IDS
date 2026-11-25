# tests/unit/test_cli.py
"""The CLI exposes every planned command (ROADMAP T0.4 acceptance)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from driftstream import __version__
from driftstream.cli import EXIT_NOT_IMPLEMENTED, app

pytestmark = pytest.mark.unit

runner = CliRunner()

# Command paths from PROJECT_STRUCTURE.md §6, with the minimum arguments
# each one needs to get past argument parsing.
PLANNED_COMMANDS: list[list[str]] = [
    ["run", "experiment=e1_cic_grid"],
    ["bench"],
    ["data", "download", "--dataset", "all"],
    ["data", "etl", "--dataset", "cic"],
    ["data", "validate", "--dataset", "kyoto"],
    ["theory", "predict"],
    ["analyze", "aggregate", "--experiment", "e1_cic_grid"],
    ["analyze", "hypotheses"],
    ["analyze", "figures"],
    ["analyze", "tables"],
    ["stream", "up"],
    ["stream", "down"],
    ["stream", "status"],
    ["stream", "run", "--experiment", "e5_parity_cic"],
    ["stream", "compare", "--run", "results/stream/x"],
    ["essay", "build", "--format", "docx"],
    ["essay", "wordcount"],
]


def test_help_lists_top_level_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("run", "bench", "data", "theory", "analyze", "stream"):
        assert name in result.output
    assert "essay" in result.output


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__


@pytest.mark.parametrize("argv", PLANNED_COMMANDS, ids=" ".join)
def test_planned_command_exits_not_implemented(argv: list[str]) -> None:
    result = runner.invoke(app, argv)
    assert result.exit_code == EXIT_NOT_IMPLEMENTED, result.output


def test_unknown_dataset_is_rejected() -> None:
    result = runner.invoke(app, ["data", "etl", "--dataset", "unsw"])
    assert result.exit_code == 2  # Click usage error
