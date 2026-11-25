<!-- docs/adr/0013-pyspark-batch-etl.md -->
# ADR-013 — PySpark batch for Kyoto ETL and an optional sweep runner

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §7.3, §8.3

## Context

Kyoto 2006+ is a large set of daily text files; the grids are embarrassingly parallel.

## Decision

The Kyoto ETL runs as a PySpark batch job. An optional Hydra launcher distributes independent runs as Spark tasks.

## Consequences

Scales the ETL beyond pandas and shows a legitimate batch use of Spark, separate from the streaming layer. PySpark must match the Spark image version (IMAGES.lock).

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| pandas in chunks | Slower and more code for the same job |
| Dask | Another engine to learn and pin |
