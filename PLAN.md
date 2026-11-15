# Implementation plan: whisky blind-tasting sample

Plan for the three-way comparison (ordinary tool calls, Monty via CodeMode, Monty + Smol).
It is based on the project as it exists now and on the source of the installed packages.

## 1. What is already there

| Item | State | Action |
| --- | --- | --- |
| `pyproject.toml` | Python ≥3.12, uv_build, logfire, python-dotenv, `pydantic-ai-slim[openai]==2.68.0`, `pydantic-ai-harness[codemode,smol]>=0.68.0`, dev: pytest, ruff | Pin harness to `==0.68.0` (lock already resolves 0.68.0, so the lock does not move). Add `[tool.ruff]` and `[tool.pytest.ini_options]` (marker `integration`). Replace the placeholder description. Do **not** add an `openai` extra to the harness. |
| `[project.scripts] whisky-sandbox-demo = "whisky_sandbox_demo:main"` | Hello-world stub | Keep the script; make `main()` print the three run commands. |
| `config.py` | Loads `.env`, `get_model()` from `DEMO_MODEL` | Keep; add `openai_model_name()` (prefix `openai:` when missing), `require_openai_key()` (checks presence only, never prints), `configure_logfire()`, `OUTPUT_DIR`. |
| `.env.example` | `OPENAI_API_KEY=`, `DEMO_MODEL=gpt-6-luna` (staged + modified) | Keep values; add a comment line and optional `LOGFIRE_TOKEN=`. |
| `.gitignore` | Already ignores `.env`, `output/` | Add `guest/` (downloaded wheelhouse). |
| `blog.md`, `.idea/` | Unrelated | Leave untouched. |

Locked versions: pydantic-ai-slim 2.68.0, pydantic-ai-harness 0.68.0, pydantic-monty 1.6.0,
smolmachines 1.35.0, logfire 5.6.0, openai 3.51.0. Host: macOS arm64, `smol.local_availability()`
returns True, and an `OPENAI_API_KEY` is set in `.env`, so live runs are possible.

## 2. API facts verified in the installed source

- **CodeMode** (`pydantic_ai_harness.CodeMode`): wraps selected tools into one `run_code` tool executed
  in Monty. `tools=` accepts a list of names, so Demo 3 can fold only the domain tools.
  `resource_limits={'max_duration_seconds', 'max_memory', ...}` and `max_tool_calls` bound execution.
  No host filesystem/env access unless `mount`/`os_access` is passed (we pass neither).
  Monty allows stdlib only (`math`, `itertools`, `json`, ...), so no pandas in generated code.
- **Inspecting generated code**: `run_code` calls are promoted to `RunCodeCallPart` with `.code`.
  The `ToolReturnPart` (`tool_kind == 'code_mode.run_code'`) carries `metadata['tool_calls']` and
  `metadata['tool_returns']` — this gives exact nested call counts.
- **Return schemas**: tools must have return annotations or CodeMode warns and renders `-> Any`;
  Pydantic models / TypedDicts are rendered as typed stubs.
- **SmolSandbox** (`pydantic_ai_harness.smol_sandbox`): `SmolSandbox(image, cpus, memory_mb,
  allow_internet_access=False, working_dir='/workspace', env=None)`. Nothing is mounted, no host env
  reaches the VM. A run never deletes its VM: cleanup is our job via `SmolSandbox().destroy(ref)`.
  The documented pattern for guaranteed cleanup is to build `SmolSandboxBackend` ourselves and pass
  it as `workspace=backend`, with `destroy(backend.ref)` in `finally`.
- **Shell / FileSystem**: `Shell(allowed_commands=[...], default_timeout=..., max_output_chars=...)`,
  `FileSystem(root_dir=..., allowed_patterns=..., ...)`. Both act on `ctx.workspace`, i.e. the VM.
- **Guest image preparation**: smolmachines 1.35 has `Machine.pack(path)` → a `.smolmachine` artifact
  usable as `MachineConfig(image=path)`. That allows a one-off prepare step with network, followed
  by runtime VMs without network. To verify during implementation: that a VM created from the pack
  with `allow_internet_access=False` truly has no network (we probe it), and that
  `SmolSandboxBackend(image=<path>)` accepts a local pack path. Fallback if not: build an OCI image
  with Docker (`python:3.12-slim` + matplotlib + reportlab) and point `image=` at it.

## 3. Package layout

```
src/whisky_sandbox_demo/
  __init__.py          main() prints run commands
  config.py            env, model name, logfire, output dirs (extend existing)
  models.py            Pydantic models: Whisky, Supplier, Offer, TastingBrief, TastingPlan, ...
  data/
    whiskies.json      ~20 fictional whiskies (id, name, distillery, type, abv, bottle_ml, notes, flavour scores 0-10)
    suppliers.json     3 fictional suppliers + offers (price_cents, stock_bottles)
  fixtures.py          load + cache fixtures (importlib.resources)
  tools.py             the four domain tools (plain functions, mode-independent)
  prompts.py           shared task text, Demo 3 addition, system instructions
  validation.py        independent validator → ValidationReport
  metrics.py           RunMetrics extraction from AgentRunResult
  reporting.py         console printing + JSON writing
  demos/
    tool_calls.py      Demo 1
    monty.py           Demo 2
    monty_smol.py      Demo 3
    _runner.py         shared "build agent, run, time, validate, save" helper
scripts/
  prepare_guest_image.py   one-off: boots VM with network, installs deps, packs .smolmachine
tests/
  test_fixtures.py, test_tools.py, test_quantities.py, test_validation.py, test_solvability.py
  test_integration.py      @pytest.mark.integration, skipped without key / VM
```

`fixtures.py` and `metrics.py` are small additions to the suggested structure; they keep `tools.py`
and `reporting.py` focused.

## 4. Fixture data (real whiskies, snapshot prices, illustrative scores)

Whisky identities, ABV, prices and stock come from a snapshot of
[Slijterij De Helm](https://slijterijdehelm.nl/product-categorie/whisky/) taken on 2026-11-15
(the shop's public WooCommerce Store API, the same data its product pages show). The fixture records
`snapshot_date` and each product's `source_url`. Prices and stock will drift; the demo never fetches
live data.

What is *not* copied: the shop's product descriptions. Tasting notes are short, self-written summaries.
Flavour scores (sweetness, fruitiness, smokiness, intensity, 0–10) are the author's illustrative
estimates and are labelled as such in the README and in generated output.

| ID | Whisky | Type | ABV | De Helm price | Stock | Role in the scenario |
| --- | --- | --- | --- | --- | --- | --- |
| W01 | Tamnavulin Double Cask | single malt, Speyside | 40% | €26.95 | 2 | sweet opener |
| W02 | Glen Moray Sherry Cask | single malt, Speyside | 40% | €27.95 | 2 | sweet/fruity |
| W03 | Singleton 12 Years Old | single malt, Speyside | 40% | €34.95 | 6 | sweet opener |
| W04 | Aberlour 10 Forest Reserve | single malt, Speyside | 40% | €37.95 | 3 | rich |
| W05 | Glenlivet Founder's Reserve | single malt, Speyside | 40% | €38.95 | 2 | fruity |
| W06 | Tomintoul 10 Years Old | single malt, Speyside | 40% | €39.95 | 6 | gentle, rich |
| W07 | Old Pulteney 12 Years Old | single malt, Highland | 40% | €38.95 | 1 | coastal middle |
| W08 | Glen Scotia Double Cask | single malt, Campbeltown | 46% | €38.95 | 1 | rich middle |
| W09 | Bowmore 9 Years Old | single malt, Islay | 40% | €34.95 | 4 | light smoke |
| W10 | Finlaggan Original | single malt, Islay | 40% | €29.95 | 6 | smoky, cheap |
| W11 | Ileach Single Islay Malt | single malt, Islay | 40% | €29.95 | 2 | smoky, cheap |
| W12 | Laphroaig 10 Years Old | single malt, Islay | 40% | €40.95 | 2 | smoky finale |
| W13 | Hart Brothers Islay Peated 50% | single malt, Islay | 50% | €34.95 | 6 | **edge case: exactly 50%** |
| W14 | Finlaggan Cask Strength | single malt, Islay | 58% | €42.95 | 5 | **trap: above ABV limit** |
| W15 | Ileach Cask Strength | single malt, Islay | 58% | €47.95 | 2 | **trap: above ABV limit** |
| W16 | Scarabus Islay Single Malt | single malt, Islay | 46% | €43.95 | 0 | **trap: sold out** |
| W17 | Speyburn 10 Years Old | single malt, Speyside | 40% | €32.95 | 0 | **trap: backorder only** |
| W18 | Monkey Shoulder | blended malt | 40% | €29.95 | 3 | **trap: not a single malt** |
| W19 | Rock Island | blended malt, Island | 46.8% | €39.95 | 1 | **trap: not a single malt** |
| W20 | Teeling Small Batch | blend (malt + grain), Ireland | 46% | €32.95 | 2 | **trap: not a single malt** |

Notes on the data:
- Bottle size: the shop does not state it for most of these; all are the standard 70 cl retail
  bottle. The fixture stores `bottle_ml: 700` with `bottle_ml_source: "assumed standard 70 cl"`
  where the page doesn't say so. Monkey Shoulder's ABV (40%) is also not on the page and is marked
  as from the label.
- Glenfarclas 10 was dropped: its page states two different ABVs.
- `type` is my classification. The shop's "malt" category also contains blended malts, so the agent
  cannot rely on category names — a realistic trap in itself.
- "kan nabesteld worden" (can be reordered) is ignored: stock means bottles on the shelf now.

Suppliers:
- `S1` **Slijterij De Helm** — real snapshot prices and stock, as above.
- `S2` "Peat & Price" and `S3` "Cask Corner" — **explicitly fictional** suppliers selling the same
  real whiskies, with prices and stock derived from the snapshot. S2 is about 15% cheaper but lacks
  the sweet Speysiders and has zero stock on Laphroaig 10; S3 is about 10% more expensive with full
  stock. There is only one real shop, and three suppliers are needed for the one-supplier
  trade-off. The fixture flags each supplier with `fictional: true/false`.

Solvability: at De Helm alone there are many valid sets (e.g. Tamnavulin → Glen Moray Sherry →
Glen Scotia Double Cask → Laphroaig 10 = €134.80), so the €200 budget leaves room for choice. (Later lowered to €120: see the update at the end.)
At S2 no set has a sweet opener plus a smoky finish. The brute-force test checks both.
- Required bottles: `ceil(participants * pour_ml / bottle_ml)` → 8×20 ml = 160 ml → 1 bottle of 700 ml
  each. Tests also check larger groups (e.g. 40 people → 2 bottles of 700 ml, 3 of 500 ml) and the
  budget with multiple bottles.

## 5. Domain tools (`tools.py`)

All plain, synchronous, typed functions returning Pydantic models / lists of them. Registered with
`agent.tool_plain` in every demo, so the implementations are identical across modes.

| Tool | Returns |
| --- | --- |
| `get_tasting_brief()` | participants, pour_ml, whisky_count, budget_cents, max_abv, required type, progression wish, **supplier list (id, name, notes)** |
| `search_whiskies(style: str \| None = None)` | list of whisky summaries (id, name, type, abv, style, bottle_ml). No filtering on ABV/type: the agent must apply constraints. |
| `get_whisky_details(ids: list[str])` | full records incl. tasting notes and flavour scores; unknown ids reported, not raised |
| `get_supplier_offers(supplier_id: str, whisky_ids: list[str])` | offers with `price_cents`, `stock_bottles`, `available: bool`; missing items listed |

No tool computes the selection, cost totals, or ordering. The agent does that (in text reasoning for
Demo 1, in Monty code for Demo 2/3) and the validator recomputes it.

## 6. Output schema (`models.TastingPlan`)

```
TastingPlan
  supplier_id, supplier_name
  participants, pour_ml
  whiskies: list[PlannedWhisky]   # ordered A..D: position, whisky_id, name, distillery, type, abv,
                                  # bottle_ml, bottles, unit_price_cents, line_total_cents,
                                  # required_ml, available_ml, tasting_role
  total_cost_cents
  selection_rationale: str
  ordering_rationale: str
  rejected_alternatives: list[RejectedAlternative]  # whisky_id or supplier_id + reason
```

Demo 3 uses `TastingPackResult(plan: TastingPlan, files: list[GeneratedFile])` where each file has the
guest path, kind and a short description.

## 7. Validation (`validation.py`)

`validate_plan(plan, fixtures) -> ValidationReport` with a list of `Check(name, passed, detail,
kind='constraint' | 'recommendation')`:

Constraints (objective): four entries, distinct ids, all `single_malt`, `abv <= 50.0`, single supplier
that exists, every whisky offered by that supplier, prices/names/ABV/bottle size match the fixtures,
bottles ≥ required, stock ≥ bottles, line totals and grand total correct, total ≤ budget.

Recommendation (reported, not pass/fail for validity): flavour progression — sweetness should not
increase towards the end, smokiness of the last is the maximum, intensity roughly non-decreasing.

## 8. Demo wiring

Shared runner (`demos/_runner.py`): load config, optionally configure Logfire, build an agent
(`Agent(openai_model, output_type=..., instructions=prompts.SYSTEM)`), register domain tools, run
with `asyncio`, time with `time.perf_counter()`, validate, print, write
`output/<variant>/plan.json`, `metrics.json`, `messages.json` (via `ModelMessagesTypeAdapter`).

- **Demo 1 – tool_calls**: no capabilities. Default parallel tool execution. No prescribed number of
  steps.
- **Demo 2 – monty**: `capabilities=[CodeMode(tools='all', max_tool_calls=50,
  resource_limits={'max_duration_seconds': 10, 'max_memory': 128 MiB})]`. No `mount`/`os_access`.
  Every `RunCodeCallPart.code` is written to `output/monty/code/snippet_NN.py` and printed.
- **Demo 3 – monty_smol**:
  - `CodeMode(tools=[the four domain tool names])` — domain tools stay on the host and are called from
    Monty. Shell and FileSystem remain ordinary top-level tools, so the model writes a full Python
    program to the VM and runs it there.
  - `Shell(allowed_commands=['python', 'python3', 'ls', 'cat', 'file'], default_timeout=120,
    max_output_chars=20_000)` and `FileSystem(...)` scoped to the workspace dir.
  - `SmolSandboxBackend(image=<prepared .smolmachine>, cpus=2, memory_mb=1024,
    allow_internet_access=False)` built by the demo, passed as `workspace=backend`; nothing mounted,
    no env passed. `finally: await SmolSandbox().destroy(backend.ref)`.
  - Before cleanup, the host copies `pack/*` from the VM via `Workspace(backend).read_bytes(...)` into
    `output/monty_smol/`, then verifies types: PDF magic `%PDF-`, PNG signature, CSV parses with
    expected headers and totals matching the plan, and that the cards PDF text does not contain any
    whisky name (via a simple text check on the PDF stream when uncompressed, else via a guest-side
    check we run before export).
  - Pre-flight network probe in the VM (`python -c "socket.create_connection(...)"`) recorded in
    metrics as `guest_network_disabled: true/false`.

## 9. Metrics (`metrics.py`)

Per run: variant, model, package versions (`importlib.metadata`), elapsed seconds, `result.usage()`
(`requests`, `input_tokens`, `output_tokens`, `tool_calls`), top-level tool calls counted from
`ToolCallPart`s by name, nested Code Mode calls counted from `run_code` return metadata, number of
`run_code` snippets, validation outcome. Unavailable values are `null`, never estimated.
Demo 3 adds artifact list and VM settings and is flagged `comparable_to: null`.

## 10. Tests (offline)

- Fixtures load; 20 whiskies; ids unique; snapshot date present; S1 offers have a `source_url`; S2/S3 flagged fictional.
- `search_whiskies` style filter; `get_whisky_details` unknown ids; `get_supplier_offers` prices and
  stock, out-of-stock and missing items.
- `bottles_needed` rounding for 8, 35, 36, 40 people and 500/700 ml.
- Validator: a known-good plan passes; mutations fail the right check (wrong price, ABV > 50, blend,
  duplicate, mixed supplier, insufficient stock, arithmetic error, over budget).
- Brute-force solvability: enumerate 4-combinations per supplier, assert ≥1 valid selection overall,
  ≥2 in total (multiple valid answers), and none at S2.
- `test_integration.py`: `@pytest.mark.integration`, skipped unless `OPENAI_API_KEY` is set (model
  run) or `smol.local_availability()` is true and the prepared image exists (VM boot + network probe).

## 11. README

Setup with uv, `.env.example`, the three run commands, guest-image preparation command
(`uv run python scripts/prepare_guest_image.py`), the boundary diagram (host: agent + domain tools;
Monty: generated coordination code; Smol VM: files + full Python programs), output files, Logfire
(optional, `LOGFIRE_TOKEN` or `logfire auth`), the limits of the comparison (single runs, model
non-determinism, Demo 3 not comparable), data provenance (De Helm snapshot of 2026-11-15, fictional S2/S3, illustrative flavour scores), and a note that uv workspaces are
unrelated to agent execution workspaces.

## 12. Verification steps

1. `uv run ruff check . && uv run ruff format --check .`
2. `uv run pytest -m "not integration"`
3. If key present: run Demo 1 and Demo 2 once each, inspect `output/`.
4. If VM available: prepare the guest image, run Demo 3, confirm artifacts and VM cleanup.
5. Report what ran, what passed, and what remains unverified.

## Open risks

- The packed-image route for Smol must be confirmed (network off at runtime, local path accepted).
  Docker-built OCI image is the fallback.
- `DEMO_MODEL=gpt-6-luna` must be a model the account can call; the demos print a clear error otherwise.
- Shell's default `denied_commands` may need adjusting if it blocks `python`; checked during
  implementation.

## Update after implementation (2026-11-15)

- The packed-image route failed: `Machine.pack()` needs `mkfs.ext4` (e2fsprogs) on the host.
  Replaced by a wheelhouse: `scripts/prepare_guest_image.py` downloads Linux wheels on the host,
  and every demo 3 VM installs them offline. The guest has no network at any point.
- `fixtures.py`, `calculations.py`, `metrics.py` and `guest.py` were added to the suggested layout.
- See README.md for the final structure and blog.md for build notes and measured results.
- Budget lowered from €200 to €120 after the first runs showed it never limited the choice
  (all 715 combinations fit). At €120, 7 sets are valid, all at S1; none at S2 or S3.
