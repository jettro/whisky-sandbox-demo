# Whisky sandbox demo

One agent task, three ways to run it, to compare **ordinary tool calling**, **Code Mode with
Monty**, and **Monty plus a Smol microVM** in [Pydantic AI](https://pydantic.dev/docs/ai/)
and [Pydantic AI Harness](https://pydantic.dev/docs/ai/harness/).

The task: organise a blind whisky tasting.

> Organise a blind tasting for eight people with four different single malt whiskies. The total
> bottle budget is €200. Begin accessible and sweet, and finish smoky. Each whisky must be at
> most 50% ABV. Buy all bottles from one supplier, with sufficient stock. Each participant
> receives 20 ml of each whisky.

Demo 3 adds: *"Create a printable blind-tasting pack with cards labelled A–D, a separate host
answer sheet, a shopping-list CSV and a flavour chart."*

## About the data

- **Whiskies and supplier S1 are real**: names, ABV, prices and stock of 20 whiskies are a
  snapshot of [Slijterij De Helm](https://slijterijdehelm.nl/product-categorie/whisky/) taken on
  **2026-11-15**. Prices and stock have changed since. Each S1 offer links to its product page.
- **Suppliers S2 "Peat & Price" and S3 "Cask Corner" are fictional.** They sell the same
  bottles at derived prices, so the single-supplier trade-off has something to trade.
- **Flavour scores (0–10) are illustrative estimates**, and the tasting notes are self-written
  summaries, not the shop's descriptions.
- Bottle size is the standard 70 cl; the shop does not state it on most pages.
- Built-in traps: cask-strength versions above 50% ABV, blended malts listed in the shop's
  "malt" category, sold-out and backorder-only bottles, and a cheap supplier that cannot fill
  the flight. Hart Brothers Islay Peated is exactly 50%, which is allowed.
- Money is integer euro cents and stock is whole bottles. Bottles per whisky =
  `ceil(participants × pour_ml / bottle_ml)`, so larger groups work too.

The generated output repeats this notice (`DATA_NOTICE.txt`, and on the answer sheet and chart).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync
cp .env.example .env   # then set OPENAI_API_KEY and DEMO_MODEL
```

`DEMO_MODEL` is an OpenAI model name, such as `gpt-6-luna`. A bare name gets the `openai:`
prefix; a full Pydantic AI model string such as `openai:gpt-6-luna` also works.

Pinned versions: `pydantic-ai-slim[openai]==2.68.0` and
`pydantic-ai-harness[codemode,smol]==0.68.0` (Monty 1.6.0, smolmachines 1.35.0). The harness has
no `openai` extra; the OpenAI dependency comes from `pydantic-ai-slim[openai]`.

## Running the demos

```bash
uv run python -m whisky_sandbox_demo.demos.tool_calls
```

```bash
uv run python -m whisky_sandbox_demo.demos.monty
```

```bash
uv run python scripts/prepare_guest_image.py
```

```bash
uv run python -m whisky_sandbox_demo.demos.monty_smol
```

Or use the Makefile (`make help` lists every target):

| Target | Does |
| --- | --- |
| `make install` / `make env` | `uv sync` / create `.env` from `.env.example` |
| `make demo-tools`, `make demo-monty`, `make demo-smol` | Demo 1, 2, 3 (`demo-smol` prepares the guest wheels first if missing) |
| `make demos` | All three in order |
| `make guest-image` | Download and verify the guest wheels |
| `make check` | Ruff and the offline tests (`make lint`, `make test`, `make format` separately) |
| `make test-integration` | Live model and VM checks |
| `make clean` / `make clean-guest` | Remove `output/` and caches / the wheelhouse |

Each demo prints the plan, the validation result and the run metrics, and saves them under
`output/<variant>/`. Set `PYDANTIC_AI_NO_BANNER=1` to hide Pydantic AI's start-up banner.

| Demo | What changes | Agent tools |
| --- | --- | --- |
| `tool_calls` | Nothing: the four domain tools are ordinary tools | 4 domain tools |
| `monty` | `CodeMode` folds the tools into one `run_code` tool; the model writes Python | `run_code` |
| `monty_smol` | Same Code Mode, plus a Smol VM workspace with `Shell` and `FileSystem` | `run_code`, `run_command`, file tools |

All three use the same model, task, instructions, domain tools and output schema
(`TastingPlan`; demo 3 wraps it in `TastingPackResult` with the list of generated files).

### The domain tools

`get_tasting_brief()` (requirements, rules and supplier ids), `search_whiskies(style)`,
`get_whisky_details(ids)` and `get_supplier_offers(supplier_id, whisky_ids)` only look things up.
They take batches where that makes sense and are not filtered: the agent applies the ABV, type,
stock and budget rules, compares suppliers and picks the order. The same functions are used in
every demo ([`tools.py`](src/whisky_sandbox_demo/tools.py)).

### Validation

[`validation.py`](src/whisky_sandbox_demo/validation.py) checks the agent's plan against the
fixture data, independent of what the agent claimed: four distinct single malts, ABV ≤ 50%, one
existing supplier that sells each whisky, enough bottles and stock, prices and product facts
that match, correct line totals and total, and the budget. These decide `VALID`. The flavour
progression (sweetest first, smokiest last) is reported separately as a **recommendation**.

## Where code runs

```
 Host process ───────────────────────────────────────────────────────────────
 │ Agent loop, OpenAI calls, the four domain tools (plain Python functions)
 │
 │  Monty (demos 2 and 3), sandboxed inside the host process
 │  │ Runs the model's run_code snippets: calls the domain tools, filters,
 │  │ compares offers. Stdlib subset only; no files, env, network or clock.
 │  │ Limits: 10 s and 128 MiB per snippet, 50 nested tool calls.
 │
 │  Smol microVM (demo 3 only), its own kernel and filesystem
 │  │ Shell (run_command; only python, python3, ls) and FileSystem act on
 │  │ ctx.workspace = this VM. The model writes make_pack.py and runs it with the
 │  │ guest's Python, matplotlib and reportlab. No network, nothing mounted,
 │  │ no host environment variables, 2 vCPUs, 1 GiB RAM, 120 s per command.
```

Adding Smol does **not** move the domain tools into the VM: they stay host functions, called from
Monty. Only the workspace tools (`Shell`, `FileSystem`) operate in the VM. `Coder` is not used;
`Shell` and `FileSystem` are narrower and enough for writing and running one script.

Demo 3 boots the VM itself (`SmolSandboxBackend`), passes it to the run as `workspace=`, copies
`pack/` and the agent's script to the host, and deletes the VM in a `finally` block, also when
the run fails. The whole agent run has a 600 s timeout.

## Smol prerequisites and the guest image

- A host that can run smolvm: macOS on Apple silicon, or Linux x86_64/aarch64 (glibc ≥ 2.34) with
  access to `/dev/kvm`. Check with
  `uv run python -c "import smol; print(smol.local_availability())"`.
- No Docker and no cloud account are needed. The first run pulls `python:3.12-slim`.

The guest needs matplotlib and reportlab, but it has no network. `scripts/prepare_guest_image.py`
solves that once:

1. On the host, it downloads Linux wheels (for the VM's CPU architecture, Python 3.12) for
   matplotlib, reportlab and their dependencies into `guest/wheels/` (about 42 MB, git-ignored).
2. It boots a throwaway VM with networking off, installs the wheels with `pip --no-index`,
   imports both libraries, confirms the network is closed, and deletes the VM.

Each demo 3 run then copies the wheels into its fresh VM and installs them offline (about 5 s
including boot). Installing these libraries in the host project would not help: the report
script runs inside the VM.

> Why not a prepared VM image? smolmachines 1.35 can pack a stopped VM into a `.smolmachine`
> artifact, but packing needs `mkfs.ext4` on the host (e2fsprogs). The wheelhouse avoids that
> extra host tool and keeps the guest offline even while preparing.

## Output files

```
output/
  tool_calls/   result.json  validation.json  metrics.json  messages.json  DATA_NOTICE.txt
  monty/        ...same, plus code/snippet_NN.py (the Python the model sent to Monty)
  monty_smol/   ...same, plus artifact_checks.json
                pack/cards.pdf  pack/answer_sheet.pdf  pack/shopping_list.csv  pack/flavour_chart.png
                guest_scripts/make_pack.py   (the script the model wrote and ran in the VM)
```

`metrics.json` records the variant, model, installed package versions, elapsed time, model
requests, input/output tokens, Pydantic AI's tool-call counter, **top-level** tool calls by name,
**nested** calls made from inside `run_code` (from Code Mode's own metadata), the number of
snippets and the validation result. Anything the framework does not report is `null`; nothing is
estimated. The exported pack is checked on the host: PDF/PNG signatures, no whisky names on the
cards, every name on the answer sheet, CSV line totals equal to the plan.

## Tracing

Tracing is optional. Set `LOGFIRE_TOKEN` in `.env` and the demos call `logfire.configure()` and
`logfire.instrument_pydantic_ai()`; without it, nothing is sent anywhere. In Logfire each
`run_code` span shows the nested tool calls under it. API keys are never printed or logged.

## Tests

```bash
uv run ruff check . && uv run ruff format --check .
```

```bash
uv run pytest
```

The default run is offline: no OpenAI key, network or VM. It covers fixture loading and the
traps in the data, tool filtering, prices and stock, bottle rounding (8 to 60 people, 50 and
70 cl), plan validation including invalid plans, a brute-force check that valid selections exist
(more than one, none at the discount supplier), and the artifact checks on synthetic files.

Optional live checks (model calls and a real VM), each skipped when its prerequisite is missing:

```bash
uv run pytest -m integration
```

## Limits of the comparison

- Demos 1 and 2 are the controlled comparison: same model, prompt, tools, data and schema.
  Demo 3 also generates files in a VM, so its time and tokens are not comparable with them.
- These are single runs of a non-deterministic model. Request counts, tokens and time vary
  between runs; run each demo several times before drawing conclusions.
- The task is small (four lookups), which favours neither approach much. Code Mode tends to pay
  off when there are more, dependent calls and more data to filter.
- Elapsed time includes OpenAI latency and is wall-clock on one machine.

## uv workspaces are something else

"Workspace" means two unrelated things here. A *uv workspace* is a way to manage several Python
packages in one repository; this project is a single uv package and does not use one. The *agent
workspace* (`ctx.workspace`) is where an agent's shell and file tools act — in demo 3, the Smol
microVM.
