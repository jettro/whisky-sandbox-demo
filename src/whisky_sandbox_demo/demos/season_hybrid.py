"""Scenario 2, hybrid: the agent chooses per step between direct tool calls and run_code.

Same task, tools and schema as season_tool_calls and season_monty, with the season tools offered
both directly and inside run_code (season_monty's limits), plus one neutral instruction that both
routes exist.

    uv run python -m whisky_sandbox_demo.demos.season_hybrid [--runs N]
"""

from whisky_sandbox_demo.hybrid import HYBRID_INSTRUCTIONS, code_toolset
from whisky_sandbox_demo.season.runner import main
from whisky_sandbox_demo.season.tools import SEASON_TOOLS

run_code = code_toolset(
    SEASON_TOOLS,
    max_tool_calls=100,
    resource_limits={"max_duration_seconds": 20, "max_memory": 256 * 1024 * 1024},
)

if __name__ == "__main__":
    main(
        "season_hybrid",
        toolsets=[run_code],
        uses_code_mode=True,
        extra_instructions=HYBRID_INSTRUCTIONS,
        comparable_with=["season_tool_calls", "season_monty"],
        notes=["Tools offered both directly and inside run_code; adds HYBRID_INSTRUCTIONS."],
        trace_path=True,
    )
