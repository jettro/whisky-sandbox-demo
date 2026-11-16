"""Scenario 2 tools, shaped like the shop's real Store API: a paginated listing without
ABV or bottle size, and batched product details by id. No filters the real listing lacks."""

from __future__ import annotations

from whisky_sandbox_demo.season.catalogue import (
    DEFAULT_SEASON,
    THEME_RULES,
    load_catalogue,
)
from whisky_sandbox_demo.season.models import (
    THEMES,
    ProductDetails,
    ProductDetailsResult,
    ProductListing,
    ProductPage,
    SeasonBrief,
    SupplierInfo,
    ThemeRule,
)

PAGE_SIZE = 50
MAX_DETAIL_IDS = 25


def get_season_brief() -> SeasonBrief:
    """Return the season requirements, rules, budget, suppliers (ids, shipping) and API limits."""
    cat = load_catalogue()
    req = DEFAULT_SEASON
    return SeasonBrief(
        members=req.members,
        pour_ml=req.pour_ml,
        whiskies_per_evening=req.whiskies_per_evening,
        evenings=[ThemeRule(theme=t, rule=THEME_RULES[t]) for t in THEMES],
        max_abv=req.max_abv,
        budget_cents=req.budget_cents,
        suppliers=[
            SupplierInfo(
                id=s.id,
                name=s.name,
                fictional=s.fictional,
                notes=s.notes,
                shipping=s.shipping,
                product_count=len(s.offers),
            )
            for s in cat.suppliers.values()
        ],
        page_size=PAGE_SIZE,
        max_detail_ids=MAX_DETAIL_IDS,
        rules=[
            "Money is integer euro cents; stock is whole bottles.",
            "Only whiskies with single_malt == true, a known abv <= max_abv, and not a gift set.",
            "Bottles per whisky = ceil(members * pour_ml / bottle_ml).",
            "No product may appear in more than one evening.",
            "Each evening is bought from one supplier with enough stock.",
            "All evenings bought from the same supplier form one order; shipping is charged once "
            "per order: fee_cents, unless the order subtotal >= free_from_cents (0 = always free).",
            "Season total = sum of order subtotals + shipping, and must be <= budget_cents.",
        ],
        data_note=(
            f"Snapshot of Slijterij De Helm (S1) from {cat.snapshot_date}; ABV and flags parsed "
            "from shop text (null when unclear). S2, S3 and all shipping rules are fictional."
        ),
    )


def list_products(supplier_id: str, page: int = 1) -> ProductPage:
    """List one page of a supplier's whisky catalogue (PAGE_SIZE per page, pages start at 1).

    Listings have no ABV, bottle size or single-malt flag: use get_products for those.
    """
    cat = load_catalogue()
    supplier = cat.suppliers.get(supplier_id)
    if supplier is None:
        raise ValueError(f"Unknown supplier_id {supplier_id!r}. Known: {', '.join(cat.suppliers)}.")
    total = len(supplier.offers)
    total_pages = max(1, -(-total // PAGE_SIZE))
    if page < 1 or page > total_pages:
        raise ValueError(f"page must be between 1 and {total_pages}")
    chunk = supplier.offers[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    products = []
    for offer in chunk:
        p = cat.products[offer.id]
        products.append(
            ProductListing(
                id=p.id,
                name=p.name,
                price_cents=offer.price_cents,
                stock_bottles=offer.stock_bottles,
                categories=p.categories,
                region=p.region,
                country=p.country,
                flavour_labels=p.flavour_labels,
            )
        )
    return ProductPage(
        supplier_id=supplier_id,
        page=page,
        total_pages=total_pages,
        total_products=total,
        products=products,
    )


def get_products(supplier_id: str, ids: list[str]) -> ProductDetailsResult:
    """Full facts for up to MAX_DETAIL_IDS products at one supplier: ABV, bottle size, flags."""
    cat = load_catalogue()
    if supplier_id not in cat.suppliers:
        raise ValueError(f"Unknown supplier_id {supplier_id!r}. Known: {', '.join(cat.suppliers)}.")
    if len(ids) > MAX_DETAIL_IDS:
        raise ValueError(f"At most {MAX_DETAIL_IDS} ids per call; got {len(ids)}.")
    found, missing = [], []
    for product_id in ids:
        offer = cat.offer(supplier_id, product_id)
        if offer is None:
            missing.append(product_id)
            continue
        p = cat.products[product_id]
        found.append(
            ProductDetails(
                id=p.id,
                name=p.name,
                price_cents=offer.price_cents,
                stock_bottles=offer.stock_bottles,
                categories=p.categories,
                region=p.region,
                country=p.country,
                flavour_labels=p.flavour_labels,
                abv=p.abv,
                bottle_ml=p.bottle_ml,
                bottle_ml_stated=p.bottle_ml_stated,
                single_malt=p.single_malt,
                sherry_cask=p.sherry_cask,
                gift_set=p.gift_set,
            )
        )
    return ProductDetailsResult(supplier_id=supplier_id, products=found, not_found_ids=missing)


SEASON_TOOLS = (get_season_brief, list_products, get_products)
SEASON_TOOL_NAMES = [t.__name__ for t in SEASON_TOOLS]
