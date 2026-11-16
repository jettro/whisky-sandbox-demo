"""Typed data for scenario 2: catalogue records, tool results and the season plan."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Theme = Literal["speyside", "islay", "sherry_cask", "world"]
THEMES: tuple[Theme, ...] = ("speyside", "islay", "sherry_cask", "world")


# --- Catalogue (snapshot) -------------------------------------------------------------------


class Product(BaseModel):
    id: str
    name: str
    brand: str | None
    url: str
    price_cents: int
    stock_bottles: int
    categories: list[str]
    region: str | None
    country: str | None
    flavour_labels: list[str]
    abv: float | None
    bottle_ml: int
    bottle_ml_stated: bool
    single_malt: bool | None
    sherry_cask: bool
    gift_set: bool


class Shipping(BaseModel):
    fee_cents: int
    free_from_cents: int
    """Orders with a subtotal at or above this amount ship free (0: always free)."""


class SupplierOfferRecord(BaseModel):
    id: str
    price_cents: int
    stock_bottles: int


class SeasonSupplier(BaseModel):
    id: str
    name: str
    fictional: bool
    notes: str
    shipping: Shipping
    offers: list[SupplierOfferRecord]


# --- Tool results -----------------------------------------------------------------------------


class ThemeRule(BaseModel):
    theme: Theme
    rule: str


class SupplierInfo(BaseModel):
    id: str
    name: str
    fictional: bool
    notes: str
    shipping: Shipping
    product_count: int


class SeasonBrief(BaseModel):
    members: int
    pour_ml: int
    whiskies_per_evening: int
    evenings: list[ThemeRule]
    max_abv: float
    budget_cents: int
    suppliers: list[SupplierInfo]
    page_size: int
    max_detail_ids: int
    rules: list[str]
    data_note: str


class ProductListing(BaseModel):
    """What the shop's listing shows: no ABV, no bottle size, no single-malt flag."""

    id: str
    name: str
    price_cents: int
    stock_bottles: int
    categories: list[str]
    region: str | None
    country: str | None
    flavour_labels: list[str]


class ProductPage(BaseModel):
    supplier_id: str
    page: int
    total_pages: int
    total_products: int
    products: list[ProductListing]


class ProductDetails(ProductListing):
    abv: float | None = Field(description="None when the shop text does not state it clearly.")
    bottle_ml: int
    bottle_ml_stated: bool = Field(description="False: size not stated, standard 70 cl assumed.")
    single_malt: bool | None = Field(description="None when the shop text does not say.")
    sherry_cask: bool
    gift_set: bool


class ProductDetailsResult(BaseModel):
    supplier_id: str
    products: list[ProductDetails]
    not_found_ids: list[str]


# --- Agent output -----------------------------------------------------------------------------


class SeasonWhisky(BaseModel):
    position: int = Field(description="1-based pouring order within the evening.")
    product_id: str
    name: str
    abv: float
    bottle_ml: int
    bottles: int
    unit_price_cents: int
    line_total_cents: int
    required_ml: int
    available_ml: int


class Evening(BaseModel):
    theme: Theme
    supplier_id: str
    whiskies: list[SeasonWhisky]
    subtotal_cents: int
    order_note: str = Field(description="Why these whiskies, in this order.")


class SupplierOrder(BaseModel):
    supplier_id: str
    subtotal_cents: int
    shipping_cents: int
    total_cents: int


class SeasonRejection(BaseModel):
    subject_id: str = Field(description="Product id (Hxxx) or supplier id (Sx).")
    reason: str


class SeasonPlan(BaseModel):
    members: int
    pour_ml: int
    evenings: list[Evening]
    orders: list[SupplierOrder] = Field(description="One order per supplier used in the season.")
    season_total_cents: int
    rationale: str
    rejected_alternatives: list[SeasonRejection]
