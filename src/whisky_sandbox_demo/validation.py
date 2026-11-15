"""Check a TastingPlan against the fixture data, independent of what the agent claimed.

Constraints are objective and decide `valid`. The flavour progression is a recommendation:
it is reported, but a plan with an odd order is still a valid shopping plan.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from whisky_sandbox_demo.calculations import DEFAULT_REQUIREMENTS, Requirements, bottles_needed
from whisky_sandbox_demo.fixtures import Fixtures, load_fixtures
from whisky_sandbox_demo.models import TastingPlan


class Check(BaseModel):
    name: str
    passed: bool
    detail: str
    kind: Literal["constraint", "recommendation"] = "constraint"


class ValidationReport(BaseModel):
    valid: bool
    checks: list[Check]

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.kind == "constraint" and not c.passed]


def validate_plan(
    plan: TastingPlan,
    fixtures: Fixtures | None = None,
    req: Requirements = DEFAULT_REQUIREMENTS,
) -> ValidationReport:
    fx = fixtures or load_fixtures()
    checks: list[Check] = []

    def check(name: str, passed: bool, detail: str, kind: str = "constraint") -> None:
        checks.append(Check(name=name, passed=passed, detail=detail, kind=kind))  # type: ignore[arg-type]

    items = sorted(plan.whiskies, key=lambda w: w.position)
    ids = [w.whisky_id for w in items]

    check("whisky_count", len(items) == req.whisky_count, f"{len(items)} whiskies planned")
    check("distinct", len(set(ids)) == len(ids), f"ids: {ids}")
    check(
        "positions",
        [w.position for w in items] == list(range(1, len(items) + 1)),
        f"positions: {[w.position for w in items]}",
    )
    check(
        "participants_and_pour",
        plan.participants == req.participants and plan.pour_ml == req.pour_ml,
        f"{plan.participants} people x {plan.pour_ml} ml",
    )

    supplier = fx.suppliers.get(plan.supplier_id)
    check("supplier_exists", supplier is not None, f"supplier_id {plan.supplier_id!r}")
    if supplier is not None:
        check(
            "supplier_name",
            plan.supplier_name == supplier.name,
            f"{plan.supplier_name!r} vs {supplier.name!r}",
        )

    computed_total = 0
    for item in items:
        tag = f"{item.label or item.position}:{item.whisky_id}"
        whisky = fx.whiskies.get(item.whisky_id)
        if whisky is None:
            check(f"{tag} exists", False, "unknown whisky id")
            continue
        facts_match = (
            item.name == whisky.name
            and item.distillery == whisky.distillery
            and item.type == whisky.type
            and item.abv == whisky.abv
            and item.bottle_ml == whisky.bottle_ml
        )
        check(f"{tag} facts", facts_match, "name/distillery/type/ABV/bottle size match fixtures")
        check(f"{tag} type", whisky.type == req.required_type, f"type is {whisky.type}")
        check(f"{tag} abv", whisky.abv <= req.max_abv, f"{whisky.abv}% (max {req.max_abv}%)")

        offer = fx.offer(plan.supplier_id, item.whisky_id)
        if offer is None:
            check(f"{tag} offered", False, f"not sold by {plan.supplier_id}")
            continue
        needed = bottles_needed(req.participants, req.pour_ml, whisky.bottle_ml)
        check(
            f"{tag} price",
            item.unit_price_cents == offer.price_cents,
            f"{item.unit_price_cents} vs {offer.price_cents} cents",
        )
        check(f"{tag} bottles", item.bottles >= needed, f"{item.bottles} planned, {needed} needed")
        check(
            f"{tag} stock",
            offer.stock_bottles >= item.bottles,
            f"{item.bottles} wanted, {offer.stock_bottles} in stock",
        )
        line_total = item.bottles * offer.price_cents
        check(
            f"{tag} line_total",
            item.line_total_cents == line_total,
            f"{item.line_total_cents} vs {line_total}",
        )
        check(
            f"{tag} volume",
            item.required_ml == req.required_ml
            and item.available_ml == item.bottles * whisky.bottle_ml
            and item.available_ml >= item.required_ml,
            f"required {item.required_ml} ml, available {item.available_ml} ml",
        )
        computed_total += line_total

    check(
        "total",
        plan.total_cost_cents == computed_total,
        f"{plan.total_cost_cents} vs {computed_total}",
    )
    check(
        "budget",
        computed_total <= req.budget_cents,
        f"{computed_total} of {req.budget_cents} cents",
    )

    _progression(items, fx, check)

    valid = all(c.passed for c in checks if c.kind == "constraint")
    return ValidationReport(valid=valid, checks=checks)


def _progression(items, fx: Fixtures, check) -> None:
    profiles = [fx.whiskies[i.whisky_id].flavour for i in items if i.whisky_id in fx.whiskies]
    if len(profiles) < 2:
        return
    smoke = [p.smokiness for p in profiles]
    sweet = [p.sweetness for p in profiles]
    check(
        "progression: smokiest last",
        smoke[-1] == max(smoke),
        f"smokiness in order: {smoke}",
        "recommendation",
    )
    check(
        "progression: sweet first",
        sweet[0] >= sweet[-1],
        f"sweetness in order: {sweet}",
        "recommendation",
    )
