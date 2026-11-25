<!-- docs/adr/0001-simulator-first.md -->
# ADR-001 — Science runs in a deterministic simulator

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §5, §7; ROADMAP Phases 3–5

## Context

The research question needs hundreds of runs over a D × B grid, paired across seeds. A real streaming stack is non-deterministic (micro-batching, scheduling) and far slower per run.

## Decision

All confirmatory experiments (E0–E4) run in a discrete-event simulator driven by event time. The Kafka–Spark deployment is used only to show parity (E5) and feasibility (E6).

## Consequences

Runs are fast and bit-reproducible, so hypothesis tests are meaningful. The price is a deployment gap that must be measured, not assumed away: E5 quantifies it and the essay reports it.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Run every experiment on Kafka–Spark | Too slow for the grid; results not bit-reproducible |
| Use River's evaluation helpers only | No budgets, selectors, policies or alarm bookkeeping |
