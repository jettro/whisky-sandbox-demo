# Plan: scenario 2, a whisky club season from the full shop catalogue

Goal: a second, honest scenario where Code Mode (Monty) *should* help, next to the existing
tasting scenario where it does not. The existing scenario stays unchanged as the small-task
baseline. Both get the same treatment: same model, same neutral instructions per variant pair,
same metrics, an independent validator.

Status: plan only, nothing implemented. Written 2026-11-16.

## 1. Why the current scenario can't show a Code Mode win

From the runs so far (gpt-6-luna and gpt-6.1-sol, €120 budget):

- 6 lookups, all batchable: plain tool calling already does them in 3 parallel rounds.
- ~20 KB of data in total: nothing to reduce, so returning raw results costs little.
- The hard part is taste judgement, which the model keeps doing itself.
- Code Mode adds a fixed ~1.2k input tokens per request (the `run_code` description and stubs).

Code Mode should pay off when (a) the number of calls depends on the data, (b) there is far more
raw data than the answer needs, (c) exact arithmetic or search matters, and (d) calls depend on
earlier results. Scenario 2 is designed around all four, using the real shape of the shop's API.

## 2. What the real data looks like (checked 2026-11-16)

Slijterij De Helm's public WooCommerce Store API, whisky category, €20–€80:

| Fact | Value |
| --- | --- |
| Products | 504 (500 with "op voorraad" stock) |
| Category labels | malt 387, blended 47, bourbon 25, gift sets, offers; "malt" also holds blended malts |
| Region attribute | missing for 153; Speyside 111, Highland 94, Islay 67, Lowlands 19, Campbeltown 18, Island 14+ |
| Country | Scotland 380, Ireland 37, USA 37, Netherlands 8, Japan 7, India 4, Belgium 4, ... |
| Shop flavour label | Fruitig & kruidig 218, Rijk & rond 112, Rokerig & peaty 86, Zacht & rond 23, ... |
| ABV | findable in name or description for ~423 of 504 (~84%) |
| Bottle size | stated for ~30; the rest assumed 70 cl; some 5 cl, 20 cl, 35 cl, 1 l, 5 l and gift sets |

The gaps are a feature: an agent has to cope with unknown ABV, unknown region, and category
labels that don't mean "single malt". Exactly the kind of filtering code is good at.

## 3. The scenario

> Plan a tasting season for a whisky club of 30 members: four evenings, four whiskies each,
> 20 ml per member per whisky. Themes: Speyside, Islay, sherry casks, and world whisky
> (outside Scotland). Only single malts of at most 50% ABV with a known ABV. No whisky may appear
> twice in the season. Each evening is bought from one supplier, who must have enough stock.
> The season budget, including shipping, is €X. Within each evening, go from lighter to
> heavier; finish the Islay evening with the smokiest.

- 30 × 20 ml = 600 ml per whisky: one 70 cl bottle, but two 50 cl bottles and twelve 5 cl
  miniatures, so bottle size matters for count and cost.
- Budget €X is calibrated after the snapshot (see §8) to be tight but feasible, the same way
  the €120 budget was chosen.

## 4. Data snapshot

`scripts/snapshot_de_helm.py` (run once on the host, polite: sequential pages, small delay):

- Fetches the whisky category from the Store API in the €20–€80 range.
- Stores **facts only**: id, name, permalink, price (cents), stock (parsed from "N op voorraad";
  0 for sold out or backorder-only), category labels, region, country, the shop's flavour label,
  ABV (parsed; `null` when not found), bottle size (parsed; `null` when unstated), and derived
  flags: `single_malt` (`true`/`false`/`null` from name/description keywords), `sherry_cask`
  (keywords: sherry, oloroso, PX, Pedro Ximénez), `gift_set`.
- No descriptions are stored. The parser's rules are tested; ambiguous records stay `null` rather
  than guessed.
- Output: `src/whisky_sandbox_demo/data/season_catalogue.json` with `snapshot_date` and source.
  Committed, so runs are reproducible and need no network.

Suppliers:
- `S1` De Helm: the real snapshot.
- `S2` and `S3`: fictional, as in scenario 1, each carrying a different subset (e.g. S2 strong on
  Islay and cheap, S3 strong on world whisky), prices derived from S1, own stock.
- **Shipping** (fictional for all three, clearly labelled): a flat fee per order with a
  free-shipping threshold. Buying an evening from a different supplier adds a shipping cost, so
  supplier choice per evening becomes a real optimisation.

## 5. Tools (shaped like the real API, the same for every variant)

| Tool | Real-API counterpart | Returns |
| --- | --- | --- |
| `get_season_brief()` | – | rules, themes, budget, supplier ids, shipping rules |
| `list_products(supplier_id, page, page_size=50)` | Store API listing (`per_page` max 100) | id, name, price, stock, category labels, region, country, flavour label, `total_pages` |
| `get_products(supplier_id, ids)` (max 25 ids) | Store API `include=` batch | full facts incl. ABV, bottle size, single-malt and sherry flags |

Fairness rules, to keep readers' trust:
- No artificial splitting: listing and batch details exist in the real API and are kept. Page
  size and batch limits are documented in the README with the reason.
- No filter parameters the real listing doesn't have (no "single malt" or "ABV" filter).
  Region filtering is also not offered, since 30% of records lack it.
- Same tools, same data, same instructions for tool calling and Monty. No "write one program"
  instruction in the controlled pair; the scale of the task must do that work.

Expected cost per full catalogue read: S1 is 11 pages of 50; details for shortlists are 25 ids per
call. Tool calling can request pages in parallel, but every page lands in the context
(~100 KB for the listing alone). Monty can loop, filter and return a shortlist.

## 6. Output and validation

`SeasonPlan`: four `Evening`s (theme, supplier, ordered whiskies with bottles, unit price, line
total, required/available ml), shipping per supplier order, season total, rationale, a few
rejected alternatives.

Independent validator (`season_validation.py`), constraint checks:
- Four evenings, one per theme; four distinct whiskies per evening; no repeats across the season.
- Every whisky: exists at the evening's supplier, `single_malt is True`, ABV known and ≤ 50%,
  theme rule holds (region Speyside / region Islay / `sherry_cask` / country ≠ Scotland).
- Bottles ≥ `ceil(600 ml / bottle_ml)`, stock ≥ bottles, prices and facts match the snapshot.
- Shipping charged correctly per supplier order; line, evening and season totals correct;
  season total ≤ budget.

Recommendations (reported, not pass/fail): light-to-heavy order using the shop's flavour label,
smokiest last on Islay night.

## 7. Variants and metrics

| Variant | Purpose |
| --- | --- |
| `season_tool_calls` | baseline |
| `season_monty` | same prompt, tools behind CodeMode |
| (optional) `season_monty_smol` | adds a printed season booklet in the VM, not comparable |

Metrics as today (requests, tokens, top-level vs nested calls, snippets, elapsed), plus:
- **Peak context size** (largest single-request input tokens) — the cost that grows with data.
- **Bytes returned into the context** per variant (sum of tool-return sizes).
- **Validity**: because correctness is where tool calling is expected to break on a big task,
  this scenario needs repeated runs. Add `--runs N` (default 1) that writes one folder per run
  and a `summary.json` with valid-rate and median/min/max metrics. `make season-compare RUNS=5`.

## 8. Feasibility and calibration (tests, offline)

- Parser tests on hand-picked tricky records (ABV in name vs description, "0,7 ltr", gift sets,
  blended malts in the "malt" category, backorder-only stock).
- A **reference solver in the tests only** (never exposed to the agent): picks a valid season
  greedily or with a small exact search per theme. Proves feasibility and gives the cheapest
  valid season cost `C_min`.
- Budget €X = `C_min` plus a small margin (e.g. +10%), chosen so that several valid seasons exist
  but naive "pick the favourites" choices exceed it. Documented in the README, as with €120.
- Tests assert: each theme has ≥ 6 eligible whiskies at some supplier, the budget binds, and
  at least two distinct valid seasons exist.

## 9. Code structure

```
src/whisky_sandbox_demo/
  season/
    models.py        catalogue records, tool results, SeasonPlan
    catalogue.py     load season_catalogue.json, supplier views, shipping rules
    tools.py         get_season_brief, list_products, get_products
    prompts.py       SEASON_TASK, SEASON_INSTRUCTIONS
    validation.py    validate_season
  demos/
    season_tool_calls.py
    season_monty.py
  data/season_catalogue.json
scripts/snapshot_de_helm.py
tests/season/  test_parser.py  test_tools.py  test_validation.py  test_feasibility.py
```

Reuses `config`, `metrics` (extended with peak context and returned bytes), `reporting` and the
demo runner. Makefile targets: `season-snapshot`, `season-tools`, `season-monty`,
`season-compare`.

## 10. Work order

1. Snapshot script + parser tests; commit the JSON. Review data quality by hand (spot-check ~20
   records against the shop pages).
2. Season models, catalogue, tools, tool tests.
3. Validator + reference solver + feasibility tests; calibrate the budget.
4. Demos and the `--runs N` comparison with summary.
5. Live runs (e.g. 5 per variant, one model), README section, blog notes.
6. Optional: Smol booklet variant.

## 11. Risks and open questions

- **Expected outcome is not guaranteed.** If tool calling copes well (large contexts are cheap
  for current models), report that honestly. The scenario is designed to be fair, not rigged.
- **Cost**: tool-calling runs may use 100k+ input tokens each; 5 runs × 2 variants × 2 models is
  noticeable. Start with one model.
- **Parsed facts can be wrong** (ABV from text). Mitigation: conservative parser, `null` when
  unsure, manual spot-check, and the README states facts are parsed from a snapshot.
- **Shop terms**: a single polite snapshot of public product facts, stored with source and date;
  no descriptions copied. Ask before re-fetching regularly.
- **Open**: should the world evening allow non-single-malts (e.g. Japanese blends)? Current plan
  keeps single malts only for one simple rule. Should a cask-strength evening be added to make
  the 50% rule bite? Probably not: Islay already has cask-strength traps.
