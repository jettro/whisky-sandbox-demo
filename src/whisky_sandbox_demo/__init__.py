def main() -> None:
    print("Whisky blind-tasting planner: three ways to run the same agent.\n")
    print("  uv run python -m whisky_sandbox_demo.demos.tool_calls   # ordinary tool calls")
    print("  uv run python -m whisky_sandbox_demo.demos.monty        # Code Mode (Monty)")
    print("  uv run python scripts/prepare_guest_image.py            # once, before demo 3")
    print("  uv run python -m whisky_sandbox_demo.demos.monty_smol   # Monty + Smol microVM")
