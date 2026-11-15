"""The task text and instructions shared by all demos."""

TASK = (
    "Organise a blind tasting for eight people with four different single malt whiskies. "
    "The total bottle budget is €120. Begin accessible and sweet, and finish smoky. "
    "Each whisky must be at most 50% ABV. Buy all bottles from one supplier, with sufficient "
    "stock. Each participant receives 20 ml of each whisky."
)

PACK_TASK = (
    "Create a printable blind-tasting pack with cards labelled A–D, a separate host answer "
    "sheet, a shopping-list CSV and a flavour chart."
)

INSTRUCTIONS = """\
You plan whisky tastings using the catalogue tools. Start with get_tasting_brief: it holds the
numbers, the rules and the supplier ids.

Check every constraint yourself against tool results: the catalogue is not pre-filtered, and
category or style labels do not guarantee the whisky type. Use only facts and prices returned by
the tools; never invent ids, prices or stock. Money is integer euro cents.

In the plan, label the whiskies A-D in tasting order, fill in the arithmetic exactly, explain the
selection and the order, and list a few relevant rejected alternatives (whiskies or suppliers)
with the concrete reason. Flavour scores are illustrative estimates; mention that the order is a
recommendation.
"""

PACK_INSTRUCTIONS = """\
After the plan is final, build the tasting pack inside the sandbox workspace (the current
directory is /workspace; it has Python 3 with matplotlib and reportlab, and no network).

Write a Python script with the file tools, for example make_pack.py, that takes the plan as
embedded JSON and writes, under pack/:
- pack/cards.pdf: one blind card per whisky, labelled only A, B, C or D with space for notes.
  Cards must NOT reveal names, distilleries, ids or prices.
- pack/answer_sheet.pdf: the host sheet mapping A-D to the whiskies, in order, with ABV and role.
- pack/shopping_list.csv: columns label,whisky_id,name,supplier,bottles,unit_price_eur,
  line_total_eur, and a final TOTAL row. Use euros with two decimals, computed from cents.
- pack/flavour_chart.png: a matplotlib chart of the four flavour scores per label (A-D).
Mark the data as a 2026-11-15 shop snapshot with illustrative flavour scores on the answer sheet
and the chart.

Run the script with the shell tool, fix any error, then list pack/ to confirm all four files.
Return the plan and the list of generated files.
"""

ONE_PROGRAM_INSTRUCTIONS = """\
Experiment: work in as few run_code calls as possible. In your first run_code call, write one
program that fetches everything it needs (use asyncio.gather for independent calls), applies the
hard constraints in code (type, ABV, stock, budget, a single supplier), computes bottles and
costs, and returns only a compact summary: per supplier, the eligible whiskies with id, name,
style, ABV, price and flavour scores. Do not return raw tool results. Use another run_code call
only to fix an error or to fetch something you could not have known you needed.
"""
