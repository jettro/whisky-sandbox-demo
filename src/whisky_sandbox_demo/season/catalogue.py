"""Load the season snapshot and answer catalogue questions."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

from whisky_sandbox_demo.season.models import THEMES, Product, SeasonSupplier, Theme


@dataclass(frozen=True)
class SeasonRequirements:
    members: int = 30
    pour_ml: int = 20
    whiskies_per_evening: int = 4
    max_abv: float = 50.0
    budget_cents: int = 54_000

    @property
    def required_ml(self) -> int:
        return self.members * self.pour_ml


# Calibrated in tests/season/test_feasibility.py: cheapest season found ~€488.70, +10%.
DEFAULT_SEASON = SeasonRequirements(budget_cents=54_000)

THEME_RULES: dict[Theme, str] = {
    "speyside": "region is 'Speyside'",
    "islay": "region is 'Islay'",
    "sherry_cask": "sherry_cask is true (sherry, oloroso, PX ... cask)",
    "world": "country is known and not 'Scotland'",
}


@dataclass(frozen=True)
class Catalogue:
    snapshot_date: str
    source_note: str
    products: dict[str, Product]
    suppliers: dict[str, SeasonSupplier]

    def offer(self, supplier_id: str, product_id: str):
        supplier = self.suppliers.get(supplier_id)
        if supplier is None:
            return None
        return next((o for o in supplier.offers if o.id == product_id), None)


@cache
def load_catalogue() -> Catalogue:
    doc = json.loads(
        files("whisky_sandbox_demo.data").joinpath("season_catalogue.json").read_text("utf-8")
    )
    products = [Product.model_validate(p) for p in doc["products"]]
    suppliers = [SeasonSupplier.model_validate(s) for s in doc["suppliers"]]
    return Catalogue(
        snapshot_date=doc["snapshot_date"],
        source_note=doc["source"],
        products={p.id: p for p in products},
        suppliers={s.id: s for s in suppliers},
    )


def matches_theme(product: Product, theme: Theme) -> bool:
    if theme == "speyside":
        return product.region == "Speyside"
    if theme == "islay":
        return product.region == "Islay"
    if theme == "sherry_cask":
        return product.sherry_cask
    return product.country is not None and product.country != "Scotland"


def is_eligible(product: Product, req: SeasonRequirements = DEFAULT_SEASON) -> bool:
    """Season-wide rules, independent of theme and supplier."""
    return (
        product.single_malt is True
        and product.abv is not None
        and product.abv <= req.max_abv
        and not product.gift_set
    )


def bottles_for(product: Product, req: SeasonRequirements = DEFAULT_SEASON) -> int:
    return math.ceil(req.required_ml / product.bottle_ml)


def shipping_cents(supplier: SeasonSupplier, subtotal_cents: int) -> int:
    if subtotal_cents <= 0:
        return 0
    free = supplier.shipping.free_from_cents
    return 0 if free and subtotal_cents >= free else supplier.shipping.fee_cents


__all__ = ["THEMES", "THEME_RULES"]
