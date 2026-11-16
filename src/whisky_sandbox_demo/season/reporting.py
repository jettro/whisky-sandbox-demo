"""Print a season plan and save runs, including a summary over repeated runs."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from whisky_sandbox_demo.metrics import RunMetrics
from whisky_sandbox_demo.reporting import euros
from whisky_sandbox_demo.season.catalogue import load_catalogue
from whisky_sandbox_demo.season.models import SeasonPlan


def season_disclaimer() -> str:
    cat = load_catalogue()
    return (
        f"Data: Slijterij De Helm (S1) snapshot from {cat.snapshot_date}, facts parsed from shop "
        f"text; S2, S3 and all shipping terms are fictional."
    )


def print_season(plan: SeasonPlan) -> None:
    for evening in plan.evenings:
        print(f"\n{evening.theme} - {evening.supplier_id} - {euros(evening.subtotal_cents)}")
        for w in sorted(evening.whiskies, key=lambda w: w.position):
            print(
                f"  {w.position}. {w.name} ({w.product_id}, {w.abv}%) "
                f"{w.bottles} x {euros(w.unit_price_cents)}"
            )
    print()
    for o in plan.orders:
        print(
            f"  order {o.supplier_id}: {euros(o.subtotal_cents)} + shipping "
            f"{euros(o.shipping_cents)} = {euros(o.total_cents)}"
        )
    print(f"  season total: {euros(plan.season_total_cents)}")
    print(f"\n{season_disclaimer()}")


def _stats(values: list[float]) -> dict[str, float | None]:
    values = [v for v in values if v is not None]
    if not values:
        return {"median": None, "min": None, "max": None}
    return {"median": statistics.median(values), "min": min(values), "max": max(values)}


def write_summary(out_dir: Path, runs: list[dict]) -> dict:
    """runs: [{"metrics": RunMetrics | None, "valid": bool | None, "error": str | None}]"""
    metrics = [r["metrics"] for r in runs if r["metrics"] is not None]
    fields = (
        "elapsed_seconds",
        "model_requests",
        "input_tokens",
        "output_tokens",
        "peak_request_input_tokens",
        "tool_return_chars",
    )
    summary = {
        "runs": len(runs),
        "completed": len(metrics),
        "errors": [r["error"] for r in runs if r["error"]],
        "valid": sum(1 for r in runs if r["valid"]),
        "valid_rate": round(sum(1 for r in runs if r["valid"]) / len(runs), 2) if runs else None,
        **{f: _stats([getattr(m, f) for m in metrics]) for f in fields},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def print_summary(variant: str, summary: dict) -> None:
    print(f"\n=== {variant}: {summary['valid']}/{summary['runs']} valid ===")
    for key in (
        "elapsed_seconds",
        "model_requests",
        "input_tokens",
        "peak_request_input_tokens",
        "tool_return_chars",
    ):
        s = summary[key]
        print(f"  {key}: median {s['median']} (min {s['min']}, max {s['max']})")
    for error in summary["errors"]:
        print(f"  error: {error}")


def run_metrics_line(m: RunMetrics) -> str:
    return (
        f"requests={m.model_requests} in={m.input_tokens} out={m.output_tokens} "
        f"peak={m.peak_request_input_tokens} returned={m.tool_return_chars} "
        f"top={m.top_level_tool_calls} nested={m.nested_tool_calls}"
    )
