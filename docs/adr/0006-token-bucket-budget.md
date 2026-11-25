<!-- docs/adr/0006-token-bucket-budget.md -->
# ADR-006 — Token-bucket labelling budget with burst support

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §3.3, §9.3, §9.4

## Context

The budget B must be a hard, testable constraint, while the burst policy needs to spend saved budget faster for a short horizon.

## Decision

Each arriving flow adds B tokens up to a cap C; a query costs one token. Bursts raise the query rate but are financed only by saved tokens.

## Consequences

Guarantees labels spent ≤ B·i + C for every prefix i (property-tested). Bursts cannot exceed the long-run budget.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Bernoulli(B) per flow | No prefix guarantee; no way to save budget for a burst |
