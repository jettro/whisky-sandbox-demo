from __future__ import annotations

import pytest

from whisky_sandbox_demo.calculations import DEFAULT_REQUIREMENTS, bottles_needed
from whisky_sandbox_demo.fixtures import load_fixtures
from whisky_sandbox_demo.models import PlannedWhisky, RejectedAlternative, TastingPlan


def make_plan(supplier_id: str, whisky_ids: list[str]) -> TastingPlan:
    """Build a plan exactly as a careful agent would, straight from the fixtures."""
    fx = load_fixtures()
    req = DEFAULT_REQUIREMENTS
    items = []
    for pos, wid in enumerate(whisky_ids, start=1):
        w = fx.whiskies[wid]
        offer = fx.offer(supplier_id, wid)
        price = offer.price_cents if offer else 0
        bottles = bottles_needed(req.participants, req.pour_ml, w.bottle_ml)
        items.append(
            PlannedWhisky(
                position=pos,
                label="ABCD"[pos - 1],
                whisky_id=wid,
                name=w.name,
                distillery=w.distillery,
                type=w.type,
                abv=w.abv,
                bottle_ml=w.bottle_ml,
                bottles=bottles,
                unit_price_cents=price,
                line_total_cents=bottles * price,
                required_ml=req.required_ml,
                available_ml=bottles * w.bottle_ml,
                tasting_role="test",
            )
        )
    return TastingPlan(
        supplier_id=supplier_id,
        supplier_name=fx.suppliers[supplier_id].name,
        participants=req.participants,
        pour_ml=req.pour_ml,
        whiskies=items,
        total_cost_cents=sum(i.line_total_cents for i in items),
        selection_rationale="test",
        ordering_rationale="test",
        rejected_alternatives=[RejectedAlternative(subject_id="W14", reason="58% ABV")],
    )


# Cheapest valid flight at De Helm: two sweet Speysiders, two smoky Islays, €114.80.
GOOD_SELECTION = ("S1", ["W01", "W02", "W10", "W11"])


@pytest.fixture
def good_plan() -> TastingPlan:
    return make_plan(*GOOD_SELECTION)
