<!-- docs/adr/0005-kyoto-leakage-removal.md -->
# ADR-005 — Kyoto 2006+ without detector-output columns

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §8.3, §15.4

## Context

Kyoto 2006+ ships `IDS_detection`, `Malware_detection` and `Ashula_detection`, which are outputs of other detectors and are strongly correlated with the label.

## Decision

The Kyoto ETL drops those three columns, the IP addresses and the source port. A validation assert fails the ETL if any of them survives.

## Consequences

Prevents label leakage and IP-based shortcuts. Absolute accuracy is lower than in papers that keep them; the essay states why.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Keep the columns as features | Label leakage: the model would learn the other detectors |
