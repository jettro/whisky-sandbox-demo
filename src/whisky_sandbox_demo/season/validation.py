"""Check a SeasonPlan against the snapshot, independent of what the agent claimed."""

from __future__ import annotations

from collections import defaultdict

from whisky_sandbox_demo.season.catalogue import (
    DEFAULT_SEASON,
    Catalogue,
    SeasonRequirements,
    bottles_for,
    is_eligible,
    load_catalogue,
    matches_theme,
    shipping_cents,
)
from whisky_sandbox_demo.season.models import THEMES, SeasonPlan
from whisky_sandbox_demo.validation import Check, ValidationReport

_SMOKY = "smoky_peaty"


def validate_season(
    plan: SeasonPlan,
    catalogue: Catalogue | None = None,
    req: SeasonRequirements = DEFAULT_SEASON,
) -> ValidationReport:
    cat = catalogue or load_catalogue()
    checks: list[Check] = []

    def check(name: str, passed: bool, detail: str, kind: str = "constraint") -> None:
        checks.append(Check(name=name, passed=passed, detail=detail, kind=kind))  # type: ignore[arg-type]

    check(
        "members_and_pour",
        plan.members == req.members and plan.pour_ml == req.pour_ml,
        f"{plan.members} members x {plan.pour_ml} ml",
    )
    themes = [e.theme for e in plan.evenings]
    check("themes", sorted(themes) == sorted(THEMES), f"themes: {themes}")

    seen: dict[str, str] = {}
    subtotal_by_supplier: dict[str, int] = defaultdict(int)
    for evening in plan.evenings:
        t = evening.theme
        supplier = cat.suppliers.get(evening.supplier_id)
        check(f"{t} supplier", supplier is not None, f"supplier {evening.supplier_id!r}")
        items = sorted(evening.whiskies, key=lambda w: w.position)
        check(
            f"{t} count",
            len(items) == req.whiskies_per_evening
            and len({w.product_id for w in items}) == len(items),
            f"{len(items)} whiskies, ids {[w.product_id for w in items]}",
        )
        evening_total = 0
        for w in items:
            tag = f"{t}:{w.product_id}"
            if w.product_id in seen:
                check(f"{tag} not repeated", False, f"also used on {seen[w.product_id]} evening")
            seen.setdefault(w.product_id, t)
            product = cat.products.get(w.product_id)
            if product is None:
                check(f"{tag} exists", False, "unknown product id")
                continue
            check(
                f"{tag} eligible",
                is_eligible(product, req),
                f"single_malt={product.single_malt} abv={product.abv} gift_set={product.gift_set}",
            )
            check(
                f"{tag} theme",
                matches_theme(product, t),
                f"region={product.region} "
                f"country={product.country} sherry_cask={product.sherry_cask}",
            )
            check(
                f"{tag} facts",
                w.name == product.name
                and w.abv == product.abv
                and w.bottle_ml == product.bottle_ml,
                "name/ABV/bottle size match the snapshot",
            )
            offer = cat.offer(evening.supplier_id, w.product_id)
            if offer is None:
                check(f"{tag} offered", False, f"not sold by {evening.supplier_id}")
                continue
            needed = bottles_for(product, req)
            check(
                f"{tag} price",
                w.unit_price_cents == offer.price_cents,
                f"{w.unit_price_cents} vs {offer.price_cents}",
            )
            check(f"{tag} bottles", w.bottles >= needed, f"{w.bottles} planned, {needed} needed")
            check(
                f"{tag} stock",
                offer.stock_bottles >= w.bottles,
                f"{w.bottles} wanted, {offer.stock_bottles} in stock",
            )
            line = w.bottles * offer.price_cents
            check(
                f"{tag} line_total", w.line_total_cents == line, f"{w.line_total_cents} vs {line}"
            )
            check(
                f"{tag} volume",
                w.required_ml == req.required_ml
                and w.available_ml == w.bottles * product.bottle_ml
                and w.available_ml >= w.required_ml,
                f"required {w.required_ml} ml, available {w.available_ml} ml",
            )
            evening_total += line
        check(
            f"{t} subtotal",
            evening.subtotal_cents == evening_total,
            f"{evening.subtotal_cents} vs {evening_total}",
        )
        subtotal_by_supplier[evening.supplier_id] += evening_total
        _smoky_last(t, items, cat, check)

    season_total = 0
    planned_orders = {o.supplier_id: o for o in plan.orders}
    check(
        "orders",
        set(planned_orders) == set(subtotal_by_supplier),
        f"orders for {sorted(planned_orders)}, used {sorted(subtotal_by_supplier)}",
    )
    for supplier_id, subtotal in subtotal_by_supplier.items():
        supplier = cat.suppliers.get(supplier_id)
        if supplier is None:
            continue
        ship = shipping_cents(supplier, subtotal)
        season_total += subtotal + ship
        order = planned_orders.get(supplier_id)
        if order is not None:
            check(
                f"order {supplier_id}",
                (order.subtotal_cents, order.shipping_cents, order.total_cents)
                == (subtotal, ship, subtotal + ship),
                f"planned {order.subtotal_cents}+{order.shipping_cents}={order.total_cents}, "
                f"expected {subtotal}+{ship}={subtotal + ship}",
            )
    check(
        "season_total",
        plan.season_total_cents == season_total,
        f"{plan.season_total_cents} vs {season_total}",
    )
    check("budget", season_total <= req.budget_cents, f"{season_total} of {req.budget_cents}")
    valid = all(c.passed for c in checks if c.kind == "constraint")
    return ValidationReport(valid=valid, checks=checks)


def _smoky_last(theme, items, cat: Catalogue, check) -> None:
    if theme != "islay" or not items:
        return
    last = cat.products.get(items[-1].product_id)
    smoky_any = [
        w.product_id
        for w in items
        if _SMOKY in getattr(cat.products.get(w.product_id), "flavour_labels", [])
    ]
    ok = last is not None and (not smoky_any or _SMOKY in last.flavour_labels)
    check("islay: smoky last", ok, f"smoky-labelled: {smoky_any}", "recommendation")
