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
