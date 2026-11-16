import pytest

from whisky_sandbox_demo.season.catalogue import load_catalogue
from whisky_sandbox_demo.season.validation import validate_season

from .reference import cheapest_season, plan_from_picks


@pytest.fixture
def plan():
    _, picks = cheapest_season()
    return plan_from_picks(picks)


def failed(plan):
    return {c.name for c in validate_season(plan).failed}


def _evening(plan, theme):
    return next(e for e in plan.evenings if e.theme == theme)


def test_reference_plan_passes(plan):
    assert validate_season(plan).valid


def test_repeat_across_evenings(plan):
    a, b = plan.evenings[0], plan.evenings[1]
    b.whiskies[0] = a.whiskies[0].model_copy()
    assert any(name.endswith("not repeated") for name in failed(plan))


def test_wrong_theme(plan):
    islay = _evening(plan, "islay")
    speyside = _evening(plan, "speyside")
    islay.supplier_id, islay.whiskies = speyside.supplier_id, speyside.whiskies
    speyside.whiskies = []
    assert any(n.startswith("islay:") and n.endswith(" theme") for n in failed(plan))


def test_ineligible_product(plan):
    cat = load_catalogue()
    blend = next(p for p in cat.products.values() if p.single_malt is False)
    w = plan.evenings[0].whiskies[0]
    w.product_id, w.name = blend.id, blend.name
    assert any(n.endswith(" eligible") for n in failed(plan))


def test_shipping_and_totals(plan):
    order = plan.orders[0]
    order.shipping_cents += 500
    plan.season_total_cents -= 1
    names = failed(plan)
    assert f"order {order.supplier_id}" in names and "season_total" in names


def test_over_budget(plan):
    from whisky_sandbox_demo.season.catalogue import SeasonRequirements

    report = validate_season(plan, req=SeasonRequirements(budget_cents=10_000))
    assert "budget" in {c.name for c in report.failed}


def test_missing_order(plan):
    plan.orders = plan.orders[1:]
    assert "orders" in failed(plan)
