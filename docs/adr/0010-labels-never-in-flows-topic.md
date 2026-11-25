<!-- docs/adr/0010-labels-never-in-flows-topic.md -->
# ADR-010 — Labels never travel in flows.raw

- **Status:** accepted
- **Date:** 2026-11-24
- **Related:** ARCHITECTURE.md §3.2, §13.2

## Context

A label in the scoring path could leak into the model and would be unrealistic: a sensor never knows the ground truth.

## Decision

The replayer strips `y` and `family`. The label oracle reads ground truth from Parquet by `flow_id` and releases it after the delay.

## Consequences

The scorer cannot leak labels by construction. The oracle needs read access to the processed data; this is documented as a testbed simplification.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Labels in a separate field of flows.raw | Leak-prone; unrealistic |
