"""Print a plan for humans and save results for later comparison."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessagesTypeAdapter

from whisky_sandbox_demo.fixtures import load_fixtures
from whisky_sandbox_demo.metrics import RunMetrics
from whisky_sandbox_demo.models import TastingPlan
from whisky_sandbox_demo.validation import ValidationReport


def euros(cents: int) -> str:
    return f"€{cents // 100},{cents % 100:02d}"


def data_disclaimer() -> str:
    fx = load_fixtures()
    return (
        f"Data: whisky names, ABV and S1 prices/stock are a snapshot of Slijterij De Helm from "
        f"{fx.snapshot_date}; S2 and S3 are fictional suppliers; flavour scores are illustrative."
    )


def print_plan(plan: TastingPlan) -> None:
    print(f"\nSupplier: {plan.supplier_name} ({plan.supplier_id})")
    print(f"{plan.participants} people x {plan.pour_ml} ml per whisky\n")
    for w in sorted(plan.whiskies, key=lambda w: w.position):
        print(
            f"  {w.label}. {w.name} ({w.whisky_id}, {w.abv}%) - {w.bottles} x "
            f"{euros(w.unit_price_cents)} = {euros(w.line_total_cents)} "
            f"[{w.required_ml}/{w.available_ml} ml]"
        )
        print(f"     {w.tasting_role}")
    print(f"\n  Total: {euros(plan.total_cost_cents)}")
    print(f"\nWhy these: {plan.selection_rationale}")
    print(f"Why this order: {plan.ordering_rationale}")
    if plan.rejected_alternatives:
        print("Rejected:")
        for r in plan.rejected_alternatives:
            print(f"  - {r.subject_id}: {r.reason}")
    print(f"\n{data_disclaimer()}")


def print_validation(report: ValidationReport) -> None:
    print(f"\nValidation: {'VALID' if report.valid else 'INVALID'} (checked against fixtures)")
    for c in report.checks:
        if c.kind == "constraint" and not c.passed:
            print(f"  FAIL {c.name}: {c.detail}")
    passed = sum(c.passed for c in report.checks if c.kind == "constraint")
    total = sum(c.kind == "constraint" for c in report.checks)
    print(f"  constraints passed: {passed}/{total}")
    for c in report.checks:
        if c.kind == "recommendation":
            print(f"  {'ok  ' if c.passed else 'note'} {c.name}: {c.detail} (recommendation)")


def print_metrics(m: RunMetrics) -> None:
    print(f"\nMetrics ({m.variant}, {m.model})")
    print(f"  elapsed: {m.elapsed_seconds}s, model requests: {m.model_requests}")
    print(f"  tokens in/out: {m.input_tokens}/{m.output_tokens}")
    print(f"  top-level tool calls: {m.top_level_tool_calls}")
    if m.nested_tool_calls is not None:
        print(f"  nested calls inside run_code: {m.nested_tool_calls}")
        print(f"  run_code snippets: {m.run_code_snippets}")


def _dump(obj: BaseModel | dict | list) -> str:
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(indent=2)
    return json.dumps(obj, indent=2, ensure_ascii=False)


def save_run(
    out_dir: Path,
    *,
    output: BaseModel,
    report: ValidationReport,
    metrics: RunMetrics,
    messages: list,
    snippets: list[str] | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(_dump(output))
    (out_dir / "validation.json").write_text(_dump(report))
    (out_dir / "metrics.json").write_text(_dump(metrics))
    (out_dir / "messages.json").write_bytes(ModelMessagesTypeAdapter.dump_json(messages, indent=2))
    (out_dir / "DATA_NOTICE.txt").write_text(data_disclaimer() + "\n")
    if snippets:
        code_dir = out_dir / "code"
        code_dir.mkdir(exist_ok=True)
        for i, code in enumerate(snippets, start=1):
            (code_dir / f"snippet_{i:02d}.py").write_text(code)
