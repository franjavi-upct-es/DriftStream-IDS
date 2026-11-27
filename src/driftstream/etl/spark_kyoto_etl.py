# src/driftstream/etl/spark_kyoto_etl.py
"""Kyoto 2006+ daily text files → canonical Parquet, with PySpark (T2.4).

Input format (``BenchmarkData-Description-New.pdf``, new_data201704
release, obtained from its Kaggle mirror, see
:mod:`driftstream.data.download`): tab-separated text, one file per
day (``YYYYMMDD.txt``), 24 columns in the order of
:data:`KYOTO_COLUMNS`. ``Label`` is ``1`` (normal), ``-1`` (known
attack) or ``-2`` (unknown attack). IP addresses
are sanitised IPv6 addresses whose mapping is consistent within a month
only.

Two facts the documentation does **not** state are configuration values
to verify on the first downloaded month (data card, T2.3): the timezone
of ``Start Time`` (``source_tz``, default ``Asia/Tokyo`` because the
honeypots are in Japan) and its exact format (``HH:mm:ss`` with optional
fractional seconds is accepted).

Spark performs the scan over the raw files (parsing, labels, leakage
removal, deterministic sampling). The sample, ≈ 1.5 M sessions for
2007-2009, fits in memory and goes through the same writer as CIC-IDS2017
(:mod:`driftstream.etl.writer`), so both datasets share one layout.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from driftstream.core.errors import DataValidationError, SchemaError
from driftstream.data.download import months
from driftstream.data.schema import (
    CATEGORICAL_PREFIX,
    NUMERIC_PREFIX,
    normalise_name,
)
from driftstream.data.splits import WarmupSpec, warmup_mask
from driftstream.etl.onsets import compute_onsets
from driftstream.etl.stats import compute_stats
from driftstream.etl.writer import finalise_frame, write_dataset

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

__all__ = [
    "KYOTO_COLUMNS",
    "LEAKAGE_COLUMNS",
    "KyotoEtlReport",
    "build_spark",
    "discover_day_files",
    "run_kyoto_etl",
]

log = logging.getLogger(__name__)

#: The 24 columns, in file order (new_data201704 documentation).
KYOTO_COLUMNS: tuple[str, ...] = (
    "Duration",
    "Service",
    "Source bytes",
    "Destination bytes",
    "Count",
    "Same srv rate",
    "Serror rate",
    "Srv serror rate",
    "Dst host count",
    "Dst host srv count",
    "Dst host same src port rate",
    "Dst host serror rate",
    "Dst host srv serror rate",
    "Flag",
    "IDS detection",
    "Malware detection",
    "Ashula detection",
    "Label",
    "Source IP Address",
    "Source Port Number",
    "Destination IP Address",
    "Destination Port Number",
    "Start Time",
    "Protocol",
)
#: Outputs of other detectors and host identifiers: removed (ADR-005).
LEAKAGE_COLUMNS: tuple[str, ...] = (
    "IDS detection",
    "Malware detection",
    "Ashula detection",
    "Source IP Address",
    "Source Port Number",
    "Destination IP Address",
)
CATEGORICAL: tuple[str, ...] = ("Service", "Flag", "Protocol")
NUMERIC: tuple[str, ...] = tuple(
    c
    for c in KYOTO_COLUMNS
    if c not in {*CATEGORICAL, *LEAKAGE_COLUMNS, "Label", "Start Time"}
)
_FAMILY = {"1": "BENIGN", "-1": "KNOWN", "-2": "UNKNOWN"}
_DATE_FILE = re.compile(r"(\d{8})\.txt$")
_SPARK_TIME = "yyyyMMdd HH:mm:ss[.SSSSSS]"
_DECEMBER = 12


def _col_name(raw: str) -> str:
    return "k_" + normalise_name(raw)  # internal Spark column name


def discover_day_files(raw_dir: Path, start: str, end: str) -> list[Path]:
    """Find the ``YYYYMMDD.txt`` files of a window under ``raw_dir``.

    Args:
        raw_dir: ``data/raw/kyoto2006`` (searched recursively).
        start: First month, ``YYYY-MM``.
        end: Last month, ``YYYY-MM``.

    Returns:
        Paths sorted by date.

    Raises:
        SchemaError: If no file matches or a date appears twice.
    """
    wanted = {f"{y}{m:02d}" for y, m in months(start, end)}
    by_date: dict[str, Path] = {}
    for path in sorted(Path(raw_dir).rglob("*.txt")):
        match = _DATE_FILE.search(path.name)
        if not match or match.group(1)[:6] not in wanted:
            continue
        key = match.group(1)
        if key in by_date:
            raise SchemaError(f"two files for {key}: {by_date[key]}, {path}")
        by_date[key] = path
    if not by_date:
        raise SchemaError(f"no Kyoto day files for {start}..{end} in {raw_dir}")
    return [by_date[k] for k in sorted(by_date)]


def _missing_days(files: list[Path], start: str, end: str) -> list[str]:
    present = {_DATE_FILE.search(p.name).group(1) for p in files}  # type: ignore[union-attr]
    y0, m0 = (int(v) for v in start[:7].split("-"))
    y1, m1 = (int(v) for v in end[:7].split("-"))
    day = date(y0, m0, 1)
    stop = date(y1 + (m1 == _DECEMBER), m1 % _DECEMBER + 1, 1)
    out = []
    while day < stop:
        if day.strftime("%Y%m%d") not in present:
            out.append(day.isoformat())
        day += timedelta(days=1)
    return out


@dataclass(slots=True)
class KyotoEtlReport:
    """What the ETL did, written to ``etl_report.json``.

    Attributes:
        files: Day files read.
        missing_days: Days of the window without a file.
        rows_read: Raw rows.
        invalid_label: Rows with a label outside {1, -1, -2} (dropped).
        invalid_time: Rows whose ``Start Time`` could not be parsed
            (dropped).
        sampling_fraction: Share of valid rows kept.
        rows_written: Rows in the processed table.
        source_tz: Timezone assumed for ``Start Time``.
        nan_imputed: NaN values imputed, per feature.
        imputation_medians: Warm-up medians used, per feature.
    """

    files: int = 0
    missing_days: list[str] = field(default_factory=list)
    rows_read: int = 0
    invalid_label: int = 0
    invalid_time: int = 0
    sampling_fraction: float = 1.0
    rows_written: int = 0
    source_tz: str = "Asia/Tokyo"
    nan_imputed: dict[str, int] = field(default_factory=dict)
    imputation_medians: dict[str, float] = field(default_factory=dict)


def build_spark(
    master: str = "local[*]",
    *,
    source_tz: str = "Asia/Tokyo",
    driver_memory: str = "4g",
) -> SparkSession:
    """Create the local Spark session used by the ETL.

    The session timezone is the timezone of the raw ``Start Time`` values,
    so Spark converts local wall-clock times to UTC epoch seconds.

    Args:
        master: Spark master URL.
        source_tz: IANA timezone of the raw timestamps.
        driver_memory: Driver memory (the sample is collected there).

    Returns:
        A Spark session (the caller stops it).
    """
    from pyspark.sql import SparkSession  # noqa: PLC0415 (optional dep)

    return (
        SparkSession.builder.master(master)
        .appName("driftstream-kyoto-etl")
        .config("spark.sql.session.timeZone", source_tz)
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.driver.memory", driver_memory)
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )


def _parse(spark: SparkSession, files: list[Path]) -> DataFrame:
    from pyspark.sql import functions as F  # noqa: N812, PLC0415
    from pyspark.sql.types import (  # noqa: PLC0415
        StringType,
        StructField,
        StructType,
    )

    schema = StructType(
        [StructField(_col_name(c), StringType(), True) for c in KYOTO_COLUMNS]
    )
    df = spark.read.csv(
        [str(p) for p in files], sep="\t", schema=schema, header=False
    )
    day = F.regexp_extract(F.input_file_name(), r"(\d{8})\.txt$", 1)
    stamp = F.concat_ws(" ", day, F.trim(F.col(_col_name("Start Time"))))
    ts = F.try_to_timestamp(stamp, F.lit(_SPARK_TIME))
    label = F.trim(F.col(_col_name("Label")))
    return (
        df.withColumn("_day", day)
        .withColumn("event_time", F.unix_micros(ts) / F.lit(1e6))
        .withColumn("label_raw", label)
        .withColumn(
            "y",
            F.when(label == "1", F.lit(0))
            .when(label.isin("-1", "-2"), F.lit(1))
            .otherwise(F.lit(None)),
        )
        .withColumn(
            "family",
            F.when(label == "1", "BENIGN")
            .when(label == "-1", "KNOWN")
            .when(label == "-2", "UNKNOWN"),
        )
    )


def _select_canonical(df: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F  # noqa: N812, PLC0415

    cols: list[Any] = [
        F.col("event_time"),
        F.col("y").cast("byte").alias("y"),
        F.col("family"),
        F.col("label_raw"),
    ]
    cols += [
        F.col(_col_name(c))
        .try_cast("double")
        .alias(NUMERIC_PREFIX + normalise_name(c))
        for c in NUMERIC
    ]
    cols += [
        F.trim(F.col(_col_name(c))).alias(
            CATEGORICAL_PREFIX + normalise_name(c)
        )
        for c in CATEGORICAL
    ]
    out = df.select(*cols)
    banned = {normalise_name(c) for c in LEAKAGE_COLUMNS}
    leaked = {c for c in out.columns if c[2:] in banned}
    if leaked:  # defensive: the select above never includes them
        raise SchemaError(f"leakage columns survived: {sorted(leaked)}")
    return out


def run_kyoto_etl(
    raw_dir: Path,
    out_dir: Path,
    *,
    start: str,
    end: str,
    warmup: WarmupSpec,
    target_sessions: int = 1_500_000,
    sample_seed: int = 0,
    source_tz: str = "Asia/Tokyo",
    spark: SparkSession | None = None,
    master: str = "local[*]",
) -> KyotoEtlReport:
    """Run the Kyoto 2006+ ETL end to end.

    Args:
        raw_dir: ``data/raw/kyoto2006``.
        out_dir: ``data/processed/kyoto2006``.
        start: First month of the window, ``YYYY-MM``.
        end: Last month of the window, ``YYYY-MM``.
        warmup: Warm-up slice (fits the imputation medians).
        target_sessions: Expected rows after sampling.
        sample_seed: Seed of the hash-based sampling.
        source_tz: Timezone of ``Start Time``.
        spark: Existing session (tests); otherwise one is created and
            stopped.
        master: Spark master URL when a session is created.

    Returns:
        The ETL report (also written to ``etl_report.json``).
    """
    from pyspark.sql import functions as F  # noqa: N812, PLC0415

    files = discover_day_files(raw_dir, start, end)
    report = KyotoEtlReport(
        files=len(files),
        missing_days=_missing_days(files, start, end),
        source_tz=source_tz,
    )
    own = spark is None
    session = spark or build_spark(master, source_tz=source_tz)
    try:
        session.conf.set("spark.sql.session.timeZone", source_tz)
        parsed = _parse(session, files).cache()
        report.rows_read = parsed.count()
        report.invalid_label = parsed.filter(F.col("y").isNull()).count()
        report.invalid_time = parsed.filter(
            F.col("event_time").isNull()
        ).count()
        valid = parsed.filter(
            F.col("y").isNotNull() & F.col("event_time").isNotNull()
        )
        n_valid = valid.count()
        frac = min(1.0, target_sessions / n_valid) if n_valid else 0.0
        report.sampling_fraction = frac
        raw_cols = [F.col(_col_name(c)) for c in KYOTO_COLUMNS]
        h = F.xxhash64(F.lit(sample_seed), F.col("_day"), *raw_cols)
        u = F.pmod(h, F.lit(1 << 53)) / F.lit(float(1 << 53))
        sampled = _select_canonical(valid.filter(u < F.lit(frac)))
        pdf = sampled.toPandas()
        parsed.unpersist()
    finally:
        if own:
            session.stop()
    if pdf.empty:
        raise DataValidationError(["Kyoto ETL produced no rows"])
    pdf = _impute(pdf, warmup, report)
    df = finalise_frame(pdf)
    report.rows_written = len(df)
    write_dataset(
        df,
        "kyoto2006",
        out_dir,
        partition="month",
        extra_files={
            "etl_report.json": asdict(report),
            "drift_onsets.json": compute_onsets(
                df, warmup=warmup, min_flows=0, expected_day=None
            ),
            "stats.json": compute_stats(
                df, warmup=warmup, period="month", rate_bin="day"
            ),
        },
    )
    return report


def _impute(
    df: pd.DataFrame, warmup: WarmupSpec, report: KyotoEtlReport
) -> pd.DataFrame:
    feats = [c for c in df.columns if c.startswith(NUMERIC_PREFIX)]
    warm = warmup_mask(df["event_time"].to_numpy(), warmup)
    if not warm.any():
        raise DataValidationError(["warm-up slice is empty"])
    medians = df.loc[warm, feats].median(skipna=True)
    for col in feats:
        values = df[col].replace([np.inf, -np.inf], np.nan)
        n = int(values.isna().sum())
        if n:
            report.nan_imputed[col] = n
        med = float(medians[col]) if pd.notna(medians[col]) else 0.0
        report.imputation_medians[col] = med
        df[col] = values.fillna(med)
    for col in (c for c in df.columns if c.startswith(CATEGORICAL_PREFIX)):
        df[col] = df[col].fillna("<missing>")
    return df
