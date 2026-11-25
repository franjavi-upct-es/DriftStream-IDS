<!-- docs/adr/0004-corrected-cicids2017-only.md -->
# ADR-004 — Use only the corrected CIC-IDS2017

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §8.1, §8.3

## Context

Engelen et al. (2021) report that a large share of the original CIC-IDS2017 traces had to be reconstructed or relabelled; Arp et al. (2022) list such label errors as an evaluation pitfall.

## Decision

Only the DistriNet/KU Leuven corrected release is used. The original CSVs are never loaded, not even for comparison.

## Consequences

Results are comparable with the corrected-data literature. If the corrected link fails, the fallback is corrected CSE-CIC-IDS2018 (risk R3), not the original files.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Original CIC-IDS2017 CSVs | Documented labelling and construction errors |
