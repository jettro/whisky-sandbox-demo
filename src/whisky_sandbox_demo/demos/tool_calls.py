"""Demo 1: ordinary tool calling.

The model calls the four domain tools directly. Each round of calls is a model request; the
model may batch independent calls in one response (parallel tool calls) and does all filtering,
comparing and arithmetic in its own reasoning.

    uv run python -m whisky_sandbox_demo.demos.tool_calls
"""

from whisky_sandbox_demo.demos._runner import main

if __name__ == "__main__":
    main("tool_calls", uses_code_mode=False)
