# tests/unit/test_cli.py
"""The CLI exposes every planned command (ROADMAP T0.4 acceptance)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from driftstream import __version__
from driftstream.cli import EXIT_NOT_IMPLEMENTED, app

pytestmark = pytest.mark.unit

runner = CliRunner()
CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"

# Command paths from PROJECT_STRUCTURE.md §6, with the minimum arguments
# each one needs to get past argument parsing.
PLANNED_COMMANDS: list[list[str]] = [
    ["run", "experiment=e1_cic_grid"],
    ["bench"],
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


def test_theory_predict_prints_json(tmp_path: Path) -> None:
    out = tmp_path / "theory.json"
    argv = [
        "theory",
        "predict",
        "--rate",
        "10",
        "--eps0",
        "0.05",
        "--eps1",
        "0.25",
        "--m-a",
        "500",
        "--n-pre-flows",
        "100000",
        "--n-flows",
        "200000",
        "--config-dir",
        str(CONFIG_DIR),
        "--out",
        str(out),
        "oracle.delay.mean_seconds=600",
        "detector=ks_scores",
    ]
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    assert payload["inputs"]["delay"] == 600.0
    pred = payload["prediction"]
    assert pred["tau_det_sup"] is None  # KS config: no supervised detector
    assert pred["tau_det_unsup"] is None  # no KS distance given
    assert pred["floor"] == pytest.approx(600 + 450 / 0.1)


def test_data_commands_end_to_end(cic_raw_dir: Path, tmp_path: Path) -> None:
    """etl + validate through the CLI, with config overrides for paths."""
    out = tmp_path / "processed"
    paths = [f"dataset.raw_dir={cic_raw_dir}", f"dataset.processed_dir={out}"]
    common = ["--config-dir", str(CONFIG_DIR)]
    etl = runner.invoke(
        app, ["data", "etl", "--dataset", "cic", *common, *paths]
    )
    assert etl.exit_code == 0, etl.output
    assert "rows written" in etl.output
    ok = runner.invoke(
        app, ["data", "validate", "--dataset", "cic", *common, *paths]
    )
    assert ok.exit_code == 0, ok.output
    assert "0 failed" in ok.output
    (out / "stats.json").unlink()
    bad = runner.invoke(
        app, ["data", "validate", "--dataset", "cic", *common, *paths]
    )
    assert bad.exit_code == 1


def test_data_download_uses_the_checksum_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import zipfile  # noqa: PLC0415

    from driftstream.data import download  # noqa: PLC0415

    archive = tmp_path / "CICIDS2017_improved.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("monday.csv", "a\n")
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setattr(download, "CIC_URL", archive.as_uri())
    argv = [
        "data",
        "download",
        "--dataset",
        "cic",
        "--data-root",
        str(data_root),
        "--config-dir",
        str(CONFIG_DIR),
    ]
    first = runner.invoke(app, argv)
    assert first.exit_code == 0, first.output
    assert "checksum recorded" in first.output
    strict = runner.invoke(app, [*argv, "--strict"])
    assert "checksum verified" in strict.output


def test_unknown_dataset_is_rejected() -> None:
    result = runner.invoke(app, ["data", "etl", "--dataset", "unsw"])
    assert result.exit_code == 2  # Click usage error
