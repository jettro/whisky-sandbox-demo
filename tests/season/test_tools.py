import pytest

from whisky_sandbox_demo.season.catalogue import load_catalogue
from whisky_sandbox_demo.season.tools import (
    MAX_DETAIL_IDS,
    PAGE_SIZE,
    get_products,
    get_season_brief,
    list_products,
)


def test_snapshot_shape():
    cat = load_catalogue()
    assert len(cat.products) > 400
    assert not cat.suppliers["S1"].fictional
    assert cat.suppliers["S2"].fictional and cat.suppliers["S3"].fictional
    assert all(p.url.startswith("https://slijterijdehelm.nl/") for p in cat.products.values())
    # Messy on purpose: unknowns stay unknown.
    assert any(p.abv is None for p in cat.products.values())
    assert any(p.single_malt is None for p in cat.products.values())
    assert any(p.region is None for p in cat.products.values())


def test_brief():
    brief = get_season_brief()
    assert brief.members == 30 and brief.whiskies_per_evening == 4
    assert [e.theme for e in brief.evenings] == ["speyside", "islay", "sherry_cask", "world"]
    assert {s.id for s in brief.suppliers} == {"S1", "S2", "S3"}
    assert brief.page_size == PAGE_SIZE and brief.max_detail_ids == MAX_DETAIL_IDS


def test_pagination_covers_every_offer_once():
    first = list_products("S1", 1)
    ids = [
        p.id for page in range(1, first.total_pages + 1) for p in list_products("S1", page).products
    ]
    assert len(ids) == len(set(ids)) == first.total_products
    assert all(len(list_products("S1", p).products) <= PAGE_SIZE for p in (1, first.total_pages))


def test_listing_hides_details():
    listing = list_products("S1", 1).products[0]
    assert not hasattr(listing, "abv") and not hasattr(listing, "single_malt")


def test_details_and_limits():
    ids = [p.id for p in list_products("S1", 1).products[:3]]
    result = get_products("S1", [*ids, "H0"])
    assert [p.id for p in result.products] == ids and result.not_found_ids == ["H0"]
    with pytest.raises(ValueError, match="At most 25"):
        get_products("S1", ids * 9)
    with pytest.raises(ValueError, match="page must be"):
        list_products("S1", 99)
    with pytest.raises(ValueError, match="Known: S1, S2, S3"):
        list_products("S9")


def test_fictional_supplier_prices_differ():
    cat = load_catalogue()
    pid = cat.suppliers["S2"].offers[0].id
    s1 = get_products("S1", [pid]).products[0].price_cents
    s2 = get_products("S2", [pid]).products[0].price_cents
    assert s2 < s1
