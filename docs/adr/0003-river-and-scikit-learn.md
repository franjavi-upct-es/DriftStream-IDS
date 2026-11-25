<!-- docs/adr/0003-river-and-scikit-learn.md -->
# ADR-003 — River for online learning and detectors; scikit-learn for batch

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §9

## Context

The project needs mature, citable implementations of ARF, ADWIN and DDM, plus a strong batch baseline, all in Python.

## Decision

Use River (Montiel et al. 2021) for ARF, ADWIN and DDM, and scikit-learn `HistGradientBoostingClassifier` for the static and batch learners.

## Consequences

Well-known implementations reviewers can check. The ADWIN prediction in `theory/adwin_replay.py` must follow River's exact cut condition and clock, not only the paper.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| MOA (Java) | Breaks the single-Python-library design |
| Own implementations | Unverified and less credible |
