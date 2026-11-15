# Blog

## Installing the dependencies

```bash
uv init --package --python 3.12 whisky-sandbox-demo
cd whisky-sandbox-demo

uv add "pydantic-ai-harness[codemode,smol]"
uv add "pydantic-ai-slim[openai]==2.68.0"
uv add python-dotenv logfire
uv add --dev ruff pytest

uv sync
```

---

# Notes from the build (raw material, not prose)

## Versions actually installed (uv.lock, 2026-11-15)

- pydantic-ai-slim 2.68.0, pydantic-ai-harness 0.68.0, pydantic-monty 1.6.0,
  smolmachines 1.35.0, logfire 5.6.0, openai 3.51.0. Host: macOS on Apple silicon.
- `uv add "pydantic-ai-harness[codemode,smol]"` wrote `>=0.68.0`; pinned to `==0.68.0` so the post's
  code keeps matching the API (harness is 0.x: minor releases may change the API).
- The harness has no `openai` extra; the provider extra lives on `pydantic-ai-slim[openai]`.
- `smol.local_availability()` → `(True, None, None)` on this Mac: no Docker, no cloud account needed.

## Reading the installed source instead of the newest docs

- Every harness capability ships its README inside the wheel:
  `.venv/lib/python3.12/site-packages/pydantic_ai_harness/<capability>/README.md`. That README
  matches the installed version exactly — better than the website when versions move fast.
- CodeMode in one sentence: it folds the selected tools into one `run_code` tool; the model writes
  Python that runs in Monty, and every call from that Python is dispatched back to the real tool
  on the host.
- Monty is a Python *subset*: stdlib only (math, itertools, json, collections, ...), no third-party
  imports, no file/env/clock access unless you pass `mount=` / `os_access=`. That is the point:
  it is a sandbox for *coordination code*, not for running arbitrary programs.
- Default limits: 30 s execution and 256 MiB heap per snippet, 100 nested tool calls per `run_code`.
- The generated code is inspectable: `run_code` calls become `RunCodeCallPart` with `.code`, and the
  `run_code` return carries `metadata['tool_calls']` / `metadata['tool_returns']` for nested calls.
- SmolSandbox: a microVM with its own kernel, nothing mounted, no host env vars, **no network by
  default**. A run never deletes its VM — cleanup is your job (`SmolSandbox().destroy(ref)`).
- `SmolSandbox` only supplies the workspace. Tools that *use* it (Shell, FileSystem, Coder, or your
  own via `ctx.workspace`) are separate. Adding Smol does not move your other tools into the VM.

## The data: real whiskies instead of made-up ones

- First plan used ~20 fictional whiskies. Switched to a snapshot of a real Dutch shop
  (Slijterij De Helm, 2026-11-15): names, ABV, prices and stock are real.
- The shop's site is WooCommerce; its public Store API (`/wp-json/wc/store/v1/products`) returns
  price in cents and stock text like "2 op voorraad" — much nicer than scraping HTML, and it
  happens to match the "money as integer cents" rule of the demo.
- Did not copy product descriptions; tasting notes are self-written, flavour scores are my own
  illustrative estimates.
- Realistic traps came for free: the shop's "malt" category contains blended malts (Monkey Shoulder,
  Rock Island), so an agent that trusts category names picks a non-single-malt. Cask-strength
  versions (58%) of cheap Islay malts are tempting but break the 50% ABV rule. Hart Brothers Islay
  Peated is exactly 50%: a good "at most" boundary test.
- Only one real shop, but the scenario needs a single-supplier trade-off, so two clearly fictional
  suppliers sell the same bottles at derived prices.

## Design choices worth explaining

- The four tools only *look things up* and accept batches (`get_whisky_details(ids)`,
  `get_supplier_offers(supplier_id, whisky_ids)`). Splitting them artificially would make plain
  tool calling look worse than it is — not a fair comparison.
- Return types are Pydantic models. Code Mode turns them into typed stubs for the model; without
  a return annotation a tool renders as `-> Any` and CodeMode warns.
- Independent validator: recomputes everything from the fixtures (type, ABV, stock, prices,
  arithmetic, budget). The flavour order is reported as a *recommendation*, never as pass/fail.
- A brute-force test enumerates all 4-whisky combinations per supplier: the puzzle has many
  answers at S1, none at the discount supplier. Nice to show the agent isn't solving an
  impossible puzzle, and that there isn't one "right" answer.

## Live results, 2026-11-15, model gpt-6-luna, one run each

| | tool_calls | monty | monty_smol |
| --- | --- | --- | --- |
| elapsed | 26.6 s | 20.9 s | 41.8 s (+5.0 s VM boot & offline pip) |
| model requests | 4 | 4 | 6 |
| input / output tokens | 9,095 / 1,969 | 13,919 / 1,940 | 43,481 / 4,234 |
| top-level tool calls | 6 domain + final_result | 3 `run_code` + final_result | 3 `run_code`, 1 `write_file`, 1 `run_command`, final_result |
| nested calls in Monty | – | 6 (same 6 domain calls) | 6 |
| validation | valid, €133.80 | valid, €145.80 | valid, €130.80 |

Observations:
- Same number of model requests (4) in demos 1 and 2. Plain tool calling already batched the
  three supplier lookups as parallel tool calls in one response.
- Monty used ~50% *more* input tokens here: the model returned whole tool results as the last
  expression of each snippet (`brief`, `all_whiskies`, `(details, offers)`), so everything still
  flowed back into the context. Code Mode saves tokens when the code *reduces* data before
  returning; the model didn't do that on this small task.
- What Monty did nicely: snippet 3 filtered `type == 'single_malt' and abv <= brief['max_abv']`
  in Python, then fetched details and all three suppliers' offers with one `asyncio.gather`.
  The model applied the hard constraints in code, not in its head.
- All three runs picked a sensible sweet-to-smoky flight and named concrete rejections (58% cask
  strength, sold-out Scarabus, discount supplier missing the sweet malts). Different, equally
  valid answers per run: evidence for the "multiple valid selections" design.
- Demo 3 cost far more tokens than the planning, mostly the agent writing a ~6 KB report script
  and reading its output. Not comparable with demos 1-2 by design.

Small task + one run = anecdote, not a benchmark. Say so in the post.

## Things that went wrong (good blog material)

- **Packing a VM image needs a host tool.** First plan: boot a VM with network, `pip install`,
  stop it, `machine.pack()` to a `.smolmachine` file, boot later VMs from it without network.
  `pip install` worked (egress limited with `ResourceSpec(allow_hosts=["pypi.org",
  "files.pythonhosted.org"])`), but `pack()` failed:
  `mkfs.ext4 not found. Install e2fsprogs or place a pre-formatted storage-template.ext4 in ~/.smolvm/`.
- **Better solution: a wheelhouse.** Download Linux aarch64 wheels on the host
  (`uvx pip download --platform manylinux_2_28_aarch64 --python-version 3.12 --only-binary=:all:`),
  copy them into each fresh VM with the smol SDK's `write_file`, `pip install --no-index`.
  The guest never has network, not even during preparation. 13 wheels, 42 MB.
- **Numbers:** VM boot 0.9 s (image cached), copying 42 MB of wheels 0.5 s via
  `AsyncMachine.write_file`, offline install 3.5–5 s. The generic workspace file API moves
  64 KiB per shell command, so for bulk copies use the SDK handle (`backend.get_sandbox()`).
- Network probe inside the VM: `socket.create_connection(("pypi.org", 443))` →
  `[Errno -3] Temporary failure in name resolution`. No DNS, no egress. Recorded in metrics.
- **Cleanup is on you.** A run never deletes its VM. Demo 3 creates `SmolSandboxBackend` itself,
  passes it as `agent.run(..., workspace=backend)` and calls `SmolSandbox().destroy(backend.ref)`
  in `finally`. `backend.ref` is set before boot finishes, so even a cancelled boot gets cleaned up.
  Checked afterwards: 0 VMs left in smolvm's local DB.
- `smol.Machine.list()` only works against Smol Cloud (needs an API key), not for local VMs.
- My host-side PDF check first failed: ReportLab encodes page content as
  `/Filter [/ASCII85Decode /FlateDecode]` and writes `~>endstream` on the same line. A naive
  "decompress the stream and grep" missed everything — and the "no whisky names on the cards"
  check passed for the wrong reason. Lesson: test your validators on files that should fail too.
- Ruff linted the generated Monty snippets saved under `output/` (top-level `await`, undefined
  tool names). Excluded `output/` from Ruff.
- `result.usage()` is deprecated in pydantic-ai 2.68: `usage` is a property now.
- Pydantic AI 2.68 prints a start-up banner suggesting Logfire; `PYDANTIC_AI_NO_BANNER=1` hides it.
- `'openai:<model>'` resolves to `OpenAIResponsesModel` (Responses API), not Chat Completions.

## Boundaries, in one picture (for the post)

- Host: agent loop + domain tools. Unchanged in all three demos.
- Monty: the model's *coordination code* (call tools, filter, compare). Stdlib only, 10 s /
  128 MiB per snippet, no files/env/network. Runs inside the host process.
- Smol VM: *full programs and files* (matplotlib, reportlab, writing PDFs). Own kernel, no network,
  nothing mounted, no host env vars (verified: no `OPENAI_*` in the guest's `env`).
- Adding Smol does not move the domain tools into the VM. Only Shell/FileSystem act on
  `ctx.workspace`. In demo 3, `CodeMode(tools=[...domain tool names])` so the file and shell tools
  stay ordinary top-level tools.
- Shell is not a security boundary by itself ("a command reaches whatever the workspace lets it").
  The VM is the boundary; `allowed_commands=["python", "python3", "ls"]` is a guardrail on top.
- The agent wrote `make_pack.py` (~6 KB) with the plan embedded as JSON, ran it once, listed
  `pack/`. Cards: "BLIND TASTING / A / Tasting notes", no names. Chart titled
  "Flavour profile — illustrative estimates, 2026-11-15 shop snapshot".

## Makefile

- Added a Makefile so the post can show one-liners: `make demo-tools`, `make demo-monty`,
  `make demo-smol`, `make demos`, `make check`. `demo-smol` depends on `guest/wheels`, so the
  first run downloads and verifies the guest wheelhouse automatically.
- The demo targets set `PYDANTIC_AI_NO_BANNER=1` to keep terminal output (and screenshots) clean.

## Reading a Monty run: why 4 `run_code` calls? (run at 23:36)

Per-request breakdown from `messages.json` (tool_calls run from 19:42 for comparison):

| request | tool_calls: in / out tokens, calls | monty: in / out tokens, snippet |
| --- | --- | --- |
| 1 | 714 / 17, `get_tasting_brief` | 1,960 / 28, `brief = await get_tasting_brief()` |
| 2 | 1,055 / 35, `search_whiskies` | 2,309 / 46, `catalogue = await search_whiskies()` |
| 3 | 1,971 / 358, details + 3x offers (parallel) | 3,234 / 112, `asyncio.gather` offers from S1-S3 for all 20 ids |
| 4 | 5,293 / 1,716, `final_result` | 5,291 / 289, `get_whisky_details` for 8 shortlisted ids |
| 5 | – | 6,384 / 1,142, `final_result` |

- Yes, *all* domain calls go through Monty: top level is only `run_code` x4 + `final_result`;
  the 6 domain calls are nested. That is what `CodeMode(tools="all")` does.
- But each `run_code` is still one model round trip. The model used Monty as a REPL: one step,
  look at the result, decide the next step. Variables persist between snippets (`catalogue` from
  snippet 2 is reused in snippet 3), but the *thinking* happens between snippets, in the model.
- Every snippet ends with the raw value (`brief`, `catalogue`, `offers`, `details`), so all data
  flows back into the context anyway. No data reduction in code this time (an earlier run did
  filter on type and ABV in snippet 3).
- Fixed overhead: request 1 costs 1,960 input tokens vs 714. The `run_code` tool description
  carries the Python stubs of all tools plus Monty's rules (~1.2k tokens), paid on every request.
  5 requests x ~1.2k explains most of the gap (19.2k vs 9.1k input tokens in total).
- Code Mode only saves round trips and tokens when the model writes the dependent steps as one
  program and returns a compact result. The task here is small and judgment-heavy (choosing by
  tasting notes), so the model prefers to read the data itself.
- Our instructions say "Start with get_tasting_brief", which also nudges a step-by-step style.

## Experiment: "write one program" (demos/monty_program.py, 2026-11-15)

Same as demo 2 plus one instruction: fetch, filter and summarise in a single `run_code`, return
only a compact summary. Result of one run:

| request | in / out tokens | what happened |
| --- | --- | --- |
| 1 | 2,085 / 1,311 | one full program (2.4 KB) — **rejected by Monty's type checker** before running: `No overload of function sum matches arguments` |
| 2 | 3,849 / 748 | rewrote `sum(...)` as a loop — rejected again: `Unsupported += operation` |
| 3 | 4,937 / 1,074 | ran: all 6 domain calls in one snippet (`asyncio.gather` for brief+catalogue and 3 suppliers), filtering on type/ABV/stock, `itertools.combinations` for budget — but returned **100,614 chars** |
| 4 | 40,830 / 1,265 | small snippet to assemble the 4 chosen whiskies |
| 5 | 42,606 / 1,660 | final_result |

Total: 94,307 input tokens (demo 2: 19,178; tool calls: 9,095), 57 s, plan valid (€125.80).

What this shows:
- **The one-program idea worked mechanically**: snippet 3 did every lookup and the constraint
  filtering in code, in one round trip. The model wrote real coordination code, not a REPL session.
- **Monty type-checks before it runs.** The model built dicts mixing `str`, `float`, `int` and
  nested dicts, so `x['line_total_cents']` had a union type and `sum()` / `+=` failed the check.
  No tool was called by the rejected snippets (nested call count stayed at 6), but each rejection
  cost a model round trip. A strict sandbox language has a price for loosely typed LLM code.
- **"Compact summary" is up to the model.** It returned every valid 4-whisky combination: 715 at
  S1 and 715 at S3. That one result (~100 KB) then sat in the context for the last two requests,
  which is where the 94k tokens come from. Code Mode only saves tokens if the code *reduces* data.
- **Side finding about the scenario**: 13 whiskies are eligible at S1 and C(13,4) = 715, so *every*
  combination fits the €200 budget. The budget never binds; the real constraints are type, ABV and
  stock. A tighter budget (e.g. €140) would make the agent actually trade off price.
- Takeaway for the post: Code Mode changes *where* the work can happen, not *whether* the model
  does it efficiently. Results swing a lot with the model's coding choices and with prompts.

## Budget lowered from €200 to €120 (2026-11-15)

- Asked for "under €100" first: impossible with this data. One 70 cl bottle per whisky is
  needed (8 x 20 ml = 160 ml), and the four cheapest valid bottles at De Helm add up to €114.80.
  The brute-force solvability check answered that in a second — worth having.
- Budget options computed from the fixtures: €115 → 1 valid set, **€120 → 7**, €125 → 27,
  €130 → 77, €200 → 715 per full-range supplier (every combination fits). Picked €120.
- New tests: the default budget must actually limit the choice (2–10 valid sets at S1, none at
  S3), and a "nicer" flight with Glen Scotia + Laphroaig (€134.80) now fails on budget.
- Bug found while re-running: saved Monty snippets from a previous run stayed in `code/` when the
  new run had fewer snippets. `save_run` now clears old `snippet_*.py` first.

### Results at €120, one run each, gpt-6-luna

| | tool_calls | monty | monty_program (prompt variant) | monty_smol |
| --- | --- | --- | --- | --- |
| elapsed | 31.9 s | 40.1 s | 31.0 s | 52.0 s (+5.6 s VM setup) |
| model requests | 4 | 7 | 4 | 6 |
| input / output tokens | 8,816 / 2,614 | 29,557 / 2,935 | 18,667 / 3,000 | 44,766 / 4,944 |
| top-level calls | 10 domain + final | 6 `run_code` + final | 3 `run_code` + final | 3 `run_code`, `write_file`, `run_command`, final |
| plan | €119.80 | €119.80 | €119.80 | €119.80 |

- All four runs landed on €119.80, the most expensive of the 7 valid sets — four different
  flights at the same price (sweet, sweet, then two smoky ones; or three sweet + one smoky).
- The rejection reasons became much more interesting: "substituting Aberlour for Singleton
  would raise the total to €122.80, €2.80 over budget"; "Cask Corner: the same four cost
  €131.30". The agent is now visibly trading off price.
- Plain tool calling batched aggressively: four `search_whiskies(style=...)` calls in one turn,
  then details + three supplier lookups in parallel in the next. 4 requests, fewest tokens.
- Monty (demo 2) went REPL-style again, now 6 snippets → 7 requests, 3.4x the input tokens.
- The one-program variant: first program rejected by the type checker
  (`Unknown key "whiskies" for TypedDict Supplier`, it guessed the shape of a supplier record),
  then one program returned a 9 KB filtered summary per supplier. 4 requests, 18.7k tokens:
  better than plain Monty, still worse than tool calls on this small task.
- Note the type checker cuts both ways: it catches wrong guesses about data shapes *before* any
  tool runs (good), but each rejection costs a model round trip.
