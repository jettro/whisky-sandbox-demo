"""Measure a run from what the framework reports. Missing values stay None, never estimated."""

from __future__ import annotations

from collections import Counter
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, ToolReturnPart

RUN_CODE_KIND = "code_mode.run_code"
PACKAGES = (
    "pydantic-ai-slim",
    "pydantic-ai-harness",
    "pydantic-monty",
    "smolmachines",
    "openai",
    "logfire",
)


class RunMetrics(BaseModel):
    variant: str
    model: str
    package_versions: dict[str, str | None]
    elapsed_seconds: float
    model_requests: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    usage_tool_calls: int | None
    """Pydantic AI's own tool-call counter (`RunUsage.tool_calls`)."""
    top_level_tool_calls: dict[str, int]
    """Tool calls the model emitted directly, by name (includes `run_code` and output tools)."""
    nested_tool_calls: dict[str, int] | None
    """Calls made inside Monty `run_code` snippets, by name; None without Code Mode."""
    run_code_snippets: int | None
    validation_valid: bool | None
    comparable_with: list[str]
    notes: list[str] = []


def package_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = None
    return out


def _is_run_code_return(part: Any) -> bool:
    return isinstance(part, ToolReturnPart) and getattr(part, "tool_kind", None) == RUN_CODE_KIND


def count_calls(messages: list[ModelMessage]) -> tuple[Counter[str], Counter[str] | None, int]:
    top: Counter[str] = Counter()
    nested: Counter[str] = Counter()
    snippets = 0
    code_mode_seen = False
    for message in messages:
        for part in message.parts:
            if isinstance(message, ModelResponse) and isinstance(part, ToolCallPart):
                top[part.tool_name] += 1
            if _is_run_code_return(part):
                code_mode_seen = True
                snippets += 1
                calls = (part.metadata or {}).get("tool_calls") or {}
                for call in calls.values():
                    name = getattr(call, "tool_name", None) or (
                        call.get("tool_name") if isinstance(call, dict) else None
                    )
                    nested[name or "unknown"] += 1
    return top, (nested if code_mode_seen else None), snippets


def run_code_snippets(messages: list[ModelMessage]) -> list[str]:
    """The Python source the model sent to `run_code`, in order."""
    out: list[str] = []
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue
        for part in message.parts:
            if isinstance(part, ToolCallPart) and getattr(part, "tool_kind", None) == RUN_CODE_KIND:
                code = getattr(part, "code", None)
                if code is None:
                    args = part.args_as_dict()
                    code = args.get("code")
                if code:
                    out.append(code)
    return out


def collect(
    *,
    variant: str,
    model: str,
    result: Any,
    elapsed: float,
    validation_valid: bool | None,
    comparable_with: list[str],
    uses_code_mode: bool,
    notes: list[str] | None = None,
) -> RunMetrics:
    usage = result.usage
    messages = result.all_messages()
    top, nested, snippets = count_calls(messages)
    return RunMetrics(
        variant=variant,
        model=model,
        package_versions=package_versions(),
        elapsed_seconds=round(elapsed, 2),
        model_requests=usage.requests,
        input_tokens=usage.input_tokens if usage.input_tokens else None,
        output_tokens=usage.output_tokens if usage.output_tokens else None,
        total_tokens=usage.total_tokens if usage.total_tokens else None,
        usage_tool_calls=usage.tool_calls,
        top_level_tool_calls=dict(top),
        nested_tool_calls=dict(nested) if nested is not None else ({} if uses_code_mode else None),
        run_code_snippets=snippets if uses_code_mode else None,
        validation_valid=validation_valid,
        comparable_with=comparable_with,
        notes=notes or [],
    )
