"""A reference solver used only by the tests, never given to the agent.

It proves the scenario is feasible and finds a cheap valid season for budget calibration. It
tries every supplier per theme (3^4 assignments) and greedily takes the cheapest eligible,
unused whiskies, handling the scarcest theme first. Not guaranteed optimal; good enough as an
upper bound on the cheapest season.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import product as cartesian

from whisky_sandbox_demo.season.catalogue import (
    DEFAULT_SEASON,
    SeasonRequirements,
    bottles_for,
    is_eligible,
    load_catalogue,
    matches_theme,
    shipping_cents,
)
from whisky_sandbox_demo.season.models import (
    THEMES,
    Evening,
    SeasonPlan,
    SeasonWhisky,
    SupplierOrder,
)


def candidates(supplier_id: str, theme: str, req: SeasonRequirements = DEFAULT_SEASON):
    cat = load_catalogue()
    out = []
    for offer in cat.suppliers[supplier_id].offers:
        p = cat.products[offer.id]
        n = bottles_for(p, req)
        if is_eligible(p, req) and matches_theme(p, theme) and offer.stock_bottles >= n:
            out.append((n * offer.price_cents, p.id))
    return sorted(out)


def cheapest_season(req: SeasonRequirements = DEFAULT_SEASON):
    """Returns (total_cents, {theme: (supplier_id, [product ids])}) or None."""
    cat = load_catalogue()
    best = None
    for suppliers in cartesian(sorted(cat.suppliers), repeat=len(THEMES)):
        assign = dict(zip(THEMES, suppliers, strict=True))
        order = sorted(THEMES, key=lambda t: len(candidates(assign[t], t, req)))
        used: set[str] = set()
        picks, subtotals = {}, defaultdict(int)
        for t in order:
            chosen = [c for c in candidates(assign[t], t, req) if c[1] not in used]
            chosen = chosen[: req.whiskies_per_evening]
            if len(chosen) < req.whiskies_per_evening:
                break
            used.update(pid for _, pid in chosen)
            picks[t] = (assign[t], [pid for _, pid in chosen])
            subtotals[assign[t]] += sum(cost for cost, _ in chosen)
        else:
            total = sum(s + shipping_cents(cat.suppliers[k], s) for k, s in subtotals.items())
            if best is None or total < best[0]:
                best = (total, picks)
    return best


def plan_from_picks(picks, req: SeasonRequirements = DEFAULT_SEASON) -> SeasonPlan:
    cat = load_catalogue()
    evenings, subtotals = [], defaultdict(int)
    for theme, (supplier_id, ids) in picks.items():
        items = []
        for pos, pid in enumerate(ids, start=1):
            p, o = cat.products[pid], cat.offer(supplier_id, pid)
            n = bottles_for(p, req)
            items.append(
                SeasonWhisky(
                    position=pos,
                    product_id=pid,
                    name=p.name,
                    abv=p.abv,
                    bottle_ml=p.bottle_ml,
                    bottles=n,
                    unit_price_cents=o.price_cents,
                    line_total_cents=n * o.price_cents,
                    required_ml=req.required_ml,
                    available_ml=n * p.bottle_ml,
                )
            )
        sub = sum(i.line_total_cents for i in items)
        subtotals[supplier_id] += sub
        evenings.append(
            Evening(
                theme=theme,
                supplier_id=supplier_id,
                whiskies=items,
                subtotal_cents=sub,
                order_note="reference",
            )
        )
    orders = []
    for sid, sub in subtotals.items():
        ship = shipping_cents(cat.suppliers[sid], sub)
        orders.append(
            SupplierOrder(
                supplier_id=sid, subtotal_cents=sub, shipping_cents=ship, total_cents=sub + ship
            )
        )
    return SeasonPlan(
        members=req.members,
        pour_ml=req.pour_ml,
        evenings=evenings,
        orders=orders,
        season_total_cents=sum(o.total_cents for o in orders),
        rationale="reference",
        rejected_alternatives=[],
    )
