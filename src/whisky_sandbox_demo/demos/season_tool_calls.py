"""Scenario 2, ordinary tool calling: plan a club season from the full shop catalogue.

uv run python -m whisky_sandbox_demo.demos.season_tool_calls [--runs N]
"""

from whisky_sandbox_demo.season.runner import main

if __name__ == "__main__":
    main("season_tool_calls", uses_code_mode=False)
