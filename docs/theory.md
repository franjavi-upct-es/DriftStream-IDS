<!-- docs/theory.md -->

# DriftStream-IDS — Theory

> **What this document is:** the full derivations behind `ARCHITECTURE.md` §4
> (ROADMAP T1.1). Every formula states the assumptions it needs and its units.
> The code is `src/driftstream/theory/` (`bounds.py`, `adwin_replay.py`,
> `from_config.py`); each section names the function that implements it.
>
> **Status:** draft for E0. May be revised until the pre-registration is frozen
> (tag `prereg-v1`, milestone M3); afterwards only through the Deviations
> section of `docs/preregistration.md`.

---

## Contents

1. [Setting, notation and units](#1-setting-notation-and-units)
2. [Assumptions](#2-assumptions)
3. [Supervised detection delay (H1)](#3-supervised-detection-delay-h1)
4. [Unsupervised detection delay (H2)](#4-unsupervised-detection-delay-h2)
5. [Recovery time (H3)](#5-recovery-time-h3)
6. [Label-latency regret (H4)](#6-label-latency-regret-h4)
7. [Summary of predictions](#7-summary-of-predictions)
8. [Falsifiers and built-in checks](#8-falsifiers-and-built-in-checks)
9. [What the model does not cover](#9-what-the-model-does-not-cover)
10. [Changes with respect to ARCHITECTURE.md §4](#10-changes-with-respect-to-architecturemd-4)

---

## 1. Setting, notation and units

All times are **seconds of event time measured from the drift onset `t0`**: "τ =
600" means 600 s after `t0`. Rates are per second of event time; budgets and
shares are fractions in (0, 1].

| Symbol                           | Meaning                                                             | Unit                        |
| -------------------------------- | ------------------------------------------------------------------- | --------------------------- |
| `λ`                              | Flow arrival rate                                                   | flows/s                     |
| `B`                              | Labelling budget (long-run share of flows queried)                  | fraction                    |
| `ρ`                              | Share of `B` spent on random queries (ADR-007)                      | fraction                    |
| `C`                              | Token-bucket capacity (ADR-006)                                     | tokens = labels             |
| `D`                              | Mean verification delay                                             | s                           |
| `σ`                              | Log-normal shape of the delay (robustness variant)                  | —                           |
| `ε0`, `ε1`                       | Error rate of the pre-drift model before/after `t0`                 | fraction                    |
| `Δε = ε1 − ε0`                   | Error jump caused by the drift                                      | fraction                    |
| `n_pre`                          | Random-substream labels in the ADWIN window at `t0`                 | labels                      |
| `n*`                             | Post-drift random labels ADWIN needs to fire                        | labels                      |
| `m_a`                            | Post-drift labels the learner needs to re-attain oracle-level error | labels                      |
| `m_min`                          | Policy minimum before a retrain                                     | labels                      |
| `w_ref`, `w_test`, `k`, `p`, `α` | KS reference/test windows, check period, persistence, level         | scores, arrivals, checks, — |
| `d_KS`                           | Population KS distance between pre- and post-drift score CDFs       | —                           |
| `τ_det`, `τ_rec`                 | Detection delay, recovery time                                      | s after `t0`                |
| `R`                              | Label-latency regret                                                | excess errors               |

Derived rates: labels are **queried** at `Bλ` labels/s; the random substream at
`ρBλ` labels/s.

## 2. Assumptions

| ID     | Assumption                                                                                                                              | Used in    | Relaxed / tested in                                                                                               |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------- |
| **A1** | Abrupt drift: the pre-drift model's error jumps from `ε0` to `ε1` at `t0` and stays until adaptation                                    | §3, §5, §6 | Gradual drift is out of scope (§9); E3 injects abrupt drift on real features                                      |
| **A2** | Stationary arrivals at rate `λ` around the drift                                                                                        | all        | E1/E2 use the empirical `λ(t)`; predictions use the local rate                                                    |
| **A3** | Constant verification delay `D`; labels are released in query order                                                                     | §3–§5      | Log-normal variant: §5.5 gives the expected floor; the alarm-based policies keep the constant-delay approximation |
| **A4** | Supervised detectors see only random-substream labels, so their error bits are an unbiased sample with mean `ε0` / `ε1`                 | §3         | ADR-007; H5 measures the bias of uncertainty labels                                                               |
| **A5** | The token bucket starts every interval with at most `C` tokens and gains `B` tokens per flow                                            | §5.2, §5.3 | Property-tested (prefix invariant, ROADMAP T3.3)                                                                  |
| **A6** | Retraining on enough post-drift labels restores oracle-level error immediately (no ramp); `m_a` absorbs the learner's sample complexity | §5, §6     | `m_a` is measured on oracle-label runs (E0)                                                                       |

## 3. Supervised detection delay (H1)

### 3.1 The rule River actually applies

River's `drift.ADWIN` (River 0.27, Rust backend) keeps an exponential histogram
of the window `W` and, **every `clock` updates once the width exceeds
`grace_period`**, tests every bucket boundary as a split into an older part `W0`
(`n0` items) and a newer part `W1` (`n1` items). A split fires when
`|μ(W0) − μ(W1)| > ε_cut` with

```text
δ'      = ln( 2 · ln|W| / δ )
m⁻¹     = 1/(n0 − L + 1) + 1/(n1 − L + 1)          L = min_window_length
ε_cut   = sqrt( 2 · m⁻¹ · σ²_W · δ' ) + (2/3) · δ' · m⁻¹
```

where `σ²_W` is the population variance of the **whole** window. This differs
from the bound printed in Bifet & Gavaldà (2007) in three ways that matter for
prediction: the `ln ln |W|` correction inside `δ'`, the `L − 1` offset in `m⁻¹`,
and the restriction to bucket boundaries and clock ticks.

**Evidence that this is River's rule.** `tests/unit/test_adwin_replay.py` runs a
pure-Python ADWIN that uses `cut_threshold()` side by side with River's ADWIN on
streams with several changes and four parameter sets. The alarm indices are
identical (during development: 160 of 160 streams; in CI: 12 streams).

### 3.2 Mean-field replay of `n*`

Under A1 and A4 the detector's input is a Bernoulli stream with mean `ε0` for
`n_pre` items and `ε1` afterwards. The replay (`adwin_replay.n_star`) evaluates
River's rule on the **expected** statistics of that stream:

- the layout of the exponential histogram depends only on the width, so the
  candidate splits are exact;
- for a split at `c`, the expected sub-window means are the count-weighted
  mixtures of `ε0` and `ε1`;
- `σ²_W = μ_W (1 − μ_W)`, the population variance of a binary sample with mean
  `μ_W`;
- checks happen at widths that are multiples of `clock`. The phase of the clock
  relative to `t0` is unknown, so `n*` is the average over the `clock` possible
  phases. This includes the clock term `c_clock` of ARCHITECTURE.md §4.2 in `n*`
  itself.

`n*` is the number of post-drift random labels at the first check that fires. It
is censored (∞) beyond a horizon or when `ε0 = ε1`.

### 3.3 Accuracy of the replay

River Monte Carlo (`adwin_replay.simulate_detection`, 200 trials per cell,
`δ = 0.002`, `clock = 32`) against the mean-field replay and the first-order
bound `ln(1/δ)/Δε²`:

| `ε0 → ε1`   | `n_pre` | `n*` mean-field | `n*` River MC (mean) | first-order |
| ----------- | ------- | --------------- | -------------------- | ----------- |
| 0.05 → 0.15 | 500     | 628             | 817 (4 % censored)   | 621         |
| 0.05 → 0.15 | 5,000   | 228             | 237                  | 621         |
| 0.05 → 0.15 | 50,000  | 222             | 210                  | 621         |
| 0.05 → 0.25 | 500     | 122             | 128                  | 155         |
| 0.05 → 0.25 | 5,000   | 92              | 97                   | 155         |
| 0.05 → 0.25 | 50,000  | 92              | 92                   | 155         |
| 0.05 → 0.35 | 500     | 70              | 72                   | 69          |
| 0.05 → 0.35 | 5,000   | 62              | 62                   | 69          |
| 0.05 → 0.35 | 50,000  | 62              | 62                   | 69          |

Two lessons for the essay and for E0:

1. Without censoring the replay is within ≈ 5 % of River's mean; the first-order
   bound is off by up to 2.7× because it ignores the variance factor `σ²_W`
   (small error rates have small variance).
2. `n*` depends on `n_pre` when the pre-drift window is short (`m⁻¹` is then
   dominated by `n0`). In a run,
   `n_pre = ρ · B · (flows seen by the detector before t0)`, which
   `from_config.inputs_from_config` computes.

Sensitivity to `δ` (`ε0 = 0.05 → 0.25`, `n_pre = 5000`): `n* = 74.5`, `92.5`,
`110.5` for `δ = 0.02`, `0.002`, `0.0002`. `n*` is monotone in `Δε` and `δ`
(unit-tested).

### 3.4 Prediction

No post-drift label exists before `t0 + D` (A3); afterwards random labels arrive
at `ρBλ`:

```text
E[τ_det_sup] = D + n* / (ρ · B · λ)                 [s]      (A1, A3, A4)
```

Implemented by `bounds.tau_det_sup`. **H1 slopes:** `∂τ_det_sup/∂D = 1` and
`∂τ_det_sup/∂(1/(ρB)) = n*/λ`. With `ρ = 0` (pure uncertainty selection) the
supervised detector never fires.

## 4. Unsupervised detection delay (H2)

### 4.1 KS on a mixture window

The detector compares a reference window of `w_ref` scores with the latest
`w_test` scores every `k` arrivals and alarms after `p` consecutive rejections
at level `α`.

**Lemma (mixture).** If the test window holds a share `f` of post-drift scores,
its distribution is `F_f = f·F1 + (1 − f)·F0` and

```text
sup_x |F_f(x) − F0(x)| = f · sup_x |F1(x) − F0(x)| = f · d_KS
```

because `F_f − F0 = f (F1 − F0)` pointwise.

The asymptotic two-sample critical value is
`c(α) · sqrt((w_ref + w_test)/(w_ref · w_test))` with `c(α) = sqrt(−ln(α/2)/2)`
(`bounds.ks_critical_value`). Rejection in expectation therefore needs

```text
f ≥ c_KS = crit / d_KS                (∞ if crit / d_KS > 1)   [fraction]
```

(`bounds.ks_post_fraction`). Defaults (`w_ref = 5000`, `w_test = 1000`,
`α = 0.001`): `crit = 0.0675`, so `d_KS = 0.3` gives `c_KS = 0.225` and any
`d_KS < 0.0675` is undetectable.

### 4.2 Prediction

After `c_KS · w_test` post-drift arrivals, the next check comes after `k/2`
arrivals in expectation (uniform phase) and at most `k`; then `p − 1` further
checks must reject:

```text
E[τ_det_unsup]   = (c_KS · w_test + (p − 1/2) · k) / λ     [s]
τ_det_unsup,max  = (c_KS · w_test + p · k) / λ             (ARCHITECTURE §4.3)
```

(`bounds.tau_det_unsup`, `phase="expected" | "worst"`). **Neither depends on `D`
or `B`** (H2). For pure `P(y|x)` drift (SEA control) the score distribution does
not change, `d_KS = 0` and the prediction is ∞: the unsupervised detector is
_expected_ to miss it.

Caveats: the lemma is about population distributions; finite windows add noise
around `c_KS` (E0 estimates the empirical `c_KS`). The reference window is
re-captured after every promotion, so `d_KS` refers to the model in production.

## 5. Recovery time (H3)

### 5.1 Retrain-on-alarm policies: a unified formula

A retraining policy collects `m_eff = max(m_a, m_min)` labels of flows whose
event time is at least `t0 + o` and cannot retrain before the alarm. Labels of
those flows are queried from `t0 + o` and released `D` later (A3), so

```text
τ_rec = max( τ_det , o + D + T_collect(m_eff) )            [s]
```

where `T_collect(m)` is the time to query `m` labels (§5.3; `m/(Bλ)` without a
burst). The offset `o` encodes which labels the policy may use
(`bounds.LabelOrigin`):

| Origin                 | `o`         | Meaning                                   | Resulting `τ_rec`               |
| ---------------------- | ----------- | ----------------------------------------- | ------------------------------- |
| `CHANGE_POINT`         | 0           | Change-time estimate equals `t0`          | `max(τ_det, D + T_collect)`     |
| `ALARM`                | `τ_det`     | Only flows seen after the alarm           | `τ_det + D + T_collect`         |
| `AFTER_ALARM_ARRIVALS` | `τ_det − D` | Only labels that _arrive_ after the alarm | `max(τ_det, τ_det + T_collect)` |

ARCHITECTURE.md §4.4 uses `AFTER_ALARM_ARRIVALS` for ODS
(`D + n*/(ρBλ) + m_a/(Bλ)`) and `ALARM` for the burst row. Its ODU row,
`max(τ_det_unsup, D) + m_a/(Bλ)`, matches none of the three origins exactly: it
lies between `CHANGE_POINT` and `ALARM`. `predict()` uses `ALARM` for ODU (the
conservative reading that matches how the burst row was derived); the exact rule
is fixed when the KS detector's change-time estimate is implemented (T3.6) and
frozen in the pre-registration.

### 5.2 The recovery floor (H3)

**Claim.** For every policy whose adaptation needs `m` post-drift labels:

```text
τ_rec ≥ D + max(m − C, 0) / (B · λ)                         [s]   (A3, A5)
```

**Proof.** By A5, in any interval of length `t` at most `Bλt + C` labels are
queried. Post-drift flows exist only from `t0`, so by `t0 + s` at most `Bλs + C`
post-drift labels have been queried, and by A3 none of those queried after
`t0 + s − D` has been released by `t0 + s`. Having `m` released labels at
`t0 + τ` therefore needs `Bλ(τ − D) + C ≥ m`. ∎

With `C = 0` this is ARCHITECTURE's `D + m_a/(Bλ)`; with the default `C = 50`,
`B = 1 %`, `λ = 10` it is 500 s lower. Implemented by `bounds.recovery_floor`;
`tests/property/test_theory_floor.py` checks that no policy formula in
`bounds.py` beats it.

### 5.3 Budget bursts can only spend what was saved

A burst multiplies the query rate by `k` for at most `H` seconds after the
alarm, financed by saved tokens. The bucket holds at most `C` tokens, gains `Bλ`
per second and loses `kBλ` per second during the burst, so the burst stops after

```text
t_ex = C / ((k − 1) · B · λ)                                [s]
```

and `T_collect(m)` follows from collecting at `kBλ` for `min(H, t_ex)` seconds
and at `Bλ` afterwards (`bounds.collection_time`). **Consequence:** the burst
saves at most

```text
T_collect,plain − T_collect,burst ≤ C / (B · λ)             [s]
```

**independently of `k`, `H` and `D`**. With `C = 50`, `B = 1 %`, `λ = 10`
flows/s this is 500 s, against `m_a/(Bλ) = 5,000 s` for `m_a = 500`. This
supports the invariance part of H4 (the gain does not depend on `D`) and shows
that the burst arm of E4 is only informative if `C` is a factor of the design
(see the pre-registration, open decision OD-1).

### 5.4 Other policies

| Policy                       | Prediction                                                   | Notes                                                                             |
| ---------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `continuous` (ARF, no reset) | `D + m_ARF / (Bλ)`                                           | Attains the `C = 0` floor; `m_ARF` is ARF's own label need (E0)                   |
| `periodic` (period `T`)      | `D + m_a/(Bλ) + T/2` (worst: `+ T`)                          | Retrain phase independent of `t0`; assumes the window keeps the post-drift labels |
| ODS                          | §5.1 with `τ_det = τ_det_sup`, origin `AFTER_ALARM_ARRIVALS` | `D` enters twice: through detection and through collection                        |
| ODU                          | §5.1 with `τ_det = τ_det_unsup`, origin `ALARM`              |                                                                                   |
| ODU + burst                  | §5.1 with origin `ALARM`, `T_collect` from §5.3              | `D` is never removed (unit-tested)                                                |

### 5.5 Random (log-normal) delays

Under log-normal delays with mean `D` and shape `σ`, labels queried at `Bλ` from
`t0` are released independently, and the expected number released by `t0 + t` is
`Bλ · E[(t − δ)⁺]`, with the closed form

```text
E[(t − δ)⁺] = t · Φ(z) − D · Φ(z − σ),   z = (ln t − μ)/σ,   μ = ln D − σ²/2
```

The **expected floor** is the `t` at which this reaches `max(m − C, 0)`
(`bounds.recovery_floor_lognormal`, bisection). By Jensen's inequality
(`(t − δ)⁺` is convex in `δ`) it is **below** the constant-delay floor: heavy
tails also mean that many labels arrive early (the median delay is
`D · e^{−σ²/2} ≈ 0.61 D` for `σ = 1`). Example (`m = 500`, `B = 1 %`, `λ = 10`,
`σ = 1`):

| `D`     | constant floor | log-normal expected floor |
| ------- | -------------- | ------------------------- |
| 300 s   | 5,300 s        | 5,299 s                   |
| 1,800 s | 6,800 s        | 6,658 s                   |
| 7,200 s | 12,200 s       | 10,184 s                  |
| 1 day   | 91,400 s       | 34,757 s                  |

This matters for E2 (Kyoto, `D` up to 7 days): judging the log-normal variant
against the constant floor would count correct runs as violations of H3. The
pre-registration therefore uses the log-normal floor for the log-normal variant.
This is an expected-value floor, not a per-run bound.

## 6. Label-latency regret (H4)

Under A1 and A6 the deployed model makes `Δε` extra errors per flow from `t0`
until `t0 + τ_rec`:

```text
R = λ · Δε · τ_rec                                         [excess errors]
R_1000 = 1000 · R / N                                      [per 1,000 flows]
```

(`bounds.regret`, `bounds.regret_per_1000`). Substituting any row of §5,
`∂R/∂D = λΔε` (linear in `D`) and the budget enters only through the collection
term (`∝ 1/B`). The burst reduces `R` by at most `λ · Δε · C/(Bλ) = Δε · C/B`
excess errors, independent of `D`.

## 7. Summary of predictions

`bounds.predict(TheoryInputs)` returns all of them for one configuration;
`driftstream theory predict` does the same from a Hydra config plus the measured
stream quantities, and prints JSON (`null` = never happens).

| Quantity                             | Formula                      | Depends on `D`?           | Depends on `B`? |
| ------------------------------------ | ---------------------------- | ------------------------- | --------------- |
| `τ_det_sup`                          | `D + n*/(ρBλ)`               | slope 1                   | `∝ 1/(ρB)`      |
| `τ_det_unsup`                        | `(c_KS w_test + (p − ½)k)/λ` | no                        | no              |
| Floor                                | `D + (m_a − C)⁺/(Bλ)`        | slope 1                   | `∝ 1/B`         |
| `τ_rec` (any label-dependent policy) | §5                           | slope 1 (constant delays) | `∝ 1/B`         |
| Burst gain                           | `≤ C/(Bλ)`                   | no                        | `∝ 1/B`         |
| `R`                                  | `λ Δε τ_rec`                 | slope `λΔε`               | `∝ 1/B`         |

Worked example (`λ = 10`, `ε0 = 0.05`, `ε1 = 0.25`, `m_a = m_min = 500`,
`B = 1 %`, `ρ = 0.5`, `n_pre = 500`, `d_KS = 0.3`, `C = 50`, `D = 600 s`):
`τ_det_sup = 600 + 122.5/0.05 = 3,050 s`; `τ_det_unsup = 97.5 s`; floor = 5,100
s; ODU 5,698 s; ODU + burst (k = 5) 5,198 s; ODS 8,050 s.

## 8. Falsifiers and built-in checks

| Observation                                                                                   | What it would mean                                                         | Where it is checked                           |
| --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | --------------------------------------------- |
| A label-dependent policy recovers faster than the floor (§5.2, or §5.5 for log-normal delays) | Hidden label leak, or the drift is not abrupt                              | E0/E3; `test_no_label_leak.py` (T3.11)        |
| Supervised detection insensitive to `D`                                                       | Detection driven by something other than labels (bug, ARF-internal resets) | H1 regression in E0/E3                        |
| KS detects the SEA control                                                                    | Score distribution changed: leak or a model that sees `y`                  | E0 negative control                           |
| Burst gain > `C/(Bλ)`                                                                         | Budget leak in the token bucket                                            | E4; property test T3.3                        |
| `n*` from runs far from the replay at `B = 1`, `D = 0`                                        | Engine feeds ADWIN differently from the model (e.g. biased labels)         | E0, using `simulate_detection` as a reference |
| Unsupervised detection depends on `D`                                                         | Policy or reference re-capture couples KS to labels                        | H2 regression                                 |

## 9. What the model does not cover

- **Gradual drift.** A1 is violated; the model then over-predicts recovery
  (adaptation starts before `t0` would suggest). Kyoto contains gradual drift:
  E2 is evaluated through regret and H3's floor, not through detection delays.
- **Non-stationary `λ(t)`.** Replace `λ` by the mean rate over the relevant
  interval; diurnal cycles in CIC/Kyoto make this an approximation, reported as
  such.
- **Learning curves.** A6 replaces a gradual post-retrain improvement by a step;
  `m_a` is therefore defined operationally (§10.2 recovery criterion of
  ARCHITECTURE: within `κ = 5 %` of the oracle for `w_stab` samples).
- **Alert-level labelling.** SOCs label incidents, not flows; the model treats
  one label per flow, which is optimistic (ARCHITECTURE §18).
- **Log-normal delays for the alarm-based policies.** Only the floor and the
  continuous policy use §5.5; ODS/ODU/burst keep the constant-delay
  approximation and are compared descriptively in the log-normal variant.

## 10. Changes with respect to ARCHITECTURE.md §4

| #   | Change                                                                                                                      | Reason                                                                                 | Effect                                    |
| --- | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------- |
| C1  | `n*` is the clock-phase average of a mean-field replay of River's exact rule; the separate `c_clock/(ρBλ)` term is absorbed | Implementation-aligned; validated against River Monte Carlo                            | §4.2 formula simplifies to `D + n*/(ρBλ)` |
| C2  | Expected KS delay uses `(p − ½)k`; ARCHITECTURE's `p·k` is the worst case; `c_KS = crit/d_KS` derived (mixture lemma)       | Uniform check phase; closed form for `c_KS`                                            | §4.3                                      |
| C3  | Floor becomes `D + (m − C)⁺/(Bλ)`                                                                                           | The token bucket allows up to `C` saved labels; without this bursts would "violate" H3 | H3 decision rule                          |
| C4  | Unified retrain-on-alarm formula with a label origin; ODU uses origin `ALARM`                                               | ARCHITECTURE's ODU row matches no consistent origin                                    | §4.4 ODU row                              |
| C5  | Burst gain bounded by `C/(Bλ)`                                                                                              | Token-bucket financing                                                                 | E4 design (OD-1)                          |
| C6  | Expected floor for log-normal delays                                                                                        | Jensen: heavy tails release many labels early                                          | H3 rule for the log-normal variants       |
