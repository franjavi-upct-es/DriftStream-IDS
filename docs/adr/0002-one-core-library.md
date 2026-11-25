<!-- docs/adr/0002-one-core-library.md -->
# ADR-002 — One core library shared by both execution modes

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §5, §6; PROJECT_STRUCTURE.md §4

## Context

Parity between the simulator and the stream mode is only meaningful if both execute the same scientific logic.

## Decision

Learners, selectors, oracle, detectors, policies and evaluation live once in `src/driftstream/`. Stream services are thin adapters built through `simulate/builder.py`.

## Consequences

No duplicated logic; a bug fix applies to both modes. Components must stay free of Kafka/Spark imports (import-linter contract `deploy-is-leaf`).

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Separate stream implementation | Parity would test two codebases, not one design |
