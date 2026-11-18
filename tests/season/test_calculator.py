from whisky_sandbox_demo.season.calculator import EveningSelection, price_season

from .reference import cheapest_season, plan_from_picks


def _selection(plan):
    return [
        EveningSelection(
            theme=e.theme,
            supplier_id=e.supplier_id,
            product_ids=[w.product_id for w in sorted(e.whiskies, key=lambda w: w.position)],
        )
        for e in plan.evenings
    ]


def test_quote_matches_the_validated_reference_plan():
    _, picks = cheapest_season()
    plan = plan_from_picks(picks)
    quote = price_season(_selection(plan))
    assert quote.problems == []
    assert quote.season_total_cents == plan.season_total_cents
    assert {(o.supplier_id, o.shipping_cents, o.total_cents) for o in quote.orders} == {
        (o.supplier_id, o.shipping_cents, o.total_cents) for o in plan.orders
    }
    assert quote.within_budget


def test_quote_reports_repeats_and_unknown_products():
    _, picks = cheapest_season()
    selection = _selection(plan_from_picks(picks))
    selection[1].product_ids[0] = selection[0].product_ids[0]
    selection[2].product_ids[0] = "NOPE"
    problems = " | ".join(price_season(selection).problems)
    assert "used on" in problems
    assert "NOPE not sold" in problems
