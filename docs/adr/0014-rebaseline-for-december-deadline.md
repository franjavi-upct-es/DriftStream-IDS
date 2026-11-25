<!-- docs/adr/0014-rebaseline-for-december-deadline.md -->
# ADR-014 — Re-baseline the scope for the 16 December 2026 deadline

- **Status:** accepted
- **Date:** 2026-11-25
- **Related:** ROADMAP.md §3–§6, §10; ARCHITECTURE.md §8.1, §11, §13, §14.2;
  partially supersedes ADR-008 (benchmark part) and ADR-011 (MLflow part)

## Context

The course deadline is **2026-12-16** (Q1), three weeks after the start
date. The baseline plan assumed ten weeks (ending 2027-02-04); even the
compressed six-week plan does not fit. Available effort is above 30 h/week
and the machine has 20 cores, 32 GB RAM and an RTX 5060 (8 GB), so compute
is not the constraint: development time is. Kyoto 2006+ is available for
2006–2015; the yearly archives are about 0.63 GB (2007), 1.07 GB (2008) and
2.16 GB (2009), compressed.

## Decision

Keep the research question, the hypotheses and both datasets, and keep the
Kafka–Spark layer, but cut every component to its minimum viable form
("lean core"):

| Area | Lean-core scope |
|---|---|
| Theory | Unchanged: `bounds.py`, `adwin_replay.py`, E0 → Figure 1 |
| Simulator | All P0 components; P1/P2 components deferred |
| CIC-IDS2017 | Unchanged (E1, 5 seeds; E3 basic injection) |
| Kyoto 2006+ | Window shortened to **2007-01 → 2008-12** (≈1.7 GB compressed) |
| Experiments | E0, E1, E2, E3 (basic). E4 reduced (ODS vs. ODU vs. burst k = 5) and the A-ATT/A-FEAT ablations only if ahead of schedule |
| Stream layer | Kafka (KRaft) + Spark scorer + replayer + **one control-plane service** that runs selector, oracle, detectors, policy and updater in global order; **file-based model registry** on a shared volume instead of MLflow; E5 parity on **CIC only, 1 s trigger** (5 s if time) |
| Deferred | E6 throughput, DDM, MMD, promotion gate, MLflow tracking/registry, Prometheus/Grafana, sensitivity sweep, stretch items, Zenodo |
| Essay | Unchanged structure; PDF via Pandoc + LaTeX + BibTeX, IEEE style; repository cited as `https://github.com/franjavi-upct-es/DriftStream-IDS` |

Literature work (Phase 7) starts on day 2 and runs in parallel with the
code, so Sections 2 and 4 can be drafted before the results exist.

## Consequences

- The confirmatory claims (H1–H4) are still testable: E0 validates the
  theory, E1/E2/E3 give the empirical evidence, E5 shows feasibility.
- H5 (exploratory) and the policy part of H4 (burst invariance) depend on
  the reduced E4; if E4 is not run, they are reported as not tested.
- The single control-plane service keeps the stream semantics identical
  to the simulator (single-partition order, ADR-009) with far less code;
  the essay describes it as a simplification of a per-service deployment.
- `ARCHITECTURE.md` keeps describing the full target design; this ADR and
  `ROADMAP.md` define what is built before the deadline.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Drop the Kafka–Spark layer | Loses the practical-validity evidence (O3) the course rewards |
| Drop Kyoto 2006+ | Loses the natural long-horizon drift; weaker external validity |
| Keep the full plan | Needs about ten weeks; misses the deadline |
