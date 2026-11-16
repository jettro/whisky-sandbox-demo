"""Parser rules on small synthetic records (no shop text is stored or copied)."""

import pytest

from whisky_sandbox_demo.season.parsing import (
    parse_abv,
    parse_bottle_ml,
    parse_product,
    parse_single_malt,
    parse_stock,
)


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [
        ("Some Malt 12 years old 48,8%", "", 48.8),
        ("Some Malt", "Deze whisky heeft 46% alcohol.", 46.0),
        ("Some Malt", "met een alcoholpercentage van 51,5%.", 51.5),
        ("Some Malt", "Gerijpt op 100% eikenhout.", None),  # out of range
        ("Some Blend", "malt (25%) en grain (75%)", None),  # not an ABV
        ("Some Malt", "heeft 40% alcohol ... gebotteld op 46% alcohol", None),  # ambiguous
        ("Two Values 40% 46%", "", None),
        ("No Info", "Een mooie whisky.", None),
    ],
)
def test_abv(name, text, expected):
    assert parse_abv(name, text) == expected


@pytest.mark.parametrize(
    ("name", "ml"),
    [
        ("X 0,7 ltr", 700),
        ("X 0,35 liter", 350),
        ("X 20cl", 200),
        ("X 5cl", 50),
        ("X 1 liter", 1000),
        ("X 12 years old", None),
    ],
)
def test_bottle_size(name, ml):
    assert parse_bottle_ml(name) == ml


@pytest.mark.parametrize(
    ("text", "stock"),
    [
        ("3 op voorraad", 3),
        ("2 op voorraad (kan nabesteld worden)", 2),
        ("Uitverkocht", 0),
        ("Beschikbaar via nabestelling", 0),
        ("", 0),
    ],
)
def test_stock(text, stock):
    assert parse_stock(text) == stock


def test_single_malt_rules():
    assert parse_single_malt("X 10", "Een single malt uit Speyside.", ["malt"]) is True
    assert parse_single_malt("X 10", "een van de eerste single malts", ["malt"]) is True
    assert parse_single_malt("X Blended Malt", "single malt", ["malt"]) is False
    assert parse_single_malt("Monkey Shoulder", "", ["blended"]) is False
    assert parse_single_malt("X Distillery 12", "Een mooie whisky.", ["malt"]) is None


def _product(**overrides):
    base = {
        "id": 7,
        "name": "Test Glen 12 years old",
        "permalink": "https://example.invalid/p/7",
        "prices": {"price": "3995"},
        "stock_availability": {"text": "2 op voorraad"},
        "categories": [{"slug": "malt"}, {"slug": "whisky"}],
        "attributes": [
            {"taxonomy": "pa_gebied", "terms": [{"name": "Speyside"}]},
            {"taxonomy": "pa_land", "terms": [{"name": "Schotland"}]},
            {"taxonomy": "pa_whiskysmaak", "terms": [{"name": "Rijk &amp; rond"}]},
        ],
        "short_description": "",
        "description": "<p>Een single malt op oloroso sherry vaten. Heeft 43% alcohol.</p>",
    }
    return {**base, **overrides}


def test_parse_product_keeps_facts_only():
    record = parse_product(_product())
    assert record["id"] == "H7" and record["price_cents"] == 3995 and record["stock_bottles"] == 2
    assert record["country"] == "Scotland" and record["region"] == "Speyside"
    assert record["flavour_labels"] == ["rich_round"]
    assert record["abv"] == 43.0 and record["single_malt"] is True and record["sherry_cask"]
    assert record["bottle_ml"] == 700 and record["bottle_ml_stated"] is False
    assert "description" not in record and "short_description" not in record


def test_gift_sets_are_flagged():
    record = parse_product(_product(name="Test Tripack 3 x 5cl"))
    assert record["gift_set"] is True
