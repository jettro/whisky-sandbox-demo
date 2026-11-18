"""A deterministic price calculator for scenario 2: the fix experiment for the hybrid mode.

In the hybrid runs the model fetched and filtered in code, but still wrote the order totals
itself and once charged shipping that should have been free. `price_season` moves that last
arithmetic into a tool: the model passes its selection, the tool returns every number the plan
needs. It does not judge eligibility, themes or tasting order; choosing stays with the model.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

from whisky_sandbox_demo.season.catalogue import (
    DEFAULT_SEASON,
    bottles_for,
    load_catalogue,
    shipping_cents,
)
from whisky_sandbox_demo.season.models import SupplierOrder, Theme


class EveningSelection(BaseModel):
    theme: Theme
    supplier_id: str
    product_ids: list[str] = Field(description="In pouring order, lightest first.")


class QuotedLine(BaseModel):
    position: int
    product_id: str
    name: str
    abv: float | None
    bottle_ml: int
    bottles: int
    unit_price_cents: int
    line_total_cents: int
    required_ml: int
    available_ml: int
    stock_bottles: int


class QuotedEvening(BaseModel):
    theme: Theme
    supplier_id: str
    lines: list[QuotedLine]
    subtotal_cents: int


class SeasonQuote(BaseModel):
    evenings: list[QuotedEvening]
    orders: list[SupplierOrder]
    season_total_cents: int
    budget_cents: int
    within_budget: bool
    problems: list[str]
    """Products not sold by the supplier, too little stock, or a product used twice."""


def price_season(evenings: list[EveningSelection]) -> SeasonQuote:
    """Price a candidate season exactly: bottles, line totals, evening subtotals, one order per
    supplier with its shipping (free above the threshold), the season total and the budget check.

    Copy these numbers into the plan instead of computing them yourself. The quote does not check
    eligibility, themes or order; it lists problems it can see (not offered, stock, repeats).
    """
    cat = load_catalogue()
    req = DEFAULT_SEASON
    problems: list[str] = []
    seen: dict[str, str] = {}
    quoted: list[QuotedEvening] = []
    subtotal_by_supplier: dict[str, int] = defaultdict(int)

    for evening in evenings:
        if evening.supplier_id not in cat.suppliers:
            problems.append(f"{evening.theme}: unknown supplier {evening.supplier_id!r}")
            continue
        lines: list[QuotedLine] = []
        for position, product_id in enumerate(evening.product_ids, start=1):
            if product_id in seen:
                problems.append(f"{product_id} used on {seen[product_id]} and {evening.theme}")
            seen.setdefault(product_id, evening.theme)
            product = cat.products.get(product_id)
            offer = cat.offer(evening.supplier_id, product_id)
            if product is None or offer is None:
                problems.append(f"{evening.theme}: {product_id} not sold by {evening.supplier_id}")
                continue
            bottles = bottles_for(product, req)
            if offer.stock_bottles < bottles:
                problems.append(
                    f"{evening.theme}: {product_id} needs {bottles} bottles, "
                    f"{offer.stock_bottles} in stock"
                )
            lines.append(
                QuotedLine(
                    position=position,
                    product_id=product_id,
                    name=product.name,
                    abv=product.abv,
                    bottle_ml=product.bottle_ml,
                    bottles=bottles,
                    unit_price_cents=offer.price_cents,
                    line_total_cents=bottles * offer.price_cents,
                    required_ml=req.required_ml,
                    available_ml=bottles * product.bottle_ml,
                    stock_bottles=offer.stock_bottles,
                )
            )
        subtotal = sum(line.line_total_cents for line in lines)
        subtotal_by_supplier[evening.supplier_id] += subtotal
        quoted.append(
            QuotedEvening(
                theme=evening.theme,
                supplier_id=evening.supplier_id,
                lines=lines,
                subtotal_cents=subtotal,
            )
        )

    orders = []
    for supplier_id, subtotal in subtotal_by_supplier.items():
        ship = shipping_cents(cat.suppliers[supplier_id], subtotal)
        orders.append(
            SupplierOrder(
                supplier_id=supplier_id,
                subtotal_cents=subtotal,
                shipping_cents=ship,
                total_cents=subtotal + ship,
            )
        )
    total = sum(o.total_cents for o in orders)
    return SeasonQuote(
        evenings=quoted,
        orders=orders,
        season_total_cents=total,
        budget_cents=req.budget_cents,
        within_budget=total <= req.budget_cents,
        problems=problems,
    )
