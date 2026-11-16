"""Run a season variant one or more times and summarise.

uv run python -m whisky_sandbox_demo.demos.season_tool_calls --runs 3
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import time
from collections.abc import Sequence
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.usage import UsageLimits

from whisky_sandbox_demo import config, metrics, reporting
from whisky_sandbox_demo.season import reporting as season_reporting
from whisky_sandbox_demo.season.models import SeasonPlan
from whisky_sandbox_demo.season.prompts import SEASON_INSTRUCTIONS, SEASON_TASK
from whisky_sandbox_demo.season.tools import SEASON_TOOLS
from whisky_sandbox_demo.season.validation import validate_season

RUN_TIMEOUT_SECONDS = 900
LIMITS = UsageLimits(request_limit=80)


def build_season_agent(capabilities: Sequence[AbstractCapability[Any]] = ()) -> Agent:
    return Agent(
        config.get_agent_model(),
        instructions=SEASON_INSTRUCTIONS,
        output_type=SeasonPlan,
        tools=list(SEASON_TOOLS),
        capabilities=list(capabilities),
    )


async def run_once(agent: Agent, variant: str, run_dir, uses_code_mode: bool) -> dict:
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            agent.run(SEASON_TASK, usage_limits=LIMITS), timeout=RUN_TIMEOUT_SECONDS
        )
    except Exception as error:  # a failed run is a result too: count it, keep going
        print(f"  run failed: {type(error).__name__}: {error}")
        return {"metrics": None, "valid": False, "error": f"{type(error).__name__}: {error}"}
    elapsed = time.perf_counter() - start
    report = validate_season(result.output)
    messages = result.all_messages()
    snippets = metrics.run_code_snippets(messages) if uses_code_mode else None
    run_metrics = metrics.collect(
        variant=variant,
        model=config.get_agent_model(),
        result=result,
        elapsed=elapsed,
        validation_valid=report.valid,
        comparable_with=["season_tool_calls", "season_monty"],
        uses_code_mode=uses_code_mode,
    )
    reporting.save_run(
        run_dir,
        output=result.output,
        report=report,
        metrics=run_metrics,
        messages=messages,
        snippets=snippets,
    )
    (run_dir / "DATA_NOTICE.txt").write_text(season_reporting.season_disclaimer() + "\n")
    print(
        f"  {'VALID' if report.valid else 'INVALID'} {round(elapsed, 1)}s "
        f"{season_reporting.run_metrics_line(run_metrics)}"
    )
    for check in report.failed[:8]:
        print(f"    FAIL {check.name}: {check.detail}")
    return {"metrics": run_metrics, "valid": report.valid, "error": None, "plan": result.output}


async def run_variant(
    variant: str,
    capabilities: Sequence[AbstractCapability[Any]],
    *,
    uses_code_mode: bool,
    runs: int,
) -> None:
    config.require_openai_key()
    tracing = config.configure_logfire()
    agent = build_season_agent(capabilities)
    out_dir = config.OUTPUT_DIR / variant
    if out_dir.exists():
        shutil.rmtree(out_dir)  # one variant folder = one batch of runs
    out_dir.mkdir(parents=True)
    print(
        f"[{variant}] model={config.get_agent_model()} runs={runs} "
        f"tracing={'logfire' if tracing else 'off'}"
    )
    print(f"Task: {SEASON_TASK}")

    results = []
    for i in range(1, runs + 1):
        print(f"\nrun {i}/{runs}")
        results.append(await run_once(agent, variant, out_dir / f"run_{i:02d}", uses_code_mode))

    last_plan = next((r["plan"] for r in reversed(results) if r.get("plan")), None)
    if last_plan is not None:
        print("\nLast plan:")
        season_reporting.print_season(last_plan)
    summary = season_reporting.write_summary(out_dir, results)
    season_reporting.print_summary(variant, summary)
    print(f"\nSaved to {out_dir}/")


def main(variant: str, capabilities: Sequence[AbstractCapability[Any]] = (), **kw: Any) -> None:
    parser = argparse.ArgumentParser(description=f"Run the {variant} season demo.")
    parser.add_argument("--runs", type=int, default=1, help="repeat the run N times")
    args = parser.parse_args()
    asyncio.run(run_variant(variant, capabilities, runs=args.runs, **kw))
