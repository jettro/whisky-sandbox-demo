"""What demos 1 and 2 share: one agent definition, one run, one way of measuring it."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability

from whisky_sandbox_demo import config, metrics, reporting
from whisky_sandbox_demo.models import TastingPlan
from whisky_sandbox_demo.prompts import INSTRUCTIONS, TASK
from whisky_sandbox_demo.tools import DOMAIN_TOOLS
from whisky_sandbox_demo.validation import validate_plan


def build_planning_agent(capabilities: Sequence[AbstractCapability[Any]] = ()) -> Agent:
    return Agent(
        config.get_agent_model(),
        instructions=INSTRUCTIONS,
        output_type=TastingPlan,
        tools=list(DOMAIN_TOOLS),
        capabilities=list(capabilities),
    )


async def run_planning_demo(
    variant: str,
    capabilities: Sequence[AbstractCapability[Any]] = (),
    *,
    uses_code_mode: bool,
) -> None:
    config.require_openai_key()
    tracing = config.configure_logfire()
    agent = build_planning_agent(capabilities)
    print(f"[{variant}] model={config.get_agent_model()} tracing={'logfire' if tracing else 'off'}")
    print(f"Task: {TASK}")

    start = time.perf_counter()
    result = await agent.run(TASK)
    elapsed = time.perf_counter() - start

    plan = result.output
    report = validate_plan(plan)
    messages = result.all_messages()
    snippets = metrics.run_code_snippets(messages) if uses_code_mode else None
    run_metrics = metrics.collect(
        variant=variant,
        model=config.get_agent_model(),
        result=result,
        elapsed=elapsed,
        validation_valid=report.valid,
        comparable_with=["tool_calls", "monty"],
        uses_code_mode=uses_code_mode,
    )

    if snippets:
        for i, code in enumerate(snippets, start=1):
            print(f"\n--- run_code snippet {i} (executed in Monty) ---\n{code}")
    reporting.print_plan(plan)
    reporting.print_validation(report)
    reporting.print_metrics(run_metrics)

    out_dir = config.OUTPUT_DIR / variant
    reporting.save_run(
        out_dir,
        output=plan,
        report=report,
        metrics=run_metrics,
        messages=messages,
        snippets=snippets,
    )
    print(f"\nSaved to {out_dir}/")


def main(variant: str, capabilities: Sequence[AbstractCapability[Any]] = (), **kw: Any) -> None:
    asyncio.run(run_planning_demo(variant, capabilities, **kw))
