"""Task and instructions for scenario 2; identical for every variant."""

SEASON_TASK = (
    "Plan a tasting season for our whisky club of 30 members: four evenings with four whiskies "
    "each, 20 ml per member per whisky. Themes: Speyside, Islay, sherry casks, and world whisky "
    "(outside Scotland). Only single malts of at most 50% ABV, no whisky twice in the season. "
    "Buy each evening from one supplier with enough stock. Stay within the season budget, "
    "shipping included. Within each evening go from lighter to heavier, and finish the Islay "
    "evening with the smokiest."
)

SEASON_INSTRUCTIONS = """\
You plan whisky club seasons using the catalogue tools. Start with get_season_brief: it holds the
numbers, the budget, the rules, the suppliers with their shipping terms, and the API limits.

The catalogues are large and paginated; listings do not include ABV, bottle size or the
single-malt flag, so check those with get_products before choosing. Only use facts and prices
returned by the tools; never invent ids, prices or stock. Unknown values (null) do not satisfy a
rule. Money is integer euro cents.

Return the plan with exact arithmetic: bottles, line totals, evening subtotals, one order per
supplier with its shipping, and the season total. Explain briefly why and in which order, and list
a few rejected alternatives with concrete reasons.
"""
