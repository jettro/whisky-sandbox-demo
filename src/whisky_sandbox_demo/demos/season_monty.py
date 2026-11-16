"""Scenario 2, the same agent with its tools behind Code Mode (Monty).

Same task, instructions, tools and output schema as season_tool_calls. Limits are higher than in
scenario 1 because a snippet may page through several hundred products.

    uv run python -m whisky_sandbox_demo.demos.season_monty [--runs N]
"""

from pydantic_ai_harness import CodeMode

from whisky_sandbox_demo.season.runner import main

code_mode = CodeMode(
    tools="all",
    max_tool_calls=100,
    resource_limits={"max_duration_seconds": 20, "max_memory": 256 * 1024 * 1024},
)

if __name__ == "__main__":
    main("season_monty", [code_mode], uses_code_mode=True)
