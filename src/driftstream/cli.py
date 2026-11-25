# src/driftstream/cli.py
"""Command-line interface for DriftStream-IDS (PROJECT_STRUCTURE.md §6).

Every command exists from Phase 0 so the interface is stable. Commands
that are not implemented yet exit with :data:`EXIT_NOT_IMPLEMENTED` and
name the ROADMAP task that will implement them, so a missing feature is
never mistaken for a silent success.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, NoReturn

import typer
from rich.console import Console

from driftstream import __version__

#: Exit code returned by commands that are planned but not implemented.
EXIT_NOT_IMPLEMENTED = 3

_err = Console(stderr=True)

app = typer.Typer(
    name="driftstream",
    help="Verification latency and labelling budgets in streaming NIDS.",
    no_args_is_help=True,
    add_completion=False,
)
data_app = typer.Typer(
    help="Download, ETL and validation of the datasets.",
    no_args_is_help=True,
)
theory_app = typer.Typer(
    help="Analytic predictions (ARCHITECTURE.md §4).",
    no_args_is_help=True,
)
analyze_app = typer.Typer(
    help="Aggregation, hypothesis tests, figures and tables.",
    no_args_is_help=True,
)
stream_app = typer.Typer(
    help="Kafka-Spark stream mode (docker compose lifecycle and runs).",
    no_args_is_help=True,
)
essay_app = typer.Typer(
    help="Essay build and word count.",
    no_args_is_help=True,
)

app.add_typer(data_app, name="data")
app.add_typer(theory_app, name="theory")
app.add_typer(analyze_app, name="analyze")
app.add_typer(stream_app, name="stream")
app.add_typer(essay_app, name="essay")


class DatasetChoice(StrEnum):
    """Datasets accepted by the data commands."""

    CIC = "cic"
    KYOTO = "kyoto"
    ALL = "all"


class EssayFormat(StrEnum):
    """Output formats of the essay build."""

    PDF = "pdf"
    DOCX = "docx"


def _not_implemented(command: str, task: str) -> NoReturn:
    """Report a planned command and exit with a dedicated code.

    Args:
        command: Name of the command as typed by the user.
        task: ROADMAP task ID that will implement the command.

    Raises:
        typer.Exit: Always, with code :data:`EXIT_NOT_IMPLEMENTED`.
    """
    _err.print(
        f"[yellow]`driftstream {command}` is not implemented yet[/yellow] "
        f"(planned in ROADMAP task {task})."
    )
    raise typer.Exit(code=EXIT_NOT_IMPLEMENTED)


# --------------------------------------------------------------------------
# Top-level commands
# --------------------------------------------------------------------------
@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command(
    context_settings={"allow_extra_args": True},
)
def run(
    overrides: Annotated[
        list[str] | None,
        typer.Argument(help="Hydra overrides, e.g. experiment=e1_cic_grid."),
    ] = None,
) -> None:
    """Run one config, or a sweep through experiment=...."""
    _not_implemented("run", "T3.8")


@app.command()
def bench() -> None:
    """Measure simulator throughput in flows per second."""
    _not_implemented("bench", "T3.12")


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
@data_app.command("download")
def data_download(
    dataset: Annotated[
        DatasetChoice, typer.Option(help="Dataset to download.")
    ] = DatasetChoice.ALL,
) -> None:
    """Download raw data and verify it against data/CHECKSUMS.raw."""
    _not_implemented("data download", "T2.1 / T2.3")


@data_app.command("etl")
def data_etl(
    dataset: Annotated[DatasetChoice, typer.Option(help="Dataset to process.")],
    spark_master: Annotated[
        str, typer.Option(help="Spark master URL (Kyoto ETL only).")
    ] = "local[*]",
) -> None:
    """Run the raw-to-processed ETL for one dataset."""
    _not_implemented("data etl", "T2.2 / T2.4")


@data_app.command("validate")
def data_validate(
    dataset: Annotated[
        DatasetChoice, typer.Option(help="Dataset to validate.")
    ],
) -> None:
    """Run post-ETL assertions and write stats.json."""
    _not_implemented("data validate", "T2.5")


# --------------------------------------------------------------------------
# theory
# --------------------------------------------------------------------------
@theory_app.command("predict")
def theory_predict(
    config_name: Annotated[
        str, typer.Option(help="Hydra config name.")
    ] = "config",
    overrides: Annotated[
        list[str] | None, typer.Argument(help="Hydra overrides.")
    ] = None,
) -> None:
    """Print and save the analytic predictions for a config."""
    _not_implemented("theory predict", "T1.3")


# --------------------------------------------------------------------------
# analyze
# --------------------------------------------------------------------------
@analyze_app.command("aggregate")
def analyze_aggregate(
    experiment: Annotated[str, typer.Option(help="Experiment name.")],
) -> None:
    """Collect run directories into results/aggregated/."""
    _not_implemented("analyze aggregate", "T6.1")


@analyze_app.command("hypotheses")
def analyze_hypotheses() -> None:
    """Apply the pre-registered H1-H5 decision rules."""
    _not_implemented("analyze hypotheses", "T6.2")


@analyze_app.command("figures")
def analyze_figures() -> None:
    """Regenerate every essay figure."""
    _not_implemented("analyze figures", "T6.3")


@analyze_app.command("tables")
def analyze_tables() -> None:
    """Regenerate every essay table."""
    _not_implemented("analyze tables", "T6.4")


# --------------------------------------------------------------------------
# stream
# --------------------------------------------------------------------------
@stream_app.command("up")
def stream_up() -> None:
    """Start the docker compose core profile."""
    _not_implemented("stream up", "T5.1")


@stream_app.command("down")
def stream_down() -> None:
    """Stop the docker compose stack."""
    _not_implemented("stream down", "T5.1")


@stream_app.command("status")
def stream_status() -> None:
    """Show the health of every stream service."""
    _not_implemented("stream status", "T5.1")


@stream_app.command("run")
def stream_run(
    experiment: Annotated[str, typer.Option(help="Stream experiment name.")],
) -> None:
    """Replay a dataset through Kafka-Spark and sink the topics."""
    _not_implemented("stream run", "T5.8")


@stream_app.command("compare")
def stream_compare(
    run_dir: Annotated[
        str, typer.Option("--run", help="Stream run directory.")
    ],
) -> None:
    """Compute parity metrics between a stream run and the simulator."""
    _not_implemented("stream compare", "T5.6")


# --------------------------------------------------------------------------
# essay
# --------------------------------------------------------------------------
@essay_app.command("build")
def essay_build(
    fmt: Annotated[
        EssayFormat, typer.Option("--format", help="Output format.")
    ] = EssayFormat.PDF,
) -> None:
    """Build the essay with Pandoc."""
    _not_implemented("essay build", "T7.8")


@essay_app.command("wordcount")
def essay_wordcount() -> None:
    """Count essay words, excluding the references."""
    _not_implemented("essay wordcount", "T7.4")


if __name__ == "__main__":  # pragma: no cover
    app()
