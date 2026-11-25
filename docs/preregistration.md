<!-- docs/preregistration.md -->

# Pre-registration — DriftStream-IDS

| Field                 | Value                                                      |
| --------------------- | ---------------------------------------------------------- |
| Status                | **DRAFT** — not frozen                                     |
| Freeze point          | Milestone M3, git tag `prereg-v1` (after E0, before E1/E2) |
| Authoritative sources | `ARCHITECTURE.md` §2.3 (hypotheses), §12 (analysis plan)   |
| Completed in          | ROADMAP task T1.4; frozen in T4.2                          |

> **Rule (ADR-012):** once tagged `prereg-v1`, the sections below are not
> edited. Any change is recorded in **Deviations** with a date, a reason and its
> expected effect on the conclusions.

## 1. Research question

_How much post-drift detection performance can a streaming flow-based NIDS
recover when ground-truth labels arrive with realistic delays and under a fixed
analyst labelling budget, compared with the immediate-label assumption used in
most drift-adaptation studies?_

## 2. Hypotheses and decision rules

| ID                 | Hypothesis                | Primary experiment | Decision rule    |
| ------------------ | ------------------------- | ------------------ | ---------------- |
| H1                 | _To be completed in T1.4_ | E0, E3, E1         |                  |
| H2                 |                           | E0, E1, E3         |                  |
| H3                 |                           | E0, E1, E2, E3     |                  |
| H4                 |                           | E1, E2, E4         |                  |
| H5 _(exploratory)_ |                           | E1, E4             | Descriptive only |

## 3. Primary metrics

_To be completed in T1.4 (detection delay, recovery time, label-latency regret
per 1,000 flows; definitions from ARCHITECTURE.md §10.2)._

## 4. Exclusions

_To be completed in T1.4. Planned: CIC families with too few flows for per-onset
delay analysis (e.g. Heartbleed, Infiltration) are excluded from the per-onset
analysis but kept in aggregate metrics._

## 5. Seeds and pairing

_To be completed in T1.4._

## 6. Analysis plan

_To be completed in T1.4 from ARCHITECTURE.md §12._

## 7. Sensitivity analyses

_To be completed in T1.5 (ADWIN δ, KS window sizes; E0 only)._

## Deviations

_None yet. Entries are added only after the freeze._

| Date | Section | Change | Reason | Expected effect |
| ---- | ------- | ------ | ------ | --------------- |
