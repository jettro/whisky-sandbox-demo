"""Demo 3: Monty for coordination, a Smol microVM for files and full Python programs.

Where things run:
- Host: the agent loop and the four domain tools (plain Python functions, as in demos 1-2).
- Monty (on the host, sandboxed): the `run_code` snippets the model writes to call the domain
  tools, filter candidates and compare offers. Only the domain tools are folded into Code Mode.
- Smol VM: the Shell and FileSystem tools act on `ctx.workspace`, which is this VM. The model
  writes a report script there and runs it with the guest's Python, matplotlib and reportlab.

The VM has no network, nothing mounted from the host and no host environment variables.
It is deleted in `finally`, on success and on failure.

    uv run python scripts/prepare_guest_image.py   # once
    uv run python -m whisky_sandbox_demo.demos.monty_smol
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import csv
import io
import json
import re
import time
import zlib
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai_harness import CodeMode
from pydantic_ai_harness.filesystem import FileSystem
from pydantic_ai_harness.shell import Shell
from pydantic_ai_harness.smol_sandbox import SmolSandbox, SmolSandboxBackend

from whisky_sandbox_demo import config, guest, metrics, reporting
from whisky_sandbox_demo.models import TastingPackResult, TastingPlan
from whisky_sandbox_demo.prompts import INSTRUCTIONS, PACK_INSTRUCTIONS, PACK_TASK, TASK
from whisky_sandbox_demo.tools import DOMAIN_TOOL_NAMES, DOMAIN_TOOLS
from whisky_sandbox_demo.validation import validate_plan

VARIANT = "monty_smol"
RUN_TIMEOUT_SECONDS = 600
EXPECTED_FILES = {
    "cards_pdf": "pack/cards.pdf",
    "answer_sheet_pdf": "pack/answer_sheet.pdf",
    "shopping_list_csv": "pack/shopping_list.csv",
    "flavour_chart_png": "pack/flavour_chart.png",
}


def build_agent() -> Agent:
    return Agent(
        config.get_agent_model(),
        instructions=INSTRUCTIONS + "\n" + PACK_INSTRUCTIONS,
        output_type=TastingPackResult,
        tools=list(DOMAIN_TOOLS),
        capabilities=[
            # Domain tools only: the file and shell tools stay ordinary tool calls.
            CodeMode(
                tools=DOMAIN_TOOL_NAMES,
                max_tool_calls=50,
                resource_limits={"max_duration_seconds": 10, "max_memory": 128 * 1024 * 1024},
            ),
            # Supplies the workspace; the backend passed to run() below takes precedence.
            SmolSandbox(image=guest.GUEST_IMAGE, allow_internet_access=False),
            Shell(
                tools=["run_command"],
                allowed_commands=["python", "python3", "ls"],
                default_timeout=120,
                max_output_chars=20_000,
            ),
            FileSystem(),
        ],
    )


# --- Checking the exported files on the host --------------------------------------------------


def _decode_stream(raw: bytes) -> bytes | None:
    """Undo the filters ReportLab uses by default: ASCII85 and/or Flate."""
    candidates = [raw]
    stripped = raw.strip()
    if stripped.endswith(b"~>"):
        body = stripped.removeprefix(b"<~").removesuffix(b"~>")
        with contextlib.suppress(ValueError):
            candidates.insert(0, base64.a85decode(body, ignorechars=b" \t\r\n"))
    for data in candidates:
        try:
            return zlib.decompress(data)
        except zlib.error:
            continue
    return None


def _pdf_strings(data: bytes) -> str:
    """The text a PDF draws: the (...) operands in its decoded content streams.

    A rough extractor, enough to check labels and names in a ReportLab PDF. Text in raw form
    (metadata, uncompressed streams) is included too, so a leak cannot hide there.
    """
    streams = [data]
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.DOTALL):
        decoded = _decode_stream(match.group(1))
        if decoded is not None:
            streams.append(decoded)
    strings = []
    for stream in streams:
        strings += re.findall(rb"\(((?:[^()\\]|\\.)*)\)", stream)
    return "\n".join(s.decode("latin-1").replace("\\(", "(").replace("\\)", ")") for s in strings)


def verify_artifacts(out_dir: Path, plan: TastingPlan) -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}
    names = [w.name for w in plan.whiskies]

    def read(kind: str) -> bytes | None:
        path = out_dir / EXPECTED_FILES[kind]
        return path.read_bytes() if path.exists() else None

    cards = read("cards_pdf")
    if cards is None or not cards.startswith(b"%PDF-"):
        results["cards_pdf"] = (False, "missing or not a PDF")
    else:
        text = _pdf_strings(cards)
        leaked = [n for n in names if n in text]
        labels = all(re.search(rf"\b{label}\b", text) for label in "ABCD")
        results["cards_pdf"] = (
            not leaked and labels,
            f"PDF; labels A-D present: {labels}; whisky names leaked: {leaked or 'none'}",
        )

    sheet = read("answer_sheet_pdf")
    if sheet is None or not sheet.startswith(b"%PDF-"):
        results["answer_sheet_pdf"] = (False, "missing or not a PDF")
    else:
        text = _pdf_strings(sheet)
        missing = [n for n in names if n not in text]
        results["answer_sheet_pdf"] = (
            not missing,
            f"PDF; whisky names missing: {missing or 'none'} (text search, may miss wrapped text)",
        )

    chart = read("flavour_chart_png")
    ok = chart is not None and chart.startswith(b"\x89PNG\r\n\x1a\n")
    results["flavour_chart_png"] = (ok, "PNG signature" if ok else "missing or not a PNG")

    csv_bytes = read("shopping_list_csv")
    if csv_bytes is None:
        results["shopping_list_csv"] = (False, "missing")
    else:
        try:
            rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
            items = [r for r in rows if (r.get("label") or "").strip().upper() != "TOTAL"]
            total = sum(round(float(r["line_total_eur"]) * 100) for r in items)
            ok = len(items) == 4 and total == plan.total_cost_cents
            results["shopping_list_csv"] = (
                ok,
                f"{len(items)} rows, line totals {total} cents vs plan {plan.total_cost_cents}",
            )
        except (KeyError, ValueError, UnicodeDecodeError) as error:
            results["shopping_list_csv"] = (False, f"unreadable CSV: {error!r}")
    return results


# --- The run ---------------------------------------------------------------------------------


async def export_workspace(backend: SmolSandboxBackend, out_dir: Path) -> list[str]:
    """Copy pack/ and the agent's own scripts from the VM to the host, before the VM is deleted."""
    machine = await backend.get_sandbox()
    listing = await backend.run(
        ["sh", "-c", "find pack -maxdepth 1 -type f; find . -maxdepth 1 -name '*.py' -type f"],
        timeout=20,
    )
    copied = []
    for rel in sorted(p.strip().removeprefix("./") for p in listing.stdout.splitlines()):
        if not rel:
            continue
        target = out_dir / rel if rel.startswith("pack/") else out_dir / "guest_scripts" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(await machine.read_file(f"/workspace/{rel}"))
        copied.append(str(target.relative_to(out_dir)))
    return copied


async def run() -> None:
    config.require_openai_key()
    tracing = config.configure_logfire()
    guest.wheel_files()  # fail early with a clear message if the wheelhouse is missing
    out_dir = config.OUTPUT_DIR / VARIANT
    out_dir.mkdir(parents=True, exist_ok=True)
    agent = build_agent()
    print(f"[{VARIANT}] model={config.get_agent_model()} tracing={'logfire' if tracing else 'off'}")

    backend = SmolSandboxBackend(
        image=guest.GUEST_IMAGE,
        cpus=guest.VM_CPUS,
        memory_mb=guest.VM_MEMORY_MB,
        allow_internet_access=False,
    )
    try:
        t0 = time.perf_counter()
        setup_seconds = await guest.install_guest_packages(backend)
        network_closed = await guest.guest_network_closed(backend)
        if not network_closed:
            raise RuntimeError("Guest VM has network access; refusing to continue.")
        boot_and_setup = time.perf_counter() - t0
        print(f"VM {backend.ref.id} ready in {boot_and_setup:.1f}s (network closed)")

        start = time.perf_counter()
        result = await asyncio.wait_for(
            agent.run(f"{TASK}\n\n{PACK_TASK}", workspace=backend),
            timeout=RUN_TIMEOUT_SECONDS,
        )
        elapsed = time.perf_counter() - start
        copied = await export_workspace(backend, out_dir)
    finally:
        if backend.ref is not None:
            await SmolSandbox().destroy(backend.ref)
            print(f"VM {backend.ref.id} deleted")

    pack: TastingPackResult = result.output
    report = validate_plan(pack.plan)
    artifact_checks = verify_artifacts(out_dir, pack.plan)
    messages = result.all_messages()
    snippets = metrics.run_code_snippets(messages)
    run_metrics = metrics.collect(
        variant=VARIANT,
        model=config.get_agent_model(),
        result=result,
        elapsed=elapsed,
        validation_valid=report.valid,
        comparable_with=[],
        uses_code_mode=True,
        notes=[
            "Adds artifact generation: not directly comparable with tool_calls/monty.",
            f"VM boot + offline package install before the agent ran: {boot_and_setup:.1f}s "
            f"(install {setup_seconds:.1f}s), not included in elapsed_seconds.",
            f"Guest network closed: {network_closed}.",
            f"Artifacts valid: {all(ok for ok, _ in artifact_checks.values())}.",
        ],
    )

    for i, code in enumerate(snippets, start=1):
        print(f"\n--- run_code snippet {i} (executed in Monty) ---\n{code}")
    reporting.print_plan(pack.plan)
    reporting.print_validation(report)
    print("\nArtifacts (copied from the VM, checked on the host):")
    for kind, (ok, detail) in artifact_checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {EXPECTED_FILES[kind]}: {detail}")
    reporting.print_metrics(run_metrics)

    reporting.save_run(
        out_dir,
        output=pack,
        report=report,
        metrics=run_metrics,
        messages=messages,
        snippets=snippets,
    )
    (out_dir / "artifact_checks.json").write_text(
        json.dumps({k: {"ok": ok, "detail": d} for k, (ok, d) in artifact_checks.items()}, indent=2)
    )
    print(f"\nCopied from VM: {copied}")
    print(f"Saved to {out_dir}/")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
