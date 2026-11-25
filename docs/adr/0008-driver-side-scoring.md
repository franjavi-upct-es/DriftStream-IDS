<!-- docs/adr/0008-driver-side-scoring.md -->
# ADR-008 — Driver-side scoring in foreachBatch

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §13.7; experiment E6

## Context

River models are small, stateful Python objects that change version during a run.

## Decision

The Spark scorer reloads the champion on version change and scores each micro-batch on the driver inside `foreachBatch`. A `mapInPandas` variant with a broadcast snapshot is benchmarked in E6.

## Consequences

Simple and correct for the parity slices. Throughput is limited by the driver; E6 measures by how much.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| `mapInPandas` with broadcast | Extra serialisation per batch; kept as the E6 alternative |
| Model server (REST) | Adds network latency and a service |
