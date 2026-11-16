"""Turn one WooCommerce Store API product into a fact record.

Only facts are kept (name, price, stock, ABV, size, region, ...). Descriptions are read to find
facts but never stored. When a fact is unclear the parser returns None instead of guessing.
"""

from __future__ import annotations

import html
import re
from typing import Any

COUNTRIES = {
    "Schotland": "Scotland",
    "Ierland": "Ireland",
    "Amerika": "USA",
    "Nederland": "Netherlands",
    "Japan": "Japan",
    "India": "India",
    "België": "Belgium",
    "Verenigd Koninkrijk": "United Kingdom",
    "Engeland": "England",
    "Frankrijk": "France",
    "Canada": "Canada",
    "Wales": "Wales",
    "Duitsland": "Germany",
    "Taiwan": "Taiwan",
    "Zweden": "Sweden",
    "Australië": "Australia",
    "Denemarken": "Denmark",
    "Zwitserland": "Switzerland",
    "Israël": "Israel",
    "Zuid-Afrika": "South Africa",
}

FLAVOURS = {
    "Fruitig & kruidig": "fruity_spicy",
    "Rijk & rond": "rich_round",
    "Rokerig & peaty": "smoky_peaty",
    "Zacht & Rond": "soft_round",
    "Zacht & rond": "soft_round",
    "Geurig & bloemig": "fragrant_floral",
    "Moutig & droog": "malty_dry",
}

SHERRY_WORDS = re.compile(
    r"\b(sherry|oloroso|pedro xim[eé]nez|px|amontillado|manzanilla|fino cask)\b", re.I
)
SINGLE_MALT = re.compile(r"\bsingle\s+(?:\w+\s+)?malts?\b", re.I)
NOT_SINGLE_MALT = re.compile(r"\b(blended|blend|grain whisk|bourbon|rye|pot still)\b", re.I)
GIFT = re.compile(r"\b(gift\s?set|giftpack|gifset|geschenk|tripack|\d+\s?x\s?\d+\s?cl)\b", re.I)

_ABV_NAME = re.compile(r"(\d{2}(?:[.,]\d{1,2})?)\s?%")
_ABV_TEXT = re.compile(
    r"(?:\b(?:heeft|bevat|op|van|is|met|een)\s+(?:een\s+)?(?:alcoholpercentage\s+van\s+)?)"
    r"(\d{2}(?:[.,]\d{1,2})?)\s?%"
    r"|(\d{2}(?:[.,]\d{1,2})?)\s?%\s*(?:alc|vol|abv)",
    re.I,
)
_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s?(cl|ml|ltr|liter|l)\b", re.I)
_STOCK = re.compile(r"(\d+)\s+op voorraad", re.I)


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _number(raw: str) -> float:
    return float(raw.replace(",", "."))


def parse_abv(name: str, description: str) -> float | None:
    """ABV from the name, else from the description; None if absent or ambiguous."""
    in_name = {_number(m) for m in _ABV_NAME.findall(name) if 30 <= _number(m) <= 75}
    if len(in_name) == 1:
        return in_name.pop()
    if len(in_name) > 1:
        return None
    found = set()
    for a, b in _ABV_TEXT.findall(description):
        value = _number(a or b)
        if 30 <= value <= 75:
            found.add(value)
    return found.pop() if len(found) == 1 else None


def parse_bottle_ml(name: str) -> int | None:
    match = _SIZE.search(name)
    if not match:
        return None
    value, unit = _number(match.group(1)), match.group(2).lower()
    if unit == "cl":
        return round(value * 10)
    if unit == "ml":
        return round(value)
    return round(value * 1000)  # ltr, liter, l


def parse_stock(text: str) -> int:
    """Bottles on the shelf now; sold out and backorder-only count as 0."""
    match = _STOCK.search(text or "")
    return int(match.group(1)) if match else 0


def parse_single_malt(name: str, description: str, categories: list[str]) -> bool | None:
    if "blended" in categories or "bourbon" in categories or NOT_SINGLE_MALT.search(name):
        return False
    if SINGLE_MALT.search(name) or SINGLE_MALT.search(description):
        return not NOT_SINGLE_MALT.search(name)
    return None


def _attribute(product: dict[str, Any], taxonomy: str) -> list[str]:
    for attribute in product.get("attributes") or []:
        if attribute.get("taxonomy") == taxonomy:
            return [html.unescape(t["name"]) for t in attribute.get("terms") or []]
    return []


def parse_product(product: dict[str, Any]) -> dict[str, Any]:
    name = clean(product["name"])
    description = clean(f"{product.get('short_description', '')} {product.get('description', '')}")
    categories = [c["slug"] for c in product.get("categories") or [] if c["slug"] != "whisky"]
    regions = _attribute(product, "pa_gebied")
    countries = _attribute(product, "pa_land")
    flavours = [FLAVOURS.get(f, f) for f in _attribute(product, "pa_whiskysmaak")]
    bottle_ml = parse_bottle_ml(name)
    return {
        "id": f"H{product['id']}",
        "name": name,
        "brand": (_attribute(product, "pa_whiskymerk") or [None])[0],
        "url": product["permalink"],
        "price_cents": int(product["prices"]["price"]),
        "stock_bottles": parse_stock((product.get("stock_availability") or {}).get("text", "")),
        "categories": categories,
        "region": regions[0] if regions else None,
        "country": COUNTRIES.get(countries[0], countries[0]) if countries else None,
        "flavour_labels": flavours,
        "abv": parse_abv(name, description),
        "bottle_ml": bottle_ml or 700,
        "bottle_ml_stated": bottle_ml is not None,
        "single_malt": parse_single_malt(name, description, categories),
        "sherry_cask": bool(SHERRY_WORDS.search(name) or SHERRY_WORDS.search(description)),
        "gift_set": bool(GIFT.search(name)) or "geschenken" in categories,
    }
