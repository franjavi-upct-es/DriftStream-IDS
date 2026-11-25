<!-- docs/preregistration.md -->

# Pre-registration — DriftStream-IDS

| Field           | Value                                                                                |
| --------------- | ------------------------------------------------------------------------------------ |
| Status          | **DRAFT v0.2** (2026-11-25) — not frozen                                             |
| Freeze point    | Milestone M3, git tag `prereg-v1` (after E0, before E1/E2; ROADMAP T4.2)             |
| Sources         | `ARCHITECTURE.md` §2.3, §10, §11, §12; `docs/theory.md` (formulas and changes C1–C6) |
| Before freezing | Resolve the open decisions in §9; replace every _[confirm]_ tag                      |

> **Rule (ADR-012):** once tagged `prereg-v1`, §1–§8 are not edited. Any change
> is recorded in **Deviations** with a date, a reason and its expected effect on
> the conclusions. E0 may still change §2–§8 _before_ the freeze; such changes
> are logged in `docs/lab_notebook.md`.

## 1. Research question

_How much post-drift detection performance can a streaming flow-based NIDS
recover when ground-truth labels arrive with realistic delays and under a fixed
analyst labelling budget, compared with the immediate-label assumption used in
most drift-adaptation studies?_

**Thesis to be supported or refuted.** For any label-dependent adaptation,
recovery time after an abrupt drift is bounded below by `D + (m_a − C)⁺/(Bλ)`.
The `D` term cannot be reduced by better detectors, larger budgets or budget
bursts; only label-free adaptation or shorter verification pipelines reduce it.

## 2. Confirmatory hypotheses and decision rules

Confirmatory tests are **H1–H4 only**. Each has one primary decision; the listed
experiments give the evidence. Significance level 0.05 (two-sided unless
stated); 95 % confidence intervals use cluster-robust standard errors clustered
by configuration (OLS) or BCa bootstrap over seeds.

### H1 — Supervised detection delay grows with `D` (slope 1) and with `1/(ρB)`

- **Model:** `τ_det_sup ~ β0 + β_D · D + β_B · 1/(ρB)` (OLS) on detected onsets
  of the `adwin` arms.
- **Data:** E0 Gaussian stream (primary), E3 (secondary), E1 (direction only).
- **Decision (supported if all hold):**
    1. E0: the 95 % CI of `β_D` contains 1, **and** `β_B > 0` with p < 0.05;
    2. E0: median relative error of `τ_det_sup` against
       `theory.bounds.tau_det_sup` (with `n*` from the mean-field replay) ≤ 25
       %;
    3. E1: `β_D > 0` with p < 0.05 (one-sided).
- **Not supported** if (1) fails; (2) and (3) are reported either way.

### H2 — Unsupervised detection delay is invariant to `D` and `B` when `P(x)` changes

- **Model:** same OLS on detected onsets of the `ks_scores` arms.
- **Data:** E0 Gaussian (primary), E3, E1; E0 SEA as negative control.
- **Decision (supported if all hold):**
    1. E0 Gaussian: equivalence test (TOST) shows `|β_D| < 0.05` s/s and
       `|β_B| < 0.05 · w_test/λ` _[confirm margins, OD-3]_;
    2. E0 SEA control: `ks_scores` detection rate within `H_match` ≤ its
       false-alarm rate on a stationary stream + 5 percentage points (the drift
       is expected **not** to be detected).
- A failure of (2) is reported as a finding about the control, not as support or
  refutation of (1).

### H3 — Recovery of label-dependent policies respects the floor

- **Floor:** `floor = D + (m_a − C)⁺/(Bλ)` for constant delays and the
  log-normal expected floor (`theory.md` §5.5,
  `bounds.recovery_floor_lognormal`) for the log-normal variants.
- **Data:** E0, E1, E2, E3; all label-dependent arms (`continuous`, `periodic`,
  ODS, ODU, burst).
- **Decision (supported if all hold):**
    1. ≥ 95 % of runs satisfy `τ_rec ≥ floor − tol`, where
       `tol = sample_every/λ` (one metric sample). Right-censored runs (recovery
       after the horizon) count as satisfying the bound;
    2. E0: median relative error of the `τ_rec` prediction (`bounds.predict`,
       policy-specific row) ≤ 25 %.
- **Refuted** if (1) fails. Each violating run is inspected for label leaks
  before interpretation (§8 of `theory.md`).

### H4 — Regret grows linearly with `D`; a burst helps only through collection

- **Models:** (a) `R_1000 ~ β0 + β_D · D` with cell fixed effects for (dataset,
  learner, detector, selector, B); (b) burst gain `G = R_ODU − R_burst`
  regressed on `D`.
- **Data:** E0/E3 for (a, R² criterion), E1/E2 for (a, sign), E4 for (b).
- **Decision (supported if all hold):**
    1. (a) on E0/E3: R² ≥ 0.80 and `β_D > 0` (p < 0.05);
    2. (a) on E1 and E2: `β_D > 0` (p < 0.05, one-sided);
    3. (b) on E4: TOST shows the slope of `G` on `D` within ±0.05 ·
       `G(D_min)/D_max` _[confirm, OD-3]_, **and** the median observed `G` is ≤
       the bound `Δε · C/B` (`theory.md` §6) + 10 %.

### H5 — Exploratory: uncertainty selection lowers `m_a` but biases the error estimate

Reported descriptively with bootstrap CIs (E1, E4): `m_a` under `random` vs.
`hybrid`; difference between the error rate of uncertainty-selected labels and
of random labels. No confirmatory claim.

## 3. Primary metrics

Definitions follow `ARCHITECTURE.md` §10.2; the parameters here are part of the
pre-registration.

| Metric                  | Definition                                                                                                                   | Parameters                                                                                  |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Windowed macro-F1       | Over the last `w_eval` predictions, sampled every `sample_every` flows                                                       | `w_eval = 10,000`; `sample_every = 1,000`                                                   |
| Detection delay `τ_det` | First alarm in `[t0, t0 + H_match]` minus `t0`; censored if none                                                             | `H_match` = time to the next onset, capped at 24 h (CIC) / 7 d (Kyoto) / end of stream (E0) |
| Detection rate          | Share of eligible onsets detected within `H_match`                                                                           | —                                                                                           |
| False-alarm rate        | Unmatched alarms per 24 h of event time                                                                                      | —                                                                                           |
| Recovery time `τ_rec`   | First `t > t0` after which windowed macro-F1 ≥ (1 − κ) · oracle macro-F1 for `w_stab` consecutive samples; censored if never | `κ = 0.05`, `w_stab = 5`                                                                    |
| Regret `R_1000`         | `Σ (ℓ_i − ℓ_i^oracle)` paired by `flow_id` with the oracle run of the same seed, per 1,000 streamed flows                    | Oracle = `arf`, `D = 0`, `B = 1`                                                            |
| `m_a`                   | Labels needed to re-attain oracle-level error, per (dataset, learner, onset)                                                 | Estimated as in §4.3                                                                        |

## 4. Data, onsets and exclusions

### 4.1 Datasets and windows

- **CIC-IDS2017 corrected** (DistriNet; never the original CSVs, ADR-004).
  Warm-up: Monday + Tuesday; streaming: Wednesday → Friday;
  `attempted_policy = benign` (A-ATT ablation in E3); subsample fraction fixed
  after T3.12 _[confirm value]_.
- **Kyoto 2006+**, 2007-01 → 2009-12, detector-output columns, IPs and source
  port removed (ADR-005); warm-up: first 30 days; target ≈ 1.5 M sessions
  _[confirm after T2.4]_.
- **Synthetic (E0):** Gaussian mean shift (changes `P(x)` and `P(y|x)`) and SEA
  with `ConceptDriftStream` (`P(y|x)` only).

### 4.2 Onsets and eligibility

- CIC onsets: first flow of each attack family (`drift_onsets.json`, computed in
  T2.5, not assumed).
- **Per-onset analyses (H1, H2, `τ_det`) include only families with at least
  1,000 flows after subsampling** _[confirm threshold against the T2.5 counts,
  OD-4]_. Families below the threshold (expected: Heartbleed, Infiltration, Web
  SQL Injection) stay in the aggregate metrics.
- Kyoto: no known onsets; Kyoto enters H3 (through change points estimated on
  the oracle run) and H4 (regret), not H1/H2.

### 4.3 Estimating `m_a`

- `continuous` (ARF): `m_a = λ · τ_rec` of the same learner under `D = 0`,
  `B = 1` (every flow labelled immediately), per onset.
- Retrain policies (`batch`, ODS/ODU): calibration sweep of the retraining set
  size `m ∈ {100, 200, 500, 1,000, 2,000}` under `D = 0`, `B = 1`; `m_a` =
  smallest `m` whose retrain meets the recovery criterion of §3.
- `m_a` is estimated on seeds 100–104, disjoint from the analysis seeds (§5), so
  that the floor is not fitted to the runs it judges.

### 4.4 Run exclusions

A run is excluded only for a documented technical failure (crash, missing
`_DONE`, corrupted output); it is re-run with the same seed. Results are never
excluded for their values. The number of re-runs is reported.

## 5. Seeds and pairing

- Analysis seeds: 0–4 for E1–E3; 0–9 for E0, E4 and the headline contrasts
  (H1/H3 cells of E1). Calibration seeds (§4.3): 100–104.
- One integer seed per run, expanded with `numpy.random.SeedSequence` into child
  streams `subsample`, `oracle_delay`, `selector`, `learner`, `detector_perm`,
  so configurations that share a seed share the subsample, the delay draws and
  (where possible) the query decisions.
- Regret pairs each run with the oracle run of the **same seed**.

## 6. Analysis plan

1. **Unit of analysis:** (dataset, configuration, seed).
2. **Hypothesis tests:** as in §2.
3. **Multi-configuration comparisons** (E1, E2, E4): Friedman omnibus test, then
   pairwise Wilcoxon signed-rank tests with Holm correction (Demšar 2006;
   Benavoli et al. 2016); no mean-rank post-hoc tests.
4. **Uncertainty:** 95 % bootstrap CIs, 10,000 resamples over seeds (BCa when n
   ≥ 10, percentile otherwise).
5. **Effect sizes:** Cliff's δ for pairwise comparisons; regret in absolute
   units per 1,000 flows.
6. **Censoring:** `τ_det` and `τ_rec` summarised by Kaplan–Meier medians with
   the number censored; never dropped.
7. **Multiple testing:** confirmatory family = H1–H4 (one primary decision each,
   no further correction); everything else is labelled exploratory.
8. **Reporting:** every figure shows CIs; every table reports n (runs) and
   censoring counts; every number in the essay traces to
   `results/aggregated/hypotheses.json` or a run directory.

## 7. Experiments and factor levels (summary)

| Exp. | Factors                                                                                                                                 | Seeds              |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| E0   | Gaussian + SEA; `D` ∈ {0, 250, 500, 1000, 2000, 4000} s; `B` ∈ {0.5, 1, 2, 5} %; `ρ` ∈ {0.25, 0.5, 1}; `Δε` ∈ {0.1, 0.2, 0.3}; `λ = 10` | 0–9                |
| E1   | `D` ∈ {0, 5 min, 30 min, 2 h} (+ log-normal at 30 min); `B` ∈ {0.1, 1, 5} % (+ 100 % ref.); selector × detector × learner               | 0–4 (0–9 headline) |
| E2   | As E1 with `D` ∈ {0, 1 h, 1 day, 7 days} (+ log-normal at 1 day); periodic T = 7 days                                                   | 0–4                |
| E3   | CIC benign + one held-out family at prevalence `π` ∈ {1, 5, 20} %; `D × B` as E1; `adwin`, `ks_scores`; ablations A-ATT, A-FEAT         | 0–4                |
| E4   | `D` = 30 min (CIC), `B = 1 %`; policy arms; burst `k` ∈ {2, 5, 10}; ± gate; **capacity `C` per OD-1**; `D` sweep for burst              | 0–9                |

Full definitions: `ARCHITECTURE.md` §11 and `configs/experiment/`.

## 8. Sensitivity analyses (exploratory, E0 only; ROADMAP T1.5)

On the E0 Gaussian base cell (`B = 1 %`, `ρ = 0.5`, `Δε = 0.2`, `D` ∈ {0, 1000,
4000} s, seeds 0–9), varied one at a time:

| Parameter   | Levels              | Main default |
| ----------- | ------------------- | ------------ |
| ADWIN `δ`   | 0.0002, 0.002, 0.02 | 0.002        |
| KS `w_test` | 500, 1000, 2000     | 1000         |

Reported: `τ_det`, false-alarm rate and the prediction error of `n*` and `c_KS`
at each level. Configured in `configs/experiment/e0_theory.yaml` (`sensitivity`
node).

## 9. Open decisions (resolve before the freeze)

| ID       | Decision                                                                                                                                                           | Options                                                                                                                      | Proposal                                                                     |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **OD-1** | Token-bucket capacity `C` in the E4 burst arms. `theory.md` §5.3: the burst gain is at most `C/(Bλ)`, independent of `k`; with `C = 50` it is ≈ 10 % of `m_a/(Bλ)` | (a) keep `C = 50` (burst arm ≈ null by design); (b) add `C` ∈ {50, 500, 5,000} as an E4 factor; (c) size `C = (k − 1)·B·λ·H` | **(b)**: it tests the bound directly and keeps the prefix guarantee explicit |
| OD-2     | Label origin of ODU retraining                                                                                                                                     | Change-point estimate of the KS detector vs. alarm time                                                                      | Decide in T3.6; `predict()` uses `ALARM` until then                          |
| OD-3     | Equivalence margins for H2 and H4(b)                                                                                                                               | Values in §2                                                                                                                 | Check the achievable precision on E0 pilots before freezing                  |
| OD-4     | Minimum family size for per-onset analysis                                                                                                                         | 1,000 flows                                                                                                                  | Confirm against the T2.5 counts                                              |

## Deviations

_None yet. Entries are added only after the freeze._

| Date | Section | Change | Reason | Expected effect |
| ---- | ------- | ------ | ------ | --------------- |
