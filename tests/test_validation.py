import pytest

from whisky_sandbox_demo.calculations import Requirements
from whisky_sandbox_demo.validation import validate_plan

from .conftest import make_plan


def failed_names(plan, **kwargs):
    return {c.name for c in validate_plan(plan, **kwargs).failed}


def test_good_plan_passes(good_plan):
    report = validate_plan(good_plan)
    assert report.valid, report.failed
    recs = [c for c in report.checks if c.kind == "recommendation"]
    assert recs and all(c.passed for c in recs)


def test_bad_order_is_only_a_recommendation():
    plan = make_plan("S1", ["W12", "W08", "W02", "W01"])  # smoky first
    report = validate_plan(plan)
    assert report.valid
    assert not all(c.passed for c in report.checks if c.kind == "recommendation")


@pytest.mark.parametrize(
    ("selection", "expected_failure"),
    [
        (("S1", ["W01", "W02", "W08", "W14"]), "D:W14 abv"),  # 58% cask strength
        (("S1", ["W18", "W02", "W08", "W12"]), "A:W18 type"),  # blended malt
        (("S1", ["W01", "W02", "W08", "W20"]), "D:W20 type"),  # blend
        (("S1", ["W01", "W02", "W08", "W16"]), "D:W16 stock"),  # sold out
        (("S2", ["W10", "W11", "W13", "W12"]), "D:W12 stock"),  # discount shop has none
        (("S2", ["W01", "W10", "W11", "W13"]), "A:W01 offered"),  # not carried
        (("S1", ["W01", "W01", "W08", "W12"]), "distinct"),
        (("S1", ["W01", "W02", "W12"]), "whisky_count"),
    ],
)
def test_constraint_violations(selection, expected_failure):
    assert expected_failure in failed_names(make_plan(*selection))


def test_exactly_50_percent_is_allowed():
    plan = make_plan("S1", ["W01", "W02", "W08", "W13"])
    assert validate_plan(plan).valid


def test_wrong_price_is_caught(good_plan):
    good_plan.whiskies[0].unit_price_cents -= 100
    assert "A:W01 price" in failed_names(good_plan)


def test_arithmetic_errors_are_caught(good_plan):
    good_plan.whiskies[1].line_total_cents += 1
    good_plan.total_cost_cents -= 500
    failed = failed_names(good_plan)
    assert {"B:W02 line_total", "total"} <= failed


def test_wrong_product_facts_are_caught(good_plan):
    good_plan.whiskies[3].abv = 46.0
    assert "D:W12 facts" in failed_names(good_plan)


def test_mixed_supplier_prices_are_caught(good_plan):
    # Claims De Helm but uses the cheaper (fictional) S2 price for the Laphroaig.
    good_plan.whiskies[3].unit_price_cents = 3495
    good_plan.whiskies[3].line_total_cents = 3495
    assert "D:W12 price" in failed_names(good_plan)


def test_over_budget():
    plan = make_plan("S1", ["W01", "W02", "W08", "W12"])
    assert "budget" in failed_names(plan, req=Requirements(budget_cents=10_000))


def test_larger_group_needs_more_bottles_and_stock():
    req = Requirements(participants=40)
    plan = make_plan("S1", ["W01", "W02", "W08", "W12"])
    for item in plan.whiskies:
        item.required_ml = req.required_ml
    failed = failed_names(plan, req=req)
    assert "A:W01 bottles" in failed and "participants_and_pour" in failed
