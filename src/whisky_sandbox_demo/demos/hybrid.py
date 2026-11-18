"""Experiment: the agent chooses per step between direct tool calls and run_code (Monty).

The four domain tools are offered twice: as ordinary tools (as in demo 1) and as functions inside
run_code (as in demo 2), with the same Code Mode limits as demo 2. One neutral instruction
(hybrid.HYBRID_INSTRUCTIONS) says both routes exist and does not say when to use which.

The prompt differs by that one instruction, so this is a variant next to tool_calls and monty, not
a controlled comparison. path.json records the route the model took per response.

    uv run python -m whisky_sandbox_demo.demos.hybrid
"""

from whisky_sandbox_demo.demos._runner import main
from whisky_sandbox_demo.hybrid import HYBRID_INSTRUCTIONS, code_toolset
from whisky_sandbox_demo.tools import DOMAIN_TOOLS

run_code = code_toolset(
    DOMAIN_TOOLS,
    max_tool_calls=50,
    resource_limits={"max_duration_seconds": 10, "max_memory": 128 * 1024 * 1024},
)

if __name__ == "__main__":
    main(
        "hybrid",
        toolsets=[run_code],
        uses_code_mode=True,
        extra_instructions=HYBRID_INSTRUCTIONS,
        comparable_with=["tool_calls", "monty"],
        notes=["Tools offered both directly and inside run_code; adds HYBRID_INSTRUCTIONS."],
        trace_path=True,
    )
