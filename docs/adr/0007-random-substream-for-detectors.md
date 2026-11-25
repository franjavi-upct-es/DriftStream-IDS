<!-- docs/adr/0007-random-substream-for-detectors.md -->
# ADR-007 — Supervised detectors use only random-substream labels

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §4.1 (A4), §9.2; hypothesis H5

## Context

Uncertainty-selected labels concentrate near the decision boundary, so their error rate overestimates the true error rate.

## Decision

ADWIN and DDM consume only the random share ρ·B of the labels. Learners may use all delayed labels.

## Consequences

Unbiased error estimates for supervised detection, at the cost of a slower detector when ρ is small; H5 reports the trade-off.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Feed all labels to the detector | Biased error estimate; alarms driven by selection |
