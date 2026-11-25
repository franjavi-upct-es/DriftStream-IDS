<!-- docs/adr/0011-hydra-and-mlflow.md -->
# ADR-011 — Hydra configs with config hashing; MLflow for tracking

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** PROJECT_STRUCTURE.md §5; ARCHITECTURE.md §14.2, §15

## Context

Every run must be fully defined by a config, sweeps must be easy, and provenance must be auditable.

## Decision

Hydra composes configs and drives sweeps; a run is identified by the hash of its resolved config plus its seed. MLflow is the model registry in stream mode and optional tracking in simulate mode.

## Consequences

Reproducible run directories and skip-if-done logic. Note: Hydra's `# @package` directive must be the first line of a file, so experiment configs carry their path comment on line 2 (decision log, 2026-11-25).

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| argparse + YAML | No composition or sweeps |
| Weights & Biases | Hosted; not needed for a local testbed |
