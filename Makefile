# Whisky sandbox demo: common tasks. Run `make` or `make help` for the list.

UV ?= uv
RUN := PYDANTIC_AI_NO_BANNER=1 $(UV) run

.DEFAULT_GOAL := help
.PHONY: help install env demo-tools demo-monty demo-monty-program demo-smol demos guest-image \
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

demo-smol: guest/wheels ## Demo 3: Monty plus a Smol microVM that builds the tasting pack
	$(RUN) python -m whisky_sandbox_demo.demos.monty_smol

demos: demo-tools demo-monty demo-smol ## Run all three demos in order

guest/wheels:
	$(MAKE) guest-image

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
