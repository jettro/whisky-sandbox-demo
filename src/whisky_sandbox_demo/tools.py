"""The four domain tools. Plain functions, identical in every demo.

They only *look things up*. Filtering on ABV and type, comparing suppliers, computing totals
and choosing the order is the agent's job: with ordinary tool calls it reasons over the
results, in Code Mode it writes Python that does it.
"""

from __future__ import annotations

from typing import get_args

from whisky_sandbox_demo.calculations import DEFAULT_REQUIREMENTS, Requirements
from whisky_sandbox_demo.fixtures import load_fixtures
from whisky_sandbox_demo.models import (
    Style,
    SupplierOffer,
    SupplierOffersResult,
    SupplierSummary,
    TastingBrief,
    WhiskyDetailsResult,
    WhiskySummary,
)


def build_brief(req: Requirements = DEFAULT_REQUIREMENTS) -> TastingBrief:
    fx = load_fixtures()
    return TastingBrief(
        participants=req.participants,
        pour_ml=req.pour_ml,
        whisky_count=req.whisky_count,
        budget_cents=req.budget_cents,
        max_abv=req.max_abv,
        required_type=req.required_type,  # type: ignore[arg-type]
        progression="Start accessible and sweet, finish smoky.",
        single_supplier=True,
        suppliers=[
            SupplierSummary(id=s.id, name=s.name, fictional=s.fictional, notes=s.notes)
            for s in fx.suppliers.values()
        ],
        available_styles=list(get_args(Style)),
        rules=[
            "Money is in integer euro cents.",
            "Stock is a count of whole bottles.",
            "Bottles needed per whisky = ceil(participants * pour_ml / bottle_ml).",
            "Each whisky's ABV must be at most max_abv.",
            "All bottles come from one supplier, which must have enough stock.",
        ],
        data_note=(
            f"Whisky names, ABV and S1 prices/stock are a snapshot of a real shop taken on "
            f"{fx.snapshot_date}. Suppliers S2 and S3 are fictional. Flavour scores are "
            f"illustrative estimates."
        ),
    )


def get_tasting_brief() -> TastingBrief:
    """Return the tasting requirements, the rules, and the list of suppliers with their ids."""
    return build_brief()


def search_whiskies(style: Style | None = None) -> list[WhiskySummary]:
    """List whiskies in the catalogue, optionally only one style.

    Styles: 'sweet', 'fruity', 'rich', 'coastal', 'smoky'. Omit `style` to list everything.
    The list is not filtered on ABV, type or availability.
    """
    fx = load_fixtures()
    return [
        WhiskySummary(
            id=w.id,
            name=w.name,
            type=w.type,
            abv=w.abv,
            bottle_ml=w.bottle_ml,
            style=w.style,
            region=w.region,
        )
        for w in fx.whiskies.values()
        if style is None or w.style == style
    ]


def get_whisky_details(ids: list[str]) -> WhiskyDetailsResult:
    """Return full records (tasting notes, flavour scores 0-10) for several whiskies at once."""
    fx = load_fixtures()
    found = [fx.whiskies[i] for i in ids if i in fx.whiskies]
    unknown = [i for i in ids if i not in fx.whiskies]
    return WhiskyDetailsResult(whiskies=found, unknown_ids=unknown)


def get_supplier_offers(supplier_id: str, whisky_ids: list[str]) -> SupplierOffersResult:
    """Return one supplier's price (euro cents) and stock (bottles) for several whiskies.

    Whiskies the supplier does not sell are listed in `not_carried_ids`.
    """
    fx = load_fixtures()
    supplier = fx.suppliers.get(supplier_id)
    if supplier is None:
        known = ", ".join(fx.suppliers)
        raise ValueError(f"Unknown supplier_id {supplier_id!r}. Known suppliers: {known}.")
    offers: list[SupplierOffer] = []
    not_carried: list[str] = []
    for whisky_id in whisky_ids:
        offer = fx.offer(supplier_id, whisky_id)
        whisky = fx.whiskies.get(whisky_id)
        if offer is None or whisky is None:
            not_carried.append(whisky_id)
            continue
        offers.append(
            SupplierOffer(
                whisky_id=whisky_id,
                whisky_name=whisky.name,
                price_cents=offer.price_cents,
                stock_bottles=offer.stock_bottles,
                in_stock=offer.stock_bottles > 0,
            )
        )
    return SupplierOffersResult(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        offers=offers,
        not_carried_ids=not_carried,
    )


DOMAIN_TOOLS = (get_tasting_brief, search_whiskies, get_whisky_details, get_supplier_offers)
DOMAIN_TOOL_NAMES = [t.__name__ for t in DOMAIN_TOOLS]
