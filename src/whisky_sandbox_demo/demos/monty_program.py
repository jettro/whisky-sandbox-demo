"""Experiment: demo 2 plus one instruction that asks for a single program.

Same model, task, tools, data, schema and Code Mode settings as demo 2. The only change is an
extra instruction (prompts.ONE_PROGRAM_INSTRUCTIONS) asking the model to fetch, filter and
summarise in one run_code call instead of stepping through the tools like a REPL.

Because the prompt differs, this is not part of the controlled tool_calls vs monty comparison;
it shows what Code Mode can do when the model writes the whole pipeline at once.

    uv run python -m whisky_sandbox_demo.demos.monty_program
"""

from whisky_sandbox_demo.demos._runner import main
from whisky_sandbox_demo.demos.monty import code_mode
from whisky_sandbox_demo.prompts import ONE_PROGRAM_INSTRUCTIONS

if __name__ == "__main__":
    main(
        "monty_program",
        [code_mode],
        uses_code_mode=True,
        extra_instructions=ONE_PROGRAM_INSTRUCTIONS,
        comparable_with=["monty"],
        notes=[
            "Prompt variant of monty: adds ONE_PROGRAM_INSTRUCTIONS; not a controlled comparison."
        ],
    )
