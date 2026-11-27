# Makefile
# Human-friendly entry points (PROJECT_STRUCTURE.md §8). Targets for later
# phases already exist and fail loudly until their task is implemented.

UV      ?= uv
RUN     := $(UV) run
PYTEST  := $(RUN) pytest

.DEFAULT_GOAL := help
.PHONY: help setup lint format typecheck test test-all coverage check \
	data bench e0 e1 e2 e3 e4 stream-up stream-down stream-e5 stream-e6 \
	aggregate hypotheses figures tables essay all clean-interim

help: ## List the available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

# ---------------------------------------------------------------- Phase 0
setup: ## Create the environment and install the git hooks
	$(UV) sync --all-extras
	@if [ -d .git ]; then $(RUN) pre-commit install; fi

lint: ## Ruff lint + format check + import contracts
	$(RUN) ruff check .
	$(RUN) ruff format --check .
	$(RUN) lint-imports

format: ## Apply Ruff fixes and formatting
	$(RUN) ruff check --fix .
	$(RUN) ruff format .

typecheck: ## mypy on the library
	$(RUN) mypy

test: ## Fast tests (no slow, no stream)
	$(PYTEST) -m "not slow and not stream"

test-all: ## Every test, including integration and slow
	$(PYTEST)

coverage: ## Fast tests with a coverage report
	$(PYTEST) -m "not slow and not stream" --cov --cov-report=term

check: lint typecheck test ## Everything CI runs

# ------------------------------------------------------- later phases
data: ## Download + ETL + validate both datasets (Phase 2)
	$(RUN) driftstream data download --dataset all
	$(RUN) driftstream data etl --dataset cic
	$(RUN) driftstream data etl --dataset kyoto
	$(RUN) driftstream data validate --dataset all

bench: ## Simulator throughput benchmark (T3.12)
	$(RUN) driftstream bench

e0: ## E0 theory validation
	$(RUN) driftstream run experiment=e0_theory

e1: ## E1 CIC-IDS2017 grid
	$(RUN) driftstream run experiment=e1_cic_grid

e2: ## E2 Kyoto 2006+ grid
	$(RUN) driftstream run experiment=e2_kyoto_grid

e3: ## E3 injected-drift ablation
	$(RUN) driftstream run experiment=e3_injected

e4: ## E4 policy comparison
	$(RUN) driftstream run experiment=e4_policies

stream-up: ## Start the Kafka-Spark stack
	$(RUN) driftstream stream up

stream-down: ## Stop the Kafka-Spark stack
	$(RUN) driftstream stream down

stream-e5: ## E5 streaming parity
	$(RUN) driftstream stream run --experiment e5_parity_cic
	$(RUN) driftstream stream run --experiment e5_parity_kyoto

stream-e6: ## E6 throughput and latency
	$(RUN) driftstream stream run --experiment e6_throughput

aggregate: ## Collect run outputs
	$(RUN) driftstream analyze aggregate --experiment all

hypotheses: ## Apply the pre-registered decision rules
	$(RUN) driftstream analyze hypotheses

figures: ## Regenerate the essay figures
	$(RUN) driftstream analyze figures

tables: ## Regenerate the essay tables
	$(RUN) driftstream analyze tables

essay: ## Build the essay PDF
	$(RUN) driftstream essay build --format pdf

all: data test e0 e1 e2 e3 e4 stream-e5 stream-e6 \
	aggregate hypotheses figures tables essay ## Full pipeline

clean-interim: ## Remove temporary ETL outputs
	rm -rf data/interim/*
