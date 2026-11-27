# src/driftstream/cli.py
"""Command-line interface for DriftStream-IDS (PROJECT_STRUCTURE.md §6).

Every command exists from Phase 0 so the interface is stable. Commands
that are not implemented yet exit with :data:`EXIT_NOT_IMPLEMENTED` and
name the ROADMAP task that will implement them, so a missing feature is
never mistaken for a silent success.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
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
_DATASET_CONFIG = {
    DatasetChoice.CIC: "cicids2017",
    DatasetChoice.KYOTO: "kyoto2006",
}


def _selected(dataset: DatasetChoice) -> list[DatasetChoice]:
    if dataset is DatasetChoice.ALL:
        return [DatasetChoice.CIC, DatasetChoice.KYOTO]
    return [dataset]


def _dataset_cfg(
    dataset: DatasetChoice, config_dir: Path, overrides: list[str] | None
) -> dict[str, object]:
    """Compose the Hydra config and return the ``dataset`` node."""
    from hydra import compose, initialize_config_dir  # noqa: PLC0415
    from omegaconf import OmegaConf  # noqa: PLC0415

    name = _DATASET_CONFIG[dataset]
    with initialize_config_dir(
        config_dir=str(config_dir.resolve()), version_base="1.3"
    ):
        cfg = compose(
            config_name="config",
            overrides=[f"dataset={name}", *(overrides or [])],
        )
    node = OmegaConf.to_container(cfg.dataset, resolve=True)
    assert isinstance(node, dict)
    return {str(k): v for k, v in node.items()}


ConfigDir = Annotated[Path, typer.Option(help="Hydra config directory.")]
DataRoot = Annotated[Path, typer.Option(help="The data/ directory.")]
Overrides = Annotated[
    list[str] | None,
    typer.Argument(help="Hydra overrides, e.g. dataset.window.end=2007-03-31."),
]


@data_app.command("download")
def data_download(
    dataset: Annotated[
        DatasetChoice, typer.Option(help="Dataset to download.")
    ] = DatasetChoice.ALL,
    strict: Annotated[
        bool, typer.Option(help="Refuse files without a recorded checksum.")
    ] = False,
    extract: Annotated[bool, typer.Option(help="Unzip archives.")] = True,
    data_root: DataRoot = Path("data"),
    config_dir: ConfigDir = Path("configs"),
    overrides: Overrides = None,
) -> None:
    """Download raw data and verify it against data/CHECKSUMS.raw.

    The first download of a file records its SHA-256 (trust on first use;
    commit data/CHECKSUMS.raw afterwards); later downloads must match.
    """
    from driftstream.data.download import (  # noqa: PLC0415
        Checksums,
        cic_files,
        kyoto_files,
        sync,
    )

    sums = Checksums(data_root / "CHECKSUMS.raw")
    for ds in _selected(dataset):
        cfg = _dataset_cfg(ds, config_dir, overrides)
        if ds is DatasetChoice.CIC:
            files = cic_files()
        else:
            window = cfg["window"]
            assert isinstance(window, dict)
            files = kyoto_files(str(window["start"]), str(window["end"]))
            if not all((data_root / f.target).exists() for f in files):
                typer.echo(
                    "kyoto2006: downloading the Kaggle archive (≈ 14.5 GB; "
                    "an interrupted download resumes on the next run)"
                )
        for res in sync(files, data_root, sums, strict=strict, extract=extract):
            got = "downloaded" if res.downloaded else "present"
            typer.echo(
                f"{res.file.target}: {got}, checksum {res.status}, "
                f"{res.extracted} files extracted"
            )


@data_app.command("etl")
def data_etl(
    dataset: Annotated[DatasetChoice, typer.Option(help="Dataset to process.")],
    spark_master: Annotated[
        str, typer.Option(help="Spark master URL (Kyoto ETL only).")
    ] = "local[*]",
    config_dir: ConfigDir = Path("configs"),
    overrides: Overrides = None,
) -> None:
    """Run the raw-to-processed ETL for one dataset."""
    from driftstream.data.splits import WarmupSpec  # noqa: PLC0415

    for ds in _selected(dataset):
        cfg = _dataset_cfg(ds, config_dir, overrides)
        warmup = WarmupSpec.from_config(cfg["warmup"])  # type: ignore[arg-type]
        raw, out = Path(str(cfg["raw_dir"])), Path(str(cfg["processed_dir"]))
        if ds is DatasetChoice.CIC:
            from driftstream.etl.cicids2017 import run_cic_etl  # noqa: PLC0415

            report: object = run_cic_etl(
                raw,
                out,
                warmup=warmup,
                attempted_policy=cfg["attempted_policy"],  # type: ignore[arg-type]
                dedup=bool(cfg["dedup"]),
                min_family_flows=int(cfg["min_family_flows"]),  # type: ignore[call-overload]
            )
        else:
            from driftstream.etl.spark_kyoto_etl import (  # noqa: PLC0415
                run_kyoto_etl,
            )

            window = cfg["window"]
            assert isinstance(window, dict)
            report = run_kyoto_etl(
                raw,
                out,
                start=str(window["start"]),
                end=str(window["end"]),
                warmup=warmup,
                target_sessions=int(cfg["target_sessions"]),  # type: ignore[call-overload]
                sample_seed=int(cfg["sample_seed"]),  # type: ignore[call-overload]
                source_tz=str(cfg["source_tz"]),
                master=spark_master,
            )
        rows = getattr(report, "rows_written", "?")
        typer.echo(f"{cfg['name']}: {rows} rows written to {out}")


@data_app.command("validate")
def data_validate(
    dataset: Annotated[
        DatasetChoice, typer.Option(help="Dataset to validate.")
    ],
    config_dir: ConfigDir = Path("configs"),
    overrides: Overrides = None,
) -> None:
    """Run the post-ETL checks; exit with code 1 if any fails."""
    from driftstream.data.splits import WarmupSpec  # noqa: PLC0415
    from driftstream.etl.validate import validate_dataset  # noqa: PLC0415

    failed = False
    for ds in _selected(dataset):
        cfg = _dataset_cfg(ds, config_dir, overrides)
        report = validate_dataset(
            str(cfg["name"]),
            Path(str(cfg["processed_dir"])),
            warmup=WarmupSpec.from_config(cfg["warmup"]),  # type: ignore[arg-type]
        )
        typer.echo(
            f"{report.dataset}: {report.n_rows} rows, "
            f"{len(report.passed)} checks passed, "
            f"{len(report.failures)} failed"
        )
        for name, msg in report.failures.items():
            _err.print(f"  [red]FAIL[/red] {name}: {msg}")
        failed = failed or not report.ok
    if failed:
        raise typer.Exit(code=1)


# --------------------------------------------------------------------------
# theory
# --------------------------------------------------------------------------
def _json_safe(value: object) -> object:
    """Replace non-finite floats by ``None`` (never happens / censored)."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


@theory_app.command("predict")
def theory_predict(
    rate: Annotated[float, typer.Option(help="Arrival rate, flows/s.")],
    eps0: Annotated[float, typer.Option(help="Pre-drift error rate.")],
    eps1: Annotated[float, typer.Option(help="Post-drift error rate.")],
    m_a: Annotated[
        float,
        typer.Option("--m-a", help="Post-drift labels the learner needs."),
    ],
    n_pre_flows: Annotated[
        int, typer.Option(help="Flows seen by the detector before the drift.")
    ],
    overrides: Annotated[
        list[str] | None,
        typer.Argument(help="Hydra overrides, e.g. oracle.budget=0.05."),
    ] = None,
    ks_distance: Annotated[
        float | None,
        typer.Option(help="KS distance between pre/post score CDFs."),
    ] = None,
    n_flows: Annotated[
        int, typer.Option(help="Flows in the streaming phase.")
    ] = 1,
    config_dir: Annotated[
        Path, typer.Option(help="Hydra config directory.")
    ] = Path("configs"),
    config_name: Annotated[
        str, typer.Option(help="Hydra config name.")
    ] = "config",
    out: Annotated[
        Path | None, typer.Option(help="Also write the JSON to this file.")
    ] = None,
) -> None:
    """Print the analytic predictions (seconds after onset) as JSON.

    Design factors (D, B, rho, C, detector and policy parameters) come from
    the Hydra config; measured stream quantities come from the options.
    ``null`` means the event never happens under the model.
    """
    from hydra import compose, initialize_config_dir  # noqa: PLC0415
    from omegaconf import OmegaConf  # noqa: PLC0415

    from driftstream.theory.bounds import predict  # noqa: PLC0415
    from driftstream.theory.from_config import (  # noqa: PLC0415
        StreamQuantities,
        inputs_from_config,
    )

    with initialize_config_dir(
        config_dir=str(config_dir.resolve()), version_base="1.3"
    ):
        cfg = compose(config_name=config_name, overrides=overrides or [])
    plain = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(plain, dict)
    cfg_map = {str(k): v for k, v in plain.items()}
    stream = StreamQuantities(
        rate=rate,
        eps0=eps0,
        eps1=eps1,
        m_a=m_a,
        n_pre_flows=n_pre_flows,
        ks_distance=ks_distance,
        n_flows=n_flows,
    )
    inputs = inputs_from_config(cfg_map, stream)
    payload = {
        "inputs": _json_safe(asdict(inputs)),
        "prediction": _json_safe(predict(inputs).to_dict()),
    }
    text = json.dumps(payload, indent=2)
    typer.echo(text)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")


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
