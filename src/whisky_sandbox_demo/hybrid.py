"""Hybrid mode: the same domain tools offered twice, as direct tool calls and inside run_code.

The `CodeMode` capability splits tools: each one is either sandboxed or native, never both. To
let the model choose, the agent keeps its normal tools and gets an extra `CodeModeToolset` that
wraps its own copy of the same functions. The model sees five tools: the four domain tools and
`run_code`, in which the same four functions are callable under the same names.

`path_trace` records, per model response, which route the model took, so a run shows when it
switched between direct calls and code.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai_harness.code_mode import CodeModeResourceLimits, CodeModeToolset

from whisky_sandbox_demo.metrics import RUN_CODE_KIND

HYBRID_INSTRUCTIONS = """\
You can use the catalogue tools in two ways: call them directly as tools, or call the same
functions from Python inside run_code. Choose whichever fits each step; you may mix both.
"""
"""Deliberately neutral: it names both routes and does not say when to prefer either."""

OUTPUT_TOOL_PREFIX = "final_result"

# Heuristic markers that a snippet does arithmetic on money, not just fetching.
_MONEY = re.compile(r"price|cents|cost|total|budget|shipping", re.IGNORECASE)
_ARITHMETIC = re.compile(r"\bsum\(|\+=|[\w)\]]\s*[-+*]\s*[\w(]")


def code_toolset(
    tools: Sequence[Callable[..., Any]],
    *,
    max_tool_calls: int,
    resource_limits: CodeModeResourceLimits,
) -> CodeModeToolset:
    """A `run_code` tool whose sandbox can call `tools`; the agent keeps its own direct copies."""
    return CodeModeToolset(
        wrapped=FunctionToolset(list(tools)),
        max_tool_calls=max_tool_calls,
        resource_limits=resource_limits,
    )


class Step(BaseModel):
    step: int
    route: str
    """'direct', 'code', 'mixed' (both in one response), 'output' or 'text'."""
    direct_calls: list[str]
    run_code_calls: int


class PathSummary(BaseModel):
    steps: list[Step]
    routes: str
    """The routes in order, e.g. 'direct > direct > code > output'."""
    first_code_step: int | None
    direct_calls: int
    run_code_calls: int
    money_arithmetic_in_code: bool
    """Heuristic: a run_code snippet mentions prices/costs/totals and does arithmetic."""


def _route(direct: list[str], code: int, output: bool) -> str:
    if direct and code:
        return "mixed"
    if code:
        return "code"
    if direct:
        return "direct"
    return "output" if output else "text"


def path_trace(messages: list[ModelMessage], snippets: Sequence[str] = ()) -> PathSummary:
    steps: list[Step] = []
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue
        direct: list[str] = []
        code = 0
        output = False
        for part in message.parts:
            if not isinstance(part, ToolCallPart):
                continue
            if getattr(part, "tool_kind", None) == RUN_CODE_KIND or part.tool_name == "run_code":
                code += 1
            elif part.tool_name.startswith(OUTPUT_TOOL_PREFIX):
                output = True
            else:
                direct.append(part.tool_name)
        steps.append(
            Step(
                step=len(steps) + 1,
                route=_route(direct, code, output),
                direct_calls=direct,
                run_code_calls=code,
            )
        )
    first_code = next((s.step for s in steps if s.run_code_calls), None)
    return PathSummary(
        steps=steps,
        routes=" > ".join(s.route for s in steps),
        first_code_step=first_code,
        direct_calls=sum(len(s.direct_calls) for s in steps),
        run_code_calls=sum(s.run_code_calls for s in steps),
        money_arithmetic_in_code=any(
            _MONEY.search(code) and _ARITHMETIC.search(code) for code in snippets
        ),
    )


def print_path(path: PathSummary) -> None:
    print(f"\nRoute per model response: {path.routes}")
    print(
        f"  direct tool calls: {path.direct_calls}, run_code calls: {path.run_code_calls}, "
        f"first code at step: {path.first_code_step}, "
        f"money arithmetic in code (heuristic): {path.money_arithmetic_in_code}"
    )
