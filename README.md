<!-- README.md -->

# DriftStream-IDS

**Verification latency: why concept-drift adaptation in streaming network
intrusion detection fails when labels arrive late.**

DriftStream-IDS is the reproducible research artefact behind a 9-page research
essay. It derives, measures and demonstrates one claim: when ground-truth labels
arrive with a verification delay `D` and only for a budgeted fraction `B` of the
traffic, recovery after a drift is lower-bounded by `D + m_a / (B·λ)`, and no
detector or budget can remove the `D` term.

> **Status:** Phase 0 — setup and scoping (milestone M0). No results yet. See
> [`ROADMAP.md`](ROADMAP.md) for the live plan and status log.

## Quick start

Requirements: [uv](https://docs.astral.sh/uv/), Python 3.11, GNU make. Docker
Compose is needed only for the stream mode (Phase 5).

```bash
git clone https://github.com/franjavi-upct-es/DriftStream-IDS.git
cd DriftStream-IDS
make setup        # uv sync --all-groups + pre-commit hooks
make check        # lint + import contracts + mypy + fast tests
uv run driftstream --help
```

Commands for later phases already exist; until their ROADMAP task is done they
exit with code 3 and name the task that will implement them.

## Repository layout

| Path               | Content                                                |
| ------------------ | ------------------------------------------------------ |
| `src/driftstream/` | The single core library used by both execution modes   |
| `configs/`         | Hydra config tree; one group per component type        |
| `tests/`           | Unit, property, integration and end-to-end tests       |
| `docs/`            | ADRs, pre-registration, lab notebook, experiment cards |
| `deploy/docker/`   | Kafka-Spark testbed (Phase 5)                          |
| `essay/`           | Pandoc source of the essay (Phase 7)                   |

The full map is in [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md).

## Documentation

| Document                                             | Purpose                                                    |
| ---------------------------------------------------- | ---------------------------------------------------------- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md)                 | Design and scientific model                                |
| [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md)       | Repository map and conventions                             |
| [`ROADMAP.md`](ROADMAP.md)                           | Phases, tasks, milestones and status log                   |
| [`docs/preregistration.md`](docs/preregistration.md) | Hypotheses H1–H5 and analysis plan (frozen at `prereg-v1`) |
| [`docs/lab_notebook.md`](docs/lab_notebook.md)       | Dated findings and anomalies                               |
| [`docs/decision_log.md`](docs/decision_log.md)       | Small decisions, one line each                             |
| [`docs/adr/`](docs/adr/)                             | Architecture Decision Records ADR-001 … ADR-013            |
| [`docs/experiment_cards/`](docs/experiment_cards/)   | Experiment cards E0 … E6                                   |
| [`data/README.md`](data/README.md)                   | Data provenance and licences                               |

### Architecture Decision Records

| ADR                                                          | Decision                                                                     |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| [ADR-001](docs/adr/0001-simulator-first.md)                  | Science in a deterministic simulator; Kafka–Spark for parity and feasibility |
| [ADR-002](docs/adr/0002-one-core-library.md)                 | One core library shared by both modes                                        |
| [ADR-003](docs/adr/0003-river-and-scikit-learn.md)           | River for online learning and detectors; scikit-learn for batch              |
| [ADR-004](docs/adr/0004-corrected-cicids2017-only.md)        | Only the corrected CIC-IDS2017                                               |
| [ADR-005](docs/adr/0005-kyoto-leakage-removal.md)            | Kyoto 2006+ without detector-output columns                                  |
| [ADR-006](docs/adr/0006-token-bucket-budget.md)              | Token-bucket budget with burst support                                       |
| [ADR-007](docs/adr/0007-random-substream-for-detectors.md)   | Supervised detectors use only random-substream labels                        |
| [ADR-008](docs/adr/0008-driver-side-scoring.md)              | Driver-side scoring in `foreachBatch`                                        |
| [ADR-009](docs/adr/0009-single-partition-stateful-topics.md) | Single-partition topics for stateful services                                |
| [ADR-010](docs/adr/0010-labels-never-in-flows-topic.md)      | Labels never travel in `flows.raw`                                           |
| [ADR-011](docs/adr/0011-hydra-and-mlflow.md)                 | Hydra configs + config hashing; MLflow tracking                              |
| [ADR-012](docs/adr/0012-preregistration.md)                  | Pre-register H1–H4 before E1/E2                                              |
| [ADR-013](docs/adr/0013-pyspark-batch-etl.md)                | PySpark batch for Kyoto ETL and the sweep runner                             |

### Experiment cards

[E0](docs/experiment_cards/e0.md) · [E1](docs/experiment_cards/e1.md) ·
[E2](docs/experiment_cards/e2.md) · [E3](docs/experiment_cards/e3.md) ·
[E4](docs/experiment_cards/e4.md) · [E5](docs/experiment_cards/e5.md) ·
[E6](docs/experiment_cards/e6.md)

## Data

Raw data is never redistributed. Download scripts and checksums are provided
from Phase 2. Kyoto 2006+ is obtained from the provider's archive
(`https://www.takakura.com/Kyoto_data/new_data201704/`, 2006-11 → 2015-12); the
MVP uses 2007–2009. Cite CIC-IDS2017 (Sharafaldin et al. 2018) and its corrected
version (Engelen et al. 2021), and Kyoto 2006+ (Song et al. 2011), as their
providers request.

## Licence

Code under the MIT licence (see [`LICENSE`](LICENSE)). Datasets remain under
their providers' terms.
