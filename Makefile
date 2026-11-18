# Whisky sandbox demo: common tasks. Run `make` or `make help` for the list.

UV ?= uv
RUN := PYDANTIC_AI_NO_BANNER=1 $(UV) run

.DEFAULT_GOAL := help
.PHONY: help install env demo-tools demo-monty demo-monty-program demo-hybrid demo-smol demos guest-image \
	season-snapshot season-tools season-monty season-hybrid season-hybrid-calc season-compare \
	lint format check test test-integration clean clean-output clean-guest

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Setup -----------------------------------------------------------------------------------

install: ## Install dependencies with uv
	$(UV) sync

env: ## Create .env from .env.example (does not overwrite)
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "Created .env: set OPENAI_API_KEY and DEMO_MODEL")

guest-image: ## Download guest wheels and verify them in a network-less Smol VM (once, before demo-smol)
	$(RUN) python scripts/prepare_guest_image.py

# --- Demos -----------------------------------------------------------------------------------

demo-tools: ## Demo 1: ordinary tool calling
	$(RUN) python -m whisky_sandbox_demo.demos.tool_calls

demo-monty: ## Demo 2: the same tools through Code Mode (Monty)
	$(RUN) python -m whisky_sandbox_demo.demos.monty

demo-monty-program: ## Experiment: demo 2 with an extra "write one program" instruction
	$(RUN) python -m whisky_sandbox_demo.demos.monty_program

demo-hybrid: ## Experiment: the agent chooses between direct tool calls and run_code
	$(RUN) python -m whisky_sandbox_demo.demos.hybrid

demo-smol: guest/wheels ## Demo 3: Monty plus a Smol microVM that builds the tasting pack
	$(RUN) python -m whisky_sandbox_demo.demos.monty_smol

demos: demo-tools demo-monty demo-smol ## Run all three demos in order

guest/wheels:
	$(MAKE) guest-image

# --- Scenario 2: club season over the full catalogue -------------------------------------------

RUNS ?= 1

season-snapshot: ## Re-parse (or with REFRESH=1 re-fetch) the De Helm catalogue snapshot
	$(UV) run python scripts/snapshot_de_helm.py $(if $(REFRESH),--refresh,)

season-tools: ## Scenario 2 with ordinary tool calling (RUNS=N to repeat)
	$(RUN) python -m whisky_sandbox_demo.demos.season_tool_calls --runs $(RUNS)

season-monty: ## Scenario 2 with Code Mode / Monty (RUNS=N to repeat)
	$(RUN) python -m whisky_sandbox_demo.demos.season_monty --runs $(RUNS)

season-hybrid: ## Scenario 2 where the agent chooses between tool calls and run_code (RUNS=N)
	$(RUN) python -m whisky_sandbox_demo.demos.season_hybrid --runs $(RUNS)

season-hybrid-calc: ## Scenario 2 hybrid plus the price_season calculator tool (RUNS=N)
	$(RUN) python -m whisky_sandbox_demo.demos.season_hybrid_calc --runs $(RUNS)

season-compare: season-tools season-monty ## Both scenario 2 variants, e.g. make season-compare RUNS=3

# --- Quality ---------------------------------------------------------------------------------

lint: ## Check code with Ruff (lint and formatting)
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Format and auto-fix with Ruff
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

test: ## Offline tests (no API key, network or VM)
	$(UV) run pytest

test-integration: ## Live checks: OpenAI model calls and a Smol VM (skipped if unavailable)
	$(UV) run pytest -m integration

check: lint test ## Lint and offline tests

# --- Cleanup ---------------------------------------------------------------------------------

clean-output: ## Remove demo results in output/
	rm -rf output

clean-guest: ## Remove the downloaded guest wheelhouse
	rm -rf guest

clean: clean-output ## Remove demo output and caches (keeps the guest wheelhouse)
	rm -rf .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -not -path './.venv/*' -prune -exec rm -rf {} +
