<!-- docs/adr/0012-preregistration.md -->
# ADR-012 — Pre-register H1–H4 before running E1/E2

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §2.3, §12; docs/preregistration.md

## Context

With many configurations and metrics, choosing hypotheses after seeing results (HARKing) would weaken every claim in the essay.

## Decision

Hypotheses, decision rules, metrics, exclusions and the analysis plan are frozen in `docs/preregistration.md` at tag `prereg-v1`, after E0 and before E1/E2.

## Consequences

Confirmatory claims are limited to H1–H4; everything else is exploratory. Later changes go to a Deviations section, never into the frozen text.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| No pre-registration | Weaker claims; easy to overfit the analysis |
