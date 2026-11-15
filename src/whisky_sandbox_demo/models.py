"""Typed data shared by every demo: fixture records, tool results and the agent's output.

All money is in integer euro cents, all volumes in millilitres and stock in whole bottles.
Every model is plain JSON-serialisable, which Code Mode needs: tool results cross into the
Monty sandbox in their JSON shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

WhiskyType = Literal["single_malt", "blended_malt", "blend"]
Style = Literal["sweet", "fruity", "rich", "coastal", "smoky"]


# --- Fixture records -------------------------------------------------------------------------


class FlavourProfile(BaseModel):
    """Illustrative 0-10 scores chosen by the demo author, not measurements."""

    sweetness: int = Field(ge=0, le=10)
    fruitiness: int = Field(ge=0, le=10)
    smokiness: int = Field(ge=0, le=10)
    intensity: int = Field(ge=0, le=10)


class Whisky(BaseModel):
    id: str
    name: str
    distillery: str
    country: str
    region: str | None
    type: WhiskyType
    abv: float
    bottle_ml: int
    style: Style
    tasting_notes: str
    flavour: FlavourProfile


class Offer(BaseModel):
    whisky_id: str
    price_cents: int
    stock_bottles: int
    source_url: str | None = None


class Supplier(BaseModel):
    id: str
    name: str
    fictional: bool
    website: str | None
    notes: str
    offers: list[Offer]


# --- Tool results ----------------------------------------------------------------------------


class SupplierSummary(BaseModel):
    id: str
    name: str
    fictional: bool
    notes: str


class TastingBrief(BaseModel):
    participants: int
    pour_ml: int
    whisky_count: int
    budget_cents: int
    max_abv: float
    required_type: WhiskyType
    progression: str
    single_supplier: bool
    suppliers: list[SupplierSummary]
    available_styles: list[Style]
    rules: list[str]
    data_note: str


class WhiskySummary(BaseModel):
    id: str
    name: str
    type: WhiskyType
    abv: float
    bottle_ml: int
    style: Style
    region: str | None


class WhiskyDetailsResult(BaseModel):
    whiskies: list[Whisky]
    unknown_ids: list[str]


class SupplierOffer(BaseModel):
    whisky_id: str
    whisky_name: str
    price_cents: int
    stock_bottles: int
    in_stock: bool


class SupplierOffersResult(BaseModel):
    supplier_id: str
    supplier_name: str
    offers: list[SupplierOffer]
    not_carried_ids: list[str]
    """Whisky ids that exist but this supplier does not sell, or ids that do not exist at all."""


# --- Agent output ----------------------------------------------------------------------------


class PlannedWhisky(BaseModel):
    position: int = Field(description="1-based tasting order; 1 is poured first.")
    label: str = Field(description="Blind label shown to tasters: 'A', 'B', 'C', 'D'.")
    whisky_id: str
    name: str
    distillery: str
    type: WhiskyType
    abv: float
    bottle_ml: int
    bottles: int
    unit_price_cents: int
    line_total_cents: int
    required_ml: int = Field(description="participants * pour_ml")
    available_ml: int = Field(description="bottles * bottle_ml")
    tasting_role: str = Field(description="Why this whisky sits at this point in the flight.")


class RejectedAlternative(BaseModel):
    subject_id: str = Field(description="Whisky id (Wxx) or supplier id (Sx) that was rejected.")
    reason: str


class TastingPlan(BaseModel):
    supplier_id: str
    supplier_name: str
    participants: int
    pour_ml: int
    whiskies: list[PlannedWhisky]
    total_cost_cents: int
    selection_rationale: str
    ordering_rationale: str
    rejected_alternatives: list[RejectedAlternative]


class GeneratedFile(BaseModel):
    path: str = Field(description="Path inside the sandbox workspace, e.g. 'pack/cards.pdf'.")
    kind: Literal["cards_pdf", "answer_sheet_pdf", "shopping_list_csv", "flavour_chart_png"]
    description: str


class TastingPackResult(BaseModel):
    plan: TastingPlan
    files: list[GeneratedFile]
