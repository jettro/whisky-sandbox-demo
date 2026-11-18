"""Scenario 2, hybrid plus a price calculator: the fix experiment.

Identical to season_hybrid, plus one extra tool, price_season, offered directly and inside
run_code like the other tools. It computes every number of the plan (bottles, line totals,
subtotals, shipping per order, season total, budget check) from the model's selection. One extra
sentence in the instructions tells the model to copy those numbers instead of computing them.

    uv run python -m whisky_sandbox_demo.demos.season_hybrid_calc [--runs N]
"""

from whisky_sandbox_demo.hybrid import HYBRID_INSTRUCTIONS, code_toolset
from whisky_sandbox_demo.season.calculator import price_season
from whisky_sandbox_demo.season.runner import main
from whisky_sandbox_demo.season.tools import SEASON_TOOLS

CALC_TOOLS = (*SEASON_TOOLS, price_season)

CALC_INSTRUCTIONS = """\
Before you return the plan, price your final selection with price_season and copy its numbers
(bottles, line totals, subtotals, orders with shipping, season total) into the plan.
"""

run_code = code_toolset(
    CALC_TOOLS,
    max_tool_calls=100,
    resource_limits={"max_duration_seconds": 20, "max_memory": 256 * 1024 * 1024},
)

if __name__ == "__main__":
    main(
        "season_hybrid_calc",
        toolsets=[run_code],
        extra_tools=[price_season],
        uses_code_mode=True,
        extra_instructions=f"{HYBRID_INSTRUCTIONS}\n{CALC_INSTRUCTIONS}",
        comparable_with=["season_hybrid"],
        notes=["season_hybrid plus the price_season calculator tool and CALC_INSTRUCTIONS."],
        trace_path=True,
    )
