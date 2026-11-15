"""Brute force over the fixtures: the puzzle must have answers, and more than one."""

from itertools import combinations

from whisky_sandbox_demo.calculations import DEFAULT_REQUIREMENTS as REQ
from whisky_sandbox_demo.calculations import bottles_needed
from whisky_sandbox_demo.fixtures import load_fixtures


def valid_sets(supplier_id: str) -> list[tuple[str, ...]]:
    fx = load_fixtures()
    eligible = {}
    for offer in fx.suppliers[supplier_id].offers:
        w = fx.whiskies[offer.whisky_id]
        n = bottles_needed(REQ.participants, REQ.pour_ml, w.bottle_ml)
        if w.type == REQ.required_type and w.abv <= REQ.max_abv and offer.stock_bottles >= n:
            eligible[w.id] = n * offer.price_cents
    return [
        combo
        for combo in combinations(sorted(eligible), REQ.whisky_count)
        if sum(eligible[i] for i in combo) <= REQ.budget_cents
    ]


def test_at_least_one_valid_selection_exists():
    assert valid_sets("S1") or valid_sets("S3")


def test_multiple_valid_selections():
    assert len(valid_sets("S1")) + len(valid_sets("S3")) >= 2


def test_budget_actually_limits_the_choice():
    # Without the budget there are 715 combinations per full-range supplier; with it, a handful.
    assert 2 <= len(valid_sets("S1")) <= 10
    assert valid_sets("S3") == []  # the premium supplier is too expensive at this budget


def test_discount_supplier_cannot_fill_the_flight():
    assert valid_sets("S2") == []


def test_a_sweet_to_smoky_flight_exists_at_one_supplier():
    fx = load_fixtures()
    for combo in valid_sets("S1"):
        styles = {fx.whiskies[i].style for i in combo}
        if "sweet" in styles and "smoky" in styles:
            return
    raise AssertionError("no sweet-to-smoky option at S1")
