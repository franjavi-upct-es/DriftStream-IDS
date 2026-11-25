<!-- PROJECT_STRUCTURE.md -->

# DriftStream-IDS — PROJECT STRUCTURE

> **What this document is:** the map of the repository. It says where every file
> lives, what it is for, which conventions apply, and how the pieces are
> connected.
>
> **Companion documents:** `ARCHITECTURE.md` (how the system works and why),
> `ROADMAP.md` (what gets built, in which order, and when it is done).
>
> **Language policy:** everything in the repository is written in **English**:
> code, identifiers, comments, docstrings, configs, commit messages,
> documentation, figures and the essay.

---

## Table of contents

1. [Guiding principles](#1-guiding-principles)
2. [Repository tree](#2-repository-tree)
3. [Directory and file reference](#3-directory-and-file-reference)
4. [Package architecture and import rules](#4-package-architecture-and-import-rules)
5. [Configuration system (Hydra)](#5-configuration-system-hydra)
6. [Command-line interface](#6-command-line-interface)
7. [Data and results layout](#7-data-and-results-layout)
8. [Makefile targets](#8-makefile-targets)
9. [Testing layout and conventions](#9-testing-layout-and-conventions)
10. [Coding conventions](#10-coding-conventions)
11. [Notebooks convention](#11-notebooks-convention)
12. [Git, CI and release conventions](#12-git-ci-and-release-conventions)
13. [Documentation map](#13-documentation-map)
14. [Essay workspace](#14-essay-workspace)
15. [Dependencies (`pyproject.toml`)](#15-dependencies-pyprojecttoml)
16. [Ignored files](#16-ignored-files)
17. ["Where do I put X?" quick reference](#17-where-do-i-put-x-quick-reference)

---

## 1. Guiding principles

1. **One library, two modes.** All scientific logic lives in `src/driftstream/`.
   The simulator (`simulate/`) and the Kafka–Spark services (`deploy/`) only
   orchestrate it.
2. **Config-driven, never hard-coded.** Every experiment is fully defined by a
   Hydra config. A run is identified by the hash of its resolved config, plus
   its seed.
3. **Raw data is immutable.** `data/raw/` is written only by the download step.
   Everything downstream can be regenerated.
4. **Results are append-only.** A finished run directory is never modified.
   Re-running produces a new run, unless the existing one has the same config
   hash and seed, in which case it is skipped.
5. **Labels are dangerous.** Only `evaluation/` and `oracle/` may read ground
   truth. Import contracts and tests enforce this (§4.3).
6. **Everything the essay states can be traced** to a run directory, a figure
   script and a commit.
7. **Every file names itself.** The first line of every file is a comment
   holding its path relative to the repository root (`# path` or
   `<!-- path -->`). Exempt: JSON and generated lock files. Exception: Hydra
   files with a `# @package` directive carry it on line 2, because Hydra reads
   the directive only on line 1. Enforced by
   `tests/unit/test_repo_conventions.py`.

---

## 2. Repository tree

Items marked _(Phase N)_ do not exist yet; they are created by the ROADMAP task
of that phase.

```text
driftstream-ids/
├── README.md                         # Quick start, results summary, citation
├── ARCHITECTURE.md                   # System design and scientific model
├── PROJECT_STRUCTURE.md              # This file
├── ROADMAP.md                        # Phases, tasks, milestones, status log
├── LICENSE                           # MIT (code); data under provider terms
├── CITATION.cff                      # How to cite the artefact (Phase 8)
├── pyproject.toml                    # uv project, deps, ruff/mypy/pytest config
├── uv.lock                           # Locked dependency graph (committed)
├── .python-version                   # 3.11
├── Makefile                          # Entry points (see §8)
├── .pre-commit-config.yaml           # file hygiene, ruff, mypy, import contracts, no .ipynb
├── .importlinter                     # Import contracts (see §4.3)
├── .env.example                      # Ports and paths for docker compose
├── .gitignore
├── .github/
│   └── workflows/
│       ├── ci.yml                    # lint + type-check + unit/property tests
│       └── integration.yml           # nightly/manual: integration + small E0
│
├── configs/                          # Hydra configuration tree (see §5)
│   ├── config.yaml                   # Root defaults list
│   ├── dataset/
│   │   ├── cicids2017.yaml
│   │   ├── kyoto2006.yaml
│   │   ├── synth_gaussian.yaml
│   │   └── synth_sea.yaml
│   ├── features/
│   │   ├── default.yaml
│   │   └── strict.yaml
│   ├── learner/
│   │   ├── static.yaml
│   │   ├── arf.yaml
│   │   ├── batch.yaml
│   │   └── oracle.yaml
│   ├── detector/
│   │   ├── none.yaml
│   │   ├── adwin.yaml
│   │   ├── ddm.yaml
│   │   ├── ks_scores.yaml
│   │   └── mmd_features.yaml
│   ├── oracle/
│   │   ├── constant.yaml
│   │   └── lognormal.yaml
│   ├── selector/
│   │   ├── random.yaml
│   │   ├── uncertainty.yaml
│   │   └── hybrid.yaml
│   ├── policy/
│   │   ├── continuous.yaml
│   │   ├── periodic.yaml
│   │   ├── on_detect_sup.yaml
│   │   ├── on_detect_unsup.yaml
│   │   ├── budget_burst.yaml
│   │   └── gate.yaml
│   ├── evaluation/
│   │   └── default.yaml
│   ├── experiment/                   # `# @package _global_` on line 1, path on line 2
│   │   ├── e0_theory.yaml
│   │   ├── e1_cic_grid.yaml
│   │   ├── e2_kyoto_grid.yaml
│   │   ├── e3_injected.yaml
│   │   ├── e4_policies.yaml
│   │   ├── e5_parity_cic.yaml
│   │   ├── e5_parity_kyoto.yaml
│   │   └── e6_throughput.yaml
│   ├── stream/
│   │   ├── local.yaml                # broker, topics, trigger, replay speed
│   │   └── perf.yaml                 # partitions/trigger overrides for E6
│   └── hydra/
│       └── launcher/
│           └── spark.yaml            # placeholder: optional Spark sweep runner
│                                     # (local sweeps use the plugin's own `joblib`)
│
├── data/                             # NOT committed except README + checksums
│   ├── README.md                     # Data cards, provenance, licences
│   ├── CHECKSUMS.raw                 # SHA-256 of expected raw files (Phase 2)
│   ├── raw/
│   │   ├── cicids2017_corrected/     # Per-day CSVs as downloaded
│   │   └── kyoto2006/                # Daily text files YYYY/MM/YYYYMMDD.txt
│   ├── interim/                      # Temporary ETL outputs (safe to delete)
│   └── processed/
│       ├── cicids2017/
│       │   ├── flows.parquet/day=YYYY-MM-DD/part-*.parquet
│       │   ├── drift_onsets.json
│       │   ├── feature_profile.json
│       │   ├── stats.json
│       │   └── CHECKSUMS.sha256
│       ├── kyoto2006/
│       │   ├── flows.parquet/month=YYYY-MM/part-*.parquet
│       │   ├── feature_profile.json
│       │   ├── stats.json
│       │   └── CHECKSUMS.sha256
│       └── synthetic/                # Cached synthetic streams (optional)
│
├── src/
│   └── driftstream/
│       ├── __init__.py               # __version__
│       ├── py.typed
│       ├── cli.py                    # Typer app: `driftstream …` (see §6)
│       ├── logging.py                # Logger setup (rich console + JSON file) (Phase 3)
│       ├── seeds.py                  # SeedSequence spawning per component (Phase 3)
│       │
│       ├── core/
│       │   ├── types.py              # Flow, Prediction, LabelRequest, DelayedLabel, DriftAlarm
│       │   ├── interfaces.py         # Learner, QuerySelector, LabelOracle, DriftDetector, AdaptationPolicy, Evaluator
│       │   ├── actions.py            # LearnOne, Buffer, Retrain, Promote, ResetDetector, Burst
│       │   ├── registry.py           # Model registry interface + in-memory implementation
│       │   ├── guards.py             # Runtime label-access guard
│       │   └── errors.py
│       │
│       ├── data/
│       │   ├── download.py           # Fetch raw files, verify CHECKSUMS.raw
│       │   ├── schema.py             # Canonical schema, pyarrow schema, validators
│       │   ├── loaders.py            # Time-ordered Parquet iterators → Flow
│       │   ├── features.py           # Feature profiles, encoders fitted on warm-up
│       │   ├── splits.py             # Warm-up / streaming split per dataset
│       │   ├── subsample.py          # Deterministic hash-based subsampling
│       │   └── synthetic.py          # Gaussian shift stream; SEA wrapper
│       │
│       ├── etl/
│       │   ├── cicids2017.py         # pandas ETL (UTC, labels, dedup, onsets)
│       │   ├── spark_kyoto_etl.py    # PySpark ETL (leakage removal, sampling)
│       │   ├── onsets.py             # drift_onsets.json computation
│       │   ├── stats.py              # stats.json (λ per hour, class ratios)
│       │   └── validate.py           # Post-ETL assertions (monotonic time, no leaks)
│       │
│       ├── oracle/
│       │   ├── delay_models.py       # constant, lognormal, (empirical)
│       │   └── label_oracle.py       # Heap-based delayed release
│       │
│       ├── selection/
│       │   ├── budget.py             # Token bucket with burst
│       │   ├── random_selector.py
│       │   ├── uncertainty.py        # Variable-uncertainty strategy
│       │   └── hybrid.py             # ρ split random/uncertainty
│       │
│       ├── learners/
│       │   ├── base.py               # Shared helpers, versioning
│       │   ├── static.py
│       │   ├── arf.py                # River ARF wrapper
│       │   ├── batch.py              # HGB sliding-window wrapper
│       │   └── serialization.py      # snapshot/restore (cloudpickle)
│       │
│       ├── detectors/
│       │   ├── base.py
│       │   ├── adwin.py              # River ADWIN on error bits
│       │   ├── ddm.py
│       │   ├── ks_scores.py          # Two-sample KS with persistence
│       │   └── mmd_features.py       # RFF-approximated MMD (P2)
│       │
│       ├── policies/
│       │   ├── base.py               # PolicyContext
│       │   ├── continuous.py
│       │   ├── periodic.py
│       │   ├── on_detect.py          # ODS and ODU
│       │   ├── budget_burst.py
│       │   └── gate.py               # Promotion gate wrapper
│       │
│       ├── simulate/
│       │   ├── events.py             # LabelRelease, PolicyTick, FlowArrival
│       │   ├── engine.py             # Discrete-event loop (ARCHITECTURE §7)
│       │   ├── builder.py            # Config → wired components
│       │   └── runner.py             # Run one config+seed; skip if done
│       │
│       ├── evaluation/
│       │   ├── prequential.py        # Windowed / faded metrics
│       │   ├── metrics.py            # Macro-F1, TPR/FPR, FPR@TPR, per-family recall
│       │   ├── onsets.py             # Detection delay, detection rate, false alarms
│       │   ├── recovery.py           # Recovery time (with censoring)
│       │   ├── regret.py             # Paired regret vs. oracle run
│       │   └── writer.py             # Columnar run outputs + manifest
│       │
│       ├── theory/
│       │   ├── bounds.py             # τ_det, τ_rec, floor, regret predictions
│       │   ├── adwin_replay.py       # Mean-field n* from River's ADWIN rule + Monte Carlo
│       │   └── from_config.py        # Resolved config + stream quantities → TheoryInputs
│       │
│       ├── analysis/
│       │   ├── aggregate.py          # Collect runs → results/aggregated/*.parquet
│       │   ├── stats.py              # OLS, Friedman, Wilcoxon-Holm, bootstrap, KM
│       │   ├── hypotheses.py         # H1–H5 decision procedures (pre-registered)
│       │   ├── figures.py            # All essay figures (deterministic styling)
│       │   └── tables.py             # All essay tables (Markdown + LaTeX)
│       │
│       ├── tracking/
│       │   └── mlflow_utils.py       # Logging runs/models (optional in simulate)
│       │
│       └── deploy/
│           ├── schemas.py            # pydantic message models (ARCHITECTURE §13.4)
│           ├── topics.py             # Topic names and settings
│           ├── kafka_io.py           # Producer/consumer helpers, idempotency LRU
│           ├── clock.py              # sim.clock handling
│           ├── replayer.py           # Parquet → flows.raw + sim.clock
│           ├── scorer_job.py         # Spark Structured Streaming (foreachBatch)
│           ├── selector_service.py
│           ├── oracle_service.py
│           ├── updater_service.py
│           ├── drift_monitor_service.py
│           ├── policy_service.py
│           ├── metrics_sink.py       # Topics → Parquet (results/stream/…)
│           └── registry_mlflow.py    # MLflow implementation of core.registry
│
│       (Phase 0 status: every sub-package exists with its `__init__.py`;
│        the module files listed above are added by their ROADMAP tasks.)
│
├── deploy/                           # (Phase 5)
│   └── docker/
│       ├── docker-compose.yml        # Profiles: core, monitoring
│       ├── IMAGES.lock               # Pinned image digests
│       ├── Dockerfile.app            # Python services (uv-based image)
│       ├── Dockerfile.spark          # Spark + PySpark + project wheel
│       ├── kafka/
│       │   └── create-topics.sh      # Topics from ARCHITECTURE §13.3
│       ├── mlflow/
│       │   └── entrypoint.sh
│       ├── prometheus/
│       │   └── prometheus.yml        # (P2)
│       └── grafana/
│           └── dashboards/
│               └── driftstream.json  # (P2)
│
├── notebooks/                        # Percent-format .py (see §11) (Phase 2+)
│   ├── 01_eda_cicids2017.py
│   ├── 02_eda_kyoto2006.py
│   ├── 03_theory_sanity.py
│   ├── 04_results_e1_e2.py
│   └── 05_stream_parity.py
│
├── scripts/                          # (Phase 2+)
│   ├── download_data.sh              # Thin wrapper over `driftstream data download`
│   ├── run_all.sh                    # Full pipeline (ARCHITECTURE §15.5)
│   ├── benchmark_throughput.py       # Simulator flows/s (feeds the compute budget)
│   └── wordcount.py                  # Essay word count (excluding refs)
│
├── tests/
│   ├── conftest.py                   # Fixtures: repo root, config dir (more from Phase 3)
│   ├── unit/
│   │   ├── test_cli.py               # Every planned command exists (exit code 3)
│   │   ├── test_config_tree.py       # Every group option and experiment composes
│   │   ├── test_repo_conventions.py  # First-line path comment in every file
│   │   ├── test_adwin_replay.py      # ADWIN port = River alarms; n* monotone; MC check
│   │   ├── test_theory_from_config.py
│   │   ├── test_budget.py
│   │   ├── test_delay_models.py
│   │   ├── test_label_oracle.py
│   │   ├── test_selectors.py
│   │   ├── test_detectors.py
│   │   ├── test_policies.py
│   │   ├── test_metrics.py
│   │   ├── test_recovery.py
│   │   ├── test_regret.py
│   │   ├── test_theory_bounds.py
│   │   └── test_schemas.py
│   ├── property/
│   │   ├── test_theory_floor.py      # No policy formula beats the recovery floor
│   │   ├── test_budget_prefix_invariant.py
│   │   ├── test_delay_causality.py
│   │   └── test_event_ordering.py
│   ├── integration/
│   │   ├── test_engine_determinism.py
│   │   ├── test_parity_with_river_delay.py
│   │   ├── test_no_label_leak.py
│   │   ├── test_etl_cic_small.py
│   │   └── test_etl_kyoto_small.py
│   ├── e2e/
│   │   └── test_stream_smoke.py      # docker compose up → 1k flows → assertions
│   └── fixtures/
│       ├── cic_sample.csv            # A few hundred synthetic rows in CIC format
│       └── kyoto_sample.txt          # A few hundred synthetic rows in Kyoto format
│
├── results/                          # NOT committed except aggregated/figures/tables
│   ├── runs/                         # One dir per (experiment, config_hash, seed)
│   ├── stream/                       # Stream-mode sinks per run
│   ├── aggregated/                   # Parquet tables used by figures/tables
│   ├── figures/                      # PDF + PNG (committed)
│   └── tables/                       # .md + .tex (committed)
│
├── docs/
│   ├── theory.md                     # Full derivations behind ARCHITECTURE §4
│   ├── preregistration.md            # H1–H5, analysis plan (frozen at M3, tag prereg-v1)
│   ├── lab_notebook.md               # Dated log of findings and surprises
│   ├── decision_log.md               # Small decisions not worth an ADR
│   ├── data_cards/                   # (Phase 2)
│   │   ├── cicids2017.md
│   │   └── kyoto2006.md
│   ├── experiment_cards/
│   │   ├── e0.md … e6.md             # Purpose, config, status, result pointers
│   ├── adr/
│   │   ├── 0000-template.md
│   │   ├── 0001-simulator-first.md
│   │   ├── 0002-one-core-library.md
│   │   ├── 0003-river-and-scikit-learn.md
│   │   ├── 0004-corrected-cicids2017-only.md
│   │   ├── 0005-kyoto-leakage-removal.md
│   │   ├── 0006-token-bucket-budget.md
│   │   ├── 0007-random-substream-for-detectors.md
│   │   ├── 0008-driver-side-scoring.md
│   │   ├── 0009-single-partition-stateful-topics.md
│   │   ├── 0010-labels-never-in-flows-topic.md
│   │   ├── 0011-hydra-and-mlflow.md
│   │   ├── 0012-preregistration.md
│   │   └── 0013-pyspark-batch-etl.md
│   └── sources/                      # (Phase 7)
│       ├── reading_list.md           # Candidate sources with status
│       └── verification.md           # Checklist for ◐ references and legal dates
│
└── essay/                            # (Phase 7)
    ├── essay.md                      # Pandoc Markdown source (English)
    ├── refs.bib                      # BibTeX (12–15 essay sources)
    ├── template/
    │   ├── reference.docx            # A4 Word style reference (if DOCX is required)
    │   └── header.tex                # A4, margins, fonts for the PDF build
    ├── csl/
    │   └── ieee.csl                  # Citation style (switch if the course requires)
    ├── figures/                      # Copied from results/figures at build time
    └── build/                        # essay.pdf / essay.docx (ignored)
```

---

## 3. Directory and file reference

### 3.1 Root files

| File                                                      | Purpose                                                                                | Notes                                         |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------- |
| `README.md`                                               | Entry point: what, why, quick start (`make setup check`), headline result, how to cite | Updated at every milestone                    |
| `ARCHITECTURE.md` / `PROJECT_STRUCTURE.md` / `ROADMAP.md` | Project memory                                                                         | Kept in sync (`ROADMAP.md` §12 review ritual) |
| `pyproject.toml`                                          | Project metadata, dependencies, tool configs                                           | §15                                           |
| `uv.lock`                                                 | Exact dependency resolution                                                            | Always committed                              |
| `Makefile`                                                | Human-friendly entry points                                                            | §8                                            |
| `.importlinter`                                           | Import contracts                                                                       | §4.3                                          |
| `CITATION.cff`                                            | Artefact citation                                                                      | Filled in at release                          |

### 3.2 `configs/`

The Hydra config tree; every group maps to one component type. See §5.

### 3.3 `data/`

| Path                 | Written by                                | Committed?                                  |
| -------------------- | ----------------------------------------- | ------------------------------------------- |
| `data/README.md`     | Human                                     | Yes                                         |
| `data/CHECKSUMS.raw` | Human (after the first verified download) | Yes                                         |
| `data/raw/**`        | `driftstream data download`               | No                                          |
| `data/interim/**`    | ETL                                       | No                                          |
| `data/processed/**`  | ETL                                       | No (except small JSON side files, optional) |

### 3.4 `src/driftstream/` — sub-packages

| Sub-package  | Responsibility                               | May read `Flow.y`?                      | Depends on                   |
| ------------ | -------------------------------------------- | --------------------------------------- | ---------------------------- |
| `core`       | Types, interfaces, actions, registry, guards | No (defines it)                         | stdlib only                  |
| `data`       | Loading, schema, features, splits, synthetic | Passes it through only                  | `core`                       |
| `etl`        | Raw → processed                              | Yes (label mapping)                     | `core`, `data`               |
| `oracle`     | Delayed, budgeted label release              | **Yes**                                 | `core`                       |
| `selection`  | Budget + query rules                         | No                                      | `core`                       |
| `learners`   | Model wrappers                               | No (only through `DelayedLabel`)        | `core`                       |
| `detectors`  | Drift detectors                              | No (only through `DelayedLabel`)        | `core`                       |
| `policies`   | Turn signals into actions                    | No                                      | `core`                       |
| `simulate`   | Discrete-event engine                        | Routes it to `oracle`/`evaluation` only | all of the above             |
| `evaluation` | Metrics and outputs                          | **Yes**                                 | `core`                       |
| `theory`     | Analytic predictions                         | No                                      | `core`, River (ADWIN replay) |
| `analysis`   | Aggregation, statistics, figures, tables     | Reads stored outputs                    | `evaluation`, `theory`       |
| `tracking`   | MLflow helpers                               | No                                      | `core`                       |
| `deploy`     | Kafka/Spark services                         | `oracle_service` only                   | `core`, component packages   |

### 3.5 `deploy/docker/`

Container definitions and topic bootstrap for the stream mode. The images
install the **same wheel** built from `src/` (`uv build`), so the services and
the simulator always run identical library code.

### 3.6 `notebooks/`

Exploration and presentation only. A notebook must never be the only place where
a result is computed: anything that reaches the essay is reproduced by
`analysis/figures.py` or `analysis/tables.py`.

### 3.7 `tests/`

See §9.

### 3.8 `results/`

See §7.

### 3.9 `docs/`

See §13.

### 3.10 `essay/`

See §14.

---

## 4. Package architecture and import rules

### 4.1 Layering

```text
                ┌──────────── cli ────────────┐
                │                              │
          simulate                          deploy
           │   │  \                        /  │
           │   │   analysis ◄── theory    /   │
           │   │        ▲                /    │
  ┌────────┼───┼────────┼───────────────┼─────┼─────────┐
  │ oracle selection learners detectors policies evaluation │   ← components
  └──────────────────────────┬──────────────────────────────┘
                             │
                     data ── etl
                             │
                            core                                ← foundation
```

### 4.2 Rules

1. `core` imports nothing from the project.
2. Component packages import only `core` (and third-party libraries). They never
   import each other. Shared behaviour goes into `core`.
3. `simulate` and `deploy` are the **only** composition roots; they wire
   components together from configs (`simulate/builder.py` is reused by `deploy`
   services).
4. `deploy` is never imported by anything else, so the core library stays free
   of Kafka/Spark dependencies.
5. `analysis` reads stored outputs; it never runs a simulation.

### 4.3 Enforcement (`.importlinter`)

Four contracts, checked by `make lint`, pre-commit and CI:

| Contract                   | Type         | Rule                                                                                             |
| -------------------------- | ------------ | ------------------------------------------------------------------------------------------------ |
| `core-is-foundation`       | forbidden    | `driftstream.core` imports no other project package (nor `cli`)                                  |
| `components-independent`   | independence | `oracle`, `selection`, `learners`, `detectors`, `policies`, `evaluation` never import each other |
| `deploy-is-leaf`           | forbidden    | no project package except `cli` imports `driftstream.deploy`                                     |
| `analysis-never-simulates` | forbidden    | `driftstream.analysis` never imports `driftstream.simulate` (rule 5)                             |

```ini
[importlinter:contract:components-independent]
name = components do not import each other
type = independence
modules =
    driftstream.oracle
    driftstream.selection
    driftstream.learners
    driftstream.detectors
    driftstream.policies
    driftstream.evaluation
```

Label-access checks (`Flow.y`) are enforced separately by
`tests/integration/test_no_label_leak.py` (an AST scan + runtime guard), as
described in `ARCHITECTURE.md` §15.4.

---

## 5. Configuration system (Hydra)

### 5.1 Root config (`configs/config.yaml`)

```yaml
defaults:
    - dataset: cicids2017
    - features: default
    - learner: arf
    - detector: adwin
    - oracle: constant
    - selector: hybrid
    - policy: on_detect_sup
    - evaluation: default
    - stream: local
    - _self_
    # Selected with `experiment=<name>`; listed after _self_ so experiment
    # files can override root values such as `experiment` and `seed`.
    - experiment: null

seed: 0
experiment: adhoc
output_root: results/runs
skip_if_done: true
track_mlflow: false

run:
    threshold: 0.5 # decision threshold on the attack score
    tick_seconds: 60 # policy tick period, seconds of event time
    log_every: 1000 # metric sampling period (flows)
```

### 5.2 Example group files

```yaml
# configs/oracle/constant.yaml
_target_: driftstream.oracle.label_oracle.LabelOracle
delay:
    _target_: driftstream.oracle.delay_models.ConstantDelay
    mean_seconds: 1800
budget: 0.01 # B, long-run fraction of flows queried
bucket_capacity: 50 # C, token-bucket cap
```

```yaml
# configs/detector/ks_scores.yaml
_target_: driftstream.detectors.ks_scores.KSScoreDetector
kind: unsupervised
w_ref: 5000
w_test: 1000
check_every: 500
alpha: 0.001
persistence: 2
```

```yaml
# configs/dataset/cicids2017.yaml
name: cicids2017
path: data/processed/cicids2017/flows.parquet
warmup: { days: ["2017-07-03", "2017-07-04"] } # Monday + Tuesday
subsample: 0.25
attempted_policy: benign # benign | attack | drop
onsets: data/processed/cicids2017/drift_onsets.json
```

Every detector config carries `kind` (`none`, `supervised`, `unsupervised`),
which `simulate/builder.py` uses for the policy-pairing table (§5.3).

### 5.3 Experiment configs (sweeps)

```yaml
# @package _global_
# configs/experiment/e1_cic_grid.yaml
# E1: CIC-IDS2017 factorial grid (ARCHITECTURE.md §11.3).
experiment: e1_cic_grid
defaults:
    - override /dataset: cicids2017
    - override /hydra/launcher: joblib
hydra:
    mode: MULTIRUN
    sweeper:
        params:
            oracle.delay.mean_seconds: 0,300,1800,7200
            oracle.budget: 0.001,0.01,0.05
            selector: random,hybrid
            detector: none,adwin,ks_scores
            learner: arf,batch
            seed: range(0,5)
```

Run with: `uv run driftstream run experiment=e1_cic_grid`.

- `# @package _global_` **must be the first line**: Hydra stops reading header
  directives at the first non-directive line. The path comment therefore sits on
  line 2 (decision log, 2026-11-25).
- `joblib` is the `hydra-joblib-launcher` plugin's own config; there is no
  project copy, because a same-named YAML triggers Hydra's deprecated schema
  matching. Tune it with `hydra.launcher.n_jobs=<n>`.

Policy pairing (e.g. `detector=none` → `continuous`/`periodic`; `adwin` → ODS;
`ks_scores` → ODU) is resolved in `simulate/builder.py` through an explicit
mapping table, so invalid combinations are impossible.

### 5.4 Config identity

- `config_hash = sha256(canonical_yaml(resolved_config − {seed, output_root, track_mlflow, hydra.*}))[:8]`
- Run directory: `results/runs/<experiment>/<config_hash>/seed=<seed>/`
- The full resolved config is saved as `config.yaml` inside the run directory.

---

## 6. Command-line interface

`src/driftstream/cli.py` (Typer). Every command is also reachable through the
Makefile. Commands that are not implemented yet exit with **code 3** and name
the ROADMAP task that will implement them.

| Command                                                                                                                 | What it does                                                   | Task        |
| ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ----------- |
| `driftstream version`                                                                                                   | Print the package version                                      | ✅          |
| `driftstream data download [--dataset cic\|kyoto\|all]`                                                                 | Download raw data, verify `CHECKSUMS.raw`                      | T2.1 / T2.3 |
| `driftstream data etl --dataset cic`                                                                                    | pandas ETL for CIC-IDS2017 corrected                           | T2.2        |
| `driftstream data etl --dataset kyoto [--spark-master local[*]]`                                                        | PySpark ETL for Kyoto 2006+                                    | T2.4        |
| `driftstream data validate --dataset …`                                                                                 | Post-ETL assertions; writes `stats.json`                       | T2.5        |
| `driftstream theory predict --rate … --eps0 … --eps1 … --m-a … --n-pre-flows … [--ks-distance …] [--out …] [overrides]` | Print (and save) the analytic predictions for a config as JSON | ✅          |
| `driftstream run [overrides]`                                                                                           | Run one config (or a sweep, via `experiment=…`)                | T3.8        |
| `driftstream bench`                                                                                                     | Measure simulator throughput (flows/s)                         | T3.12       |
| `driftstream analyze aggregate --experiment e1_cic_grid`                                                                | Runs → `results/aggregated/`                                   | T6.1        |
| `driftstream analyze hypotheses`                                                                                        | Apply pre-registered H1–H5 decision rules                      | T6.2        |
| `driftstream analyze figures` / `tables`                                                                                | Regenerate all essay figures/tables                            | T6.3 / T6.4 |
| `driftstream stream up\|down\|status`                                                                                   | Docker compose lifecycle                                       | T5.1        |
| `driftstream stream run --experiment e5_parity_cic`                                                                     | Replay through Kafka–Spark; sink to `results/stream/`          | T5.8        |
| `driftstream stream compare --run …`                                                                                    | Parity metrics: stream vs. simulator                           | T5.6        |
| `driftstream essay build [--format pdf\|docx]`                                                                          | Pandoc build                                                   | T7.8        |
| `driftstream essay wordcount`                                                                                           | Word count excluding references                                | T7.4        |

---

## 7. Data and results layout

### 7.1 Processed data

Described in `ARCHITECTURE.md` §8.2. Parquet files use zstd compression and row
groups of about 128k rows, sorted by `event_time` within and across partitions.

### 7.2 Simulation run directory

```text
results/runs/e1_cic_grid/3f2a9c1d/seed=3/
├── config.yaml            # Fully resolved Hydra config
├── manifest.json          # Provenance (ARCHITECTURE §15.3)
├── summary.json           # Scalars: regret, τ_det per onset, τ_rec, labels, wall time
├── metrics.parquet        # Windowed series (t, n, macro_f1, tpr, fpr, …)
├── events.parquet         # Alarms, promotions, bursts, retrains, gate decisions
├── predictions.parquet    # (optional, --save-predictions) flow_id, score, pred, version
├── theory.json            # Analytic predictions for this config
├── run.log                # JSON-lines log
└── _DONE                  # Written last; its presence means the run completed
```

- The skip logic checks for `_DONE`. Partial directories without `_DONE` are
  deleted and re-run.
- `predictions.parquet` is required for oracle runs (regret pairing) and for E5
  parity. It is optional elsewhere, to save disk space.

### 7.3 Stream run directory

```text
results/stream/e5_parity_cic/<config_hash>/seed=0/trigger=1s/
├── config.yaml
├── manifest.json          # + image digests, partitions, trigger, replay speed
├── flows_scored.parquet
├── labels_delayed.parquet
├── drift_events.parquet
├── model_updates.parquet
├── perf.parquet           # Latency/throughput samples (E6)
├── parity.json            # Output of `driftstream stream compare`
├── state/                 # Service state snapshots
└── _DONE
```

### 7.4 Aggregated outputs

| File                                             | Content                                               | Produced by          |
| ------------------------------------------------ | ----------------------------------------------------- | -------------------- |
| `results/aggregated/e1_summary.parquet`          | One row per run (factors + scalars)                   | `analyze aggregate`  |
| `results/aggregated/e1_series.parquet`           | Windowed series, downsampled                          | `analyze aggregate`  |
| `results/aggregated/hypotheses.json`             | H1–H5 decisions with statistics                       | `analyze hypotheses` |
| `results/figures/fig1_theory_vs_empirical.pdf`   | Essay Figure 1                                        | `analyze figures`    |
| `results/figures/fig2_regret_heatmap_DxB.pdf`    | Essay Figure 2                                        | `analyze figures`    |
| `results/figures/fig3_recovery_timeline_cic.pdf` | Per-onset recovery (optional in the essay)            | `analyze figures`    |
| `results/figures/fig4_policy_comparison.pdf`     | E4                                                    | `analyze figures`    |
| `results/figures/fig5_stream_parity.pdf`         | E5                                                    | `analyze figures`    |
| `results/tables/tab1_sota_comparison.md`         | 6-study table (hand-curated input in `docs/sources/`) | `analyze tables`     |
| `results/tables/tab2_dxb_regret.md/.tex`         | Essay Table 2                                         | `analyze tables`     |
| `results/tables/tab3_stream_perf.md`             | E6                                                    | `analyze tables`     |

---

## 8. Makefile targets

`make help` lists every target with its description.

| Target                                     | Command (summary)                                       | Expected duration*              |
| ------------------------------------------ | ------------------------------------------------------- | ------------------------------- |
| `make setup`                               | `uv sync --all-groups && pre-commit install`            | minutes                         |
| `make lint`                                | `ruff check . && ruff format --check . && lint-imports` | seconds                         |
| `make format`                              | `ruff check --fix . && ruff format .`                   | seconds                         |
| `make typecheck`                           | `mypy` (packages configured in `pyproject.toml`)        | < 1 min                         |
| `make test`                                | `pytest -m "not slow and not stream"`                   | < 2 min                         |
| `make coverage`                            | Fast tests with a coverage report                       | < 2 min                         |
| `make check`                               | `lint` + `typecheck` + `test` (what CI runs)            | < 3 min                         |
| `make test-all`                            | `pytest` (includes integration + slow)                  | ~10 min                         |
| `make data`                                | download + ETL + validate for both datasets             | 30–90 min (Kyoto ETL dominates) |
| `make bench`                               | Simulator throughput benchmark                          | minutes                         |
| `make e0` … `make e4`                      | `driftstream run experiment=eN_*`                       | see ARCHITECTURE §11.8          |
| `make stream-up` / `stream-down`           | docker compose profile `core`                           | ~1 min                          |
| `make stream-e5` / `stream-e6`             | Run the parity/throughput experiments                   | 30–120 min                      |
| `make aggregate hypotheses figures tables` | Analysis pipeline                                       | minutes                         |
| `make essay`                               | Build PDF (and DOCX if configured)                      | seconds                         |
| `make all`                                 | Everything, in order                                    | ~1–2 days compute               |
| `make clean-interim`                       | Remove `data/interim/`                                  | —                               |

\*Durations are refined in ROADMAP Phase 3 after the benchmark.

---

## 9. Testing layout and conventions

### 9.1 Markers (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
markers = [
  "unit: fast, isolated",
  "property: hypothesis-based invariants",
  "integration: multiple components, small data",
  "slow: > 30 s",
  "stream: requires docker compose stack",
]
testpaths = ["tests"]
```

Every test module sets its marker with `pytestmark = pytest.mark.<marker>`. Test
directories have no `__init__.py`, so test file names must be unique across the
whole `tests/` tree.

### 9.2 What every component must have

| Component    | Minimum tests                                                                                                                            |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Repository   | First-line path comment in every file; CLI lists every planned command; every config option and experiment composes                      |
| Token bucket | Prefix invariant (property); burst financing never exceeds the long-run budget                                                           |
| Delay models | Mean matches `D` (statistical tolerance); non-negative; seeded reproducibility                                                           |
| Label oracle | No release before `release_time`; FIFO among equal times; memory bounded                                                                 |
| Selectors    | Spending rate converges to `B`; `ρ` split respected; reason tags correct                                                                 |
| Detectors    | Detect a synthetic abrupt change; no alarm on a stationary stream at the configured α (false-alarm rate within tolerance)                |
| Policies     | Pure function behaviour: given a context, they return the expected actions                                                               |
| Metrics      | Hand-computed examples; censoring handled                                                                                                |
| Regret       | Pairing by `flow_id`; zero when compared with itself                                                                                     |
| Theory       | ADWIN port fires on the same indices as River; `n*` monotone in Δε and δ; mean-field ≈ Monte Carlo; no policy beats the floor (property) |
| Engine       | Determinism; River parity at `B = 1`; no label leak                                                                                      |
| ETL          | Fixture files → expected schema; leakage columns absent; monotonic time                                                                  |
| Stream       | Smoke test: 1k flows end-to-end; all topics non-empty; labels released after delay                                                       |

### 9.3 Coverage target

≥ 85 % line coverage on `core`, `oracle`, `selection`, `evaluation` and `theory`
(where correctness is critical); ≥ 70 % overall.

---

## 10. Coding conventions

| Topic              | Convention                                                                                          |
| ------------------ | --------------------------------------------------------------------------------------------------- |
| Python             | 3.11; full type hints; `from __future__ import annotations`                                         |
| File header        | First line: a comment with the path relative to the repository root (§1, principle 7)               |
| Formatting/linting | **Ruff, line length 80** (formatter + linter)                                                       |
| Type checking      | mypy (`strict = true` for `core`, `oracle`, `selection`, `evaluation`, `theory`)                    |
| Docstrings         | Google style; every public function documents its units (seconds, flows, fraction)                  |
| Units              | Time in **seconds of event time** (float); budgets as **fractions** (0.01, not 1); rates in flows/s |
| Naming             | `snake_case` modules/functions; `PascalCase` classes; config keys mirror constructor arguments      |
| Randomness         | Never call `np.random.*` globally; always receive a `numpy.random.Generator` from `seeds.py`        |
| Logging            | `logging` with `rich` console + JSON-lines file per run; no `print` in library code                 |
| Errors             | Custom exceptions in `core/errors.py`; fail fast on schema violations                               |
| Data classes       | `@dataclass(frozen=True, slots=True)` for messages/events                                           |
| Performance        | Avoid pandas in the per-flow hot loop; use dicts and pre-allocated Arrow builders                   |
| Comments           | Explain _why_, not _what_; cite the paper/section where an equation comes from                      |

Ruff configuration (excerpt):

```toml
[tool.ruff]
line-length = 80
target-version = "py311"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "N", "D", "PL", "RUF", "NPY"]
ignore = ["D105", "D107", "PLR0913"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D", "PLR2004"]
"notebooks/**" = ["D", "E402"]
"scripts/**" = ["D"]

[tool.ruff.format]
quote-style = "double"
```

---

## 11. Notebooks convention

- Notebooks are written as **percent-format Python files** (`# %%` cells) in
  `notebooks/`, paired with `.ipynb` through jupytext when an interactive view
  is needed. Only the `.py` files are committed (a pre-commit hook rejects
  `.ipynb`).
- Every notebook starts with its path comment, then a header cell stating its
  purpose, its inputs (paths, run IDs) and its outputs.
- Notebooks import from `driftstream`. They never define logic that the essay
  depends on: such logic goes into `analysis/`.

Example header:

```python
# notebooks/03_theory_sanity.py
# %% [markdown]
# # 03 — Theory sanity check
# **Purpose:** compare `theory.bounds` predictions with E0 runs.
# **Inputs:** results/aggregated/e0_summary.parquet
# **Outputs:** none (exploratory; final figure is fig1 in analysis/figures.py)

# %%
from driftstream.analysis import aggregate
```

---

## 12. Git, CI and release conventions

### 12.1 Branches

| Branch                | Use                                      |
| --------------------- | ---------------------------------------- |
| `main`                | Always green; tagged at milestones       |
| `feat/<area>-<short>` | Feature work (`feat/oracle-lognormal`)   |
| `exp/<experiment>`    | Experiment config tuning (`exp/e1-grid`) |
| `essay/<section>`     | Essay drafting (`essay/sota`)            |
| `fix/<short>`         | Bug fixes                                |

### 12.2 Commits

Conventional Commits, in English: `feat(oracle): add lognormal delay model`,
`fix(engine): release labels before arrivals at equal timestamps`,
`exp(e1): freeze grid levels`, `docs(roadmap): update status log`.

### 12.3 CI (`.github/workflows/ci.yml`)

1. `uv sync --frozen --all-groups`
2. `ruff check` + `ruff format --check` + `lint-imports`
3. `mypy`
4. `pytest -m "unit or property"` with coverage (XML uploaded as an artefact)
5. Integration workflow (`integration.yml`, manual/nightly):
   `pytest -m integration` + E0 on a reduced grid (regression guard on the
   theory-vs-empirical error). Exit code 5 (no tests collected) is accepted
   until Phase 2.

### 12.4 Tags and releases

| Tag                          | Meaning                                       |
| ---------------------------- | --------------------------------------------- |
| `m0-setup` … `m7-submission` | Milestones (ROADMAP §4)                       |
| `prereg-v1`                  | Frozen pre-registration (before E1/E2)        |
| `v1.0.0`                     | Submitted version: code + figures + essay PDF |

Release assets: `essay.pdf`, `results/figures/*`, `results/tables/*`,
`results/aggregated/*.parquet`. Optionally archive on Zenodo for a DOI
(portfolio value).

---

## 13. Documentation map

| Document                       | Purpose                                                      | Update cadence                                                            |
| ------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------------------- |
| `ARCHITECTURE.md`              | Design + scientific model                                    | When a design decision changes (with an ADR)                              |
| `PROJECT_STRUCTURE.md`         | Repository map                                               | When files/directories are added                                          |
| `ROADMAP.md`                   | Plan + status log                                            | At the end of every work session                                          |
| `docs/theory.md`               | Step-by-step derivations, assumptions A1–A4, falsifiers      | Phase 1; revised only before `prereg-v1`                                  |
| `docs/preregistration.md`      | Hypotheses + analysis plan                                   | Frozen at `prereg-v1` (M3); deviations appended in a "Deviations" section |
| `docs/lab_notebook.md`         | Dated findings, anomalies, ideas                             | Every session with results                                                |
| `docs/decision_log.md`         | Minor decisions (one line each)                              | As they happen                                                            |
| `docs/adr/*.md`                | Significant decisions                                        | Per decision                                                              |
| `docs/data_cards/*.md`         | Dataset provenance, quirks, licences, ETL choices            | After ETL                                                                 |
| `docs/experiment_cards/eN.md`  | Purpose, exact config, status, results pointer, caveats      | Per experiment                                                            |
| `docs/sources/reading_list.md` | Candidate sources, notes, relevance                          | Phase 7                                                                   |
| `docs/sources/verification.md` | ◐ references and legal dates checked against primary sources | Before submission                                                         |

Experiment card template:

```markdown
<!-- docs/experiment_cards/e1.md -->

# E1 — CIC-IDS2017 grid

- **Status:** planned | running | done | superseded
- **Config:** configs/experiment/e1_cic_grid.yaml @ <git sha>
- **Hypotheses:** H1–H5
- **Runs:** 720 (+ references) | completed: N | failed: N
- **Outputs:** results/aggregated/e1_summary.parquet, fig2, tab2
- **ROADMAP task:** T4.3
- **Key result (1–2 lines):**
- **Caveats/deviations:**
```

---

## 14. Essay workspace

| Item         | Convention                                                                                                                       |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Source       | `essay/essay.md` (Pandoc Markdown, English, British or American spelling: pick one and keep it consistent)                       |
| Length       | ≈ 2,500 words excluding references; checked with `driftstream essay wordcount`                                                   |
| Format       | A4; body 11–12 pt; title + 100-word abstract on page 1, Introduction right below                                                 |
| Citations    | `refs.bib` + CSL (IEEE by default; switch if the course specifies another style)                                                 |
| Figures      | Max 2 figures + 2 tables (Table 1 SotA, Table 2 D×B); generated by `analysis/`                                                   |
| Build        | `pandoc essay.md --citeproc -o build/essay.pdf` (or `.docx` with `reference.docx`)                                               |
| Traceability | Every number in the text carries an HTML comment with its source run, e.g. `<!-- src: results/aggregated/hypotheses.json#H3 -->` |

Section files are optional. If the draft grows unwieldy, split into
`essay/sections/0N_*.md` and concatenate in the build.

---

## 15. Dependencies (`pyproject.toml`)

```toml
[project]
name = "driftstream-ids"
version = "0.1.0"
description = "Verification latency and labelling budgets in streaming NIDS"
requires-python = ">=3.11,<3.13"
dependencies = [
  "numpy", "pandas", "pyarrow", "scipy", "scikit-learn", "river",
  "hydra-core", "hydra-joblib-launcher", "omegaconf", "pydantic>=2",
  "typer", "rich", "cloudpickle", "joblib", "statsmodels", "lifelines",
  "matplotlib",
]

[project.optional-dependencies]
spark = ["pyspark"]                 # Kyoto ETL + scorer + sweep runner
stream = ["confluent-kafka", "mlflow"]
tracking = ["mlflow"]

[project.scripts]
driftstream = "driftstream.cli:app"

[dependency-groups]
dev = [
  "ruff", "mypy", "pytest", "pytest-cov", "hypothesis", "import-linter",
  "jupytext", "pre-commit", "ipykernel", "pandas-stubs", "types-PyYAML",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/driftstream"]
```

Exact versions are pinned by `uv.lock` (176 packages at Phase 0; resolved with
Python 3.11, River 0.27, NumPy 2.4, pandas 2.3). The PySpark version must match
the Spark image and the `spark-sql-kafka-0-10` package. This is recorded in
`deploy/docker/IMAGES.lock` (ADR-008 / ADR-013).

mypy uses `packages = ["driftstream"]`, `strict = true` for the critical
packages, and `ignore_missing_imports` for untyped third-party libraries (River,
scikit-learn, SciPy, PySpark, …). `warn_unused_configs` stays off until those
overrides are exercised.

Common `uv` commands:

| Task                            | Command                                          |
| ------------------------------- | ------------------------------------------------ |
| Create env + install everything | `uv sync --all-extras --all-groups`              |
| Add a dependency                | `uv add river` / `uv add --group dev hypothesis` |
| Run anything in the env         | `uv run driftstream …`, `uv run pytest`          |
| Build the wheel for the images  | `uv build`                                       |

---

## 16. Ignored files

`.gitignore` essentials:

```gitignore
# environments and tool caches
.venv/
__pycache__/
*.pyc
.mypy_cache/  .ruff_cache/  .pytest_cache/  .hypothesis/
.coverage  coverage.xml  htmlcov/  dist/  build/

# data and outputs
data/raw/
data/interim/
data/processed/**/*.parquet
results/runs/
results/stream/
mlruns/
spark-checkpoints/
outputs/        # Hydra single-run output dirs
multirun/       # Hydra sweep output dirs

# notebooks
*.ipynb
.ipynb_checkpoints/

# essay build
essay/build/

# local env
.env
```

Committed on purpose: `data/README.md`, `data/CHECKSUMS.raw`,
`results/figures/`, `results/tables/`, `results/aggregated/*.json`.

---

## 17. "Where do I put X?" quick reference

| I want to…                       | Put it in…                                                                                                                |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Add a new drift detector         | `src/driftstream/detectors/<name>.py` + `configs/detector/<name>.yaml` (with `kind`) + `tests/unit/test_detectors.py`     |
| Add a new delay distribution     | `oracle/delay_models.py` + `configs/oracle/<name>.yaml`                                                                   |
| Add a new experiment             | `configs/experiment/eN_<name>.yaml` (`# @package _global_` on line 1) + `docs/experiment_cards/eN.md` + a Makefile target |
| Change a hypothesis              | **Not allowed after `prereg-v1`**; add a "Deviations" entry in `docs/preregistration.md`                                  |
| Record a surprising result       | `docs/lab_notebook.md` (dated)                                                                                            |
| Make a design change             | ADR in `docs/adr/` + update `ARCHITECTURE.md`                                                                             |
| Record a small decision          | `docs/decision_log.md` (one line)                                                                                         |
| Produce a new essay figure       | `analysis/figures.py` (function `figN_*`), output in `results/figures/`                                                   |
| Add a message type to the stream | `deploy/schemas.py` + `deploy/topics.py` + `kafka/create-topics.sh` + ARCHITECTURE §13                                    |
| Store an exploratory analysis    | `notebooks/NN_<topic>.py`                                                                                                 |
| Track a new source for the essay | `docs/sources/reading_list.md`, then `essay/refs.bib`                                                                     |
| Add a CLI command                | `src/driftstream/cli.py` (exit code 3 until implemented) + `tests/unit/test_cli.py` + §6                                  |
