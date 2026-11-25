<!-- docs/adr/0009-single-partition-stateful-topics.md -->
# ADR-009 — Single-partition topics for stateful services

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §13.3

## Context

The selector, oracle, updater, drift monitor and policy are order-sensitive, exactly like the simulator loop.

## Decision

Every topic consumed by a stateful service has one partition. Only the stateless scoring path is scaled with partitions (E6).

## Consequences

Global order keeps the stream semantics identical to the simulator. The stateful path cannot scale horizontally; this is acceptable for a research testbed.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Keyed partitions everywhere | Breaks the global ordering parity relies on |
