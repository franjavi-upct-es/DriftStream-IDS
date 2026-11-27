<!-- docs/lab_notebook.md -->

# Lab notebook — DriftStream-IDS

Dated log of findings, anomalies, surprises and ideas. Newest entry first. Every
entry that touches a result names the run directory or commit it comes from.

Entry format:

```markdown
## YYYY-MM-DD — <short title>

- **Context:** task ID, experiment, run directory or commit
- **Observation:** what happened (numbers with units)
- **Interpretation:** what it probably means; how sure
- **Action:** what changes, if anything (task, ADR, deviation)
```

---

## 2026-11-25 — Phase 2: what the real CIC-IDS2017 files contain

- **Context:** T2.1/T2.2; the dataset authors' labelling notebook
  (`GintsEngelen/CNS2022_Code`) and the DistriNet download pages.
- **Observation 1:** the latest release is CNS 2022 (`CICIDS2017_improved.zip`),
  with timestamps in UTC (µs precision), an `id` column,
  `"<attack> - Attempted"` labels and `Attempted Category`.
- **Observation 2:** Thursday contains **Infiltration - Portscan** with 71,767
  flows, which ARCHITECTURE did not list; the Thursday web attacks are tiny
  (13–73 effective flows) and Attempted-heavy.
- **Observation 3:** with the planned 25 % subsample, DoS Slowloris (3,859 →
  ≈ 965) and DoS Slowhttptest (1,740 → ≈ 435) fall below the 1,000-flow
  eligibility threshold of OD-4.
- **Interpretation:** the streaming phase has 7 eligible onsets on the full
  data, 5 at 25 %; the threshold should be defined on full-data counts, or the
  subsample raised, decided after the T3.12 benchmark.
- **Action:** canonical family list updated (`etl/cicids2017.py`, ARCHITECTURE
  §8, §16.3); OD-4 updated in the pre-registration.

## 2026-11-25 — Phase 1: the theory meets River

- **Context:** T1.1–T1.3; `theory/adwin_replay.py`, `theory/bounds.py`.
- **Observation 1:** a Python port of ADWIN using `cut_threshold` fires on
  exactly the same indices as River 0.27's Rust ADWIN (160/160 streams during
  development, 4 parameter sets).
- **Observation 2:** mean-field `n*` vs. River Monte Carlo mean (200 trials):
  within ≈ 5 % when uncensored (e.g. 0.05 → 0.25, `n_pre` = 5000: 92 vs. 97);
  first-order `ln(1/δ)/Δε²` = 155 (2.7× off for 0.05 → 0.15).
- **Observation 3:** with `C = 50`, `B = 1 %`, `λ = 10`, any burst saves at most
  500 s, against `m_a/(Bλ)` = 5,000 s for `m_a = 500`.
- **Observation 4:** log-normal delays (σ = 1) lower the expected floor from
  91,400 s to 34,757 s at `D` = 1 day.
- **Interpretation:** (2) the variance term matters at low error rates; (3) the
  E4 burst arm is near-null by design unless `C` varies; (4) judging log-normal
  runs against the constant floor would create false H3 violations.
- **Action:** changes C1–C6 in `docs/theory.md` §10 and ARCHITECTURE §4; OD-1
  opened in the pre-registration; log-normal floor in `predict()`.

## 2026-11-25 — Repository scaffold

- **Context:** ROADMAP Phase 0 (T0.1–T0.5).
- **Observation:** no experimental results yet.
- **Interpretation:** —
- **Action:** start Phase 1 (theory) and Phase 2 (data download) next.
