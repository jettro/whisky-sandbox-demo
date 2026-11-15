"""Demo 2: the same agent, with the domain tools behind Code Mode.

CodeMode folds the tools into one `run_code` tool. The model writes Python that calls them as
async functions, filters candidates and compares offers; Monty executes that Python on the
host in a sandbox without file, network or environment access. The tool implementations still
run as normal host functions.

    uv run python -m whisky_sandbox_demo.demos.monty
"""

from pydantic_ai_harness import CodeMode

from whisky_sandbox_demo.demos._runner import main

code_mode = CodeMode(
    tools="all",
    max_tool_calls=50,
    resource_limits={"max_duration_seconds": 10, "max_memory": 128 * 1024 * 1024},
)

if __name__ == "__main__":
    main("monty", [code_mode], uses_code_mode=True)
