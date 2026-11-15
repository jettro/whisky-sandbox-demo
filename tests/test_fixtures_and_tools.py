import pytest

from whisky_sandbox_demo.fixtures import load_fixtures
from whisky_sandbox_demo.tools import (
    get_supplier_offers,
    get_tasting_brief,
    get_whisky_details,
    search_whiskies,
)


def test_fixture_shape():
    fx = load_fixtures()
    assert len(fx.whiskies) == 20
    assert fx.snapshot_date == "2026-11-15"
    assert set(fx.suppliers) == {"S1", "S2", "S3"}
    assert not fx.suppliers["S1"].fictional
    assert fx.suppliers["S2"].fictional and fx.suppliers["S3"].fictional
    for offer in fx.suppliers["S1"].offers:
        assert offer.source_url and offer.source_url.startswith("https://slijterijdehelm.nl/")
    for supplier in fx.suppliers.values():
        assert all(o.whisky_id in fx.whiskies for o in supplier.offers)
        assert all(isinstance(o.price_cents, int) and o.price_cents > 0 for o in supplier.offers)


def test_fixture_contains_the_intended_traps():
    fx = load_fixtures()
    assert any(w.abv > 50 and w.type == "single_malt" for w in fx.whiskies.values())
    assert any(w.abv == 50.0 for w in fx.whiskies.values())
    assert {w.type for w in fx.whiskies.values()} == {"single_malt", "blended_malt", "blend"}
    assert any(o.stock_bottles == 0 for o in fx.suppliers["S1"].offers)


def test_brief_exposes_supplier_ids_and_rules():
    brief = get_tasting_brief()
    assert [s.id for s in brief.suppliers] == ["S1", "S2", "S3"]
    assert brief.budget_cents == 20_000
    assert brief.max_abv == 50.0
    assert brief.participants == 8 and brief.pour_ml == 20


def test_search_filters_by_style_only():
    smoky = search_whiskies("smoky")
    assert smoky and all(w.style == "smoky" for w in smoky)
    # Not filtered on ABV: the agent must reject cask strength itself.
    assert any(w.abv > 50 for w in smoky)
    assert len(search_whiskies()) == 20


def test_details_report_unknown_ids():
    result = get_whisky_details(["W01", "W99"])
    assert [w.id for w in result.whiskies] == ["W01"]
    assert result.unknown_ids == ["W99"]
    assert result.whiskies[0].flavour.sweetness == 7


def test_supplier_offers_prices_and_stock():
    result = get_supplier_offers("S1", ["W12", "W16", "W99"])
    by_id = {o.whisky_id: o for o in result.offers}
    assert by_id["W12"].price_cents == 4095 and by_id["W12"].stock_bottles == 2
    assert by_id["W16"].stock_bottles == 0 and by_id["W16"].in_stock is False
    assert result.not_carried_ids == ["W99"]


def test_discount_supplier_has_gaps():
    result = get_supplier_offers("S2", ["W01", "W12"])
    assert "W01" in result.not_carried_ids
    assert result.offers[0].whisky_id == "W12" and result.offers[0].stock_bottles == 0


def test_unknown_supplier_is_explained():
    with pytest.raises(ValueError, match="Known suppliers: S1, S2, S3"):
        get_supplier_offers("S9", ["W01"])
