"""Snapshot the whisky catalogue of Slijterij De Helm for scenario 2 (run once, on the host).

Reads the shop's public WooCommerce Store API page by page (with a pause between requests),
keeps facts only (see season/parsing.py), adds two clearly fictional suppliers, and writes
src/whisky_sandbox_demo/data/season_catalogue.json.

    uv run python scripts/snapshot_de_helm.py            # re-parse the local cache if present
    uv run python scripts/snapshot_de_helm.py --refresh  # fetch again
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from whisky_sandbox_demo.season.parsing import parse_product

API = "https://slijterijdehelm.nl/wp-json/wc/store/v1/products"
PARAMS = {"category": "whisky", "per_page": 100, "min_price": 2000, "max_price": 8000}
OUT = Path("src/whisky_sandbox_demo/data/season_catalogue.json")
# Raw API responses include the shop's descriptions: kept locally for re-parsing, never committed.
RAW_CACHE = Path("snapshot_cache") / "de_helm_store_api.json"
USER_AGENT = "whisky-sandbox-demo snapshot (one-off, facts only)"


def fetch_all() -> list[dict]:
    products, page = [], 1
    while True:
        query = urllib.parse.urlencode({**PARAMS, "page": page})
        request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)
            total_pages = int(response.headers.get("X-WP-TotalPages", page))
        products += batch
        print(f"  page {page}/{total_pages}: {len(batch)} products")
        if page >= total_pages or not batch:
            return products
        page += 1
        time.sleep(1.0)


def _fraction(key: str) -> float:
    """Deterministic pseudo-random number in [0, 1) from a string."""
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0x100000000


def fictional_offers(records: list[dict], supplier: str) -> list[dict]:
    """Derived offers for the fictional suppliers. Same bottles, different range and prices."""
    offers = []
    for r in records:
        f = _fraction(f"{supplier}:{r['id']}")
        if supplier == "S2":  # Islay specialist, cheaper, small range elsewhere
            carries = r["region"] == "Islay" or f < 0.25
            price = round(r["price_cents"] * 0.88 / 50) * 50 - 5
            stock = int(f * 7)  # 0..6, sometimes none
        else:  # S3: world whisky specialist, premium prices, good stock
            carries = (r["country"] not in (None, "Scotland")) or f < 0.45
            price = round(r["price_cents"] * 1.08 / 50) * 50 - 5
            stock = 3 + int(f * 10)
        if carries:
            offers.append({"id": r["id"], "price_cents": max(price, 995), "stock_bottles": stock})
    return offers


def main() -> None:
    if "--refresh" in sys.argv or not RAW_CACHE.exists():
        print(f"Fetching {API} ...")
        raw = fetch_all()
        RAW_CACHE.parent.mkdir(exist_ok=True)
        RAW_CACHE.write_text(json.dumps({"fetched": dt.date.today().isoformat(), "products": raw}))
    else:
        cached = json.loads(RAW_CACHE.read_text())
        raw = cached["products"]
        print(f"Re-parsing cached API response from {cached['fetched']} (use --refresh to fetch)")
    records = sorted((parse_product(p) for p in raw), key=lambda r: r["id"])
    doc = {
        "snapshot_date": json.loads(RAW_CACHE.read_text())["fetched"],
        "source": (
            "Facts (name, price, stock, ABV, size, region, country, the shop's flavour label) "
            "parsed from the public Store API of Slijterij De Helm, whisky category, EUR 20-80. "
            "ABV, single-malt and sherry-cask flags are parsed from product text and are null "
            "when unclear. Unstated bottle sizes are assumed 70 cl. No descriptions stored."
        ),
        "products": records,
        "suppliers": [
            {
                "id": "S1",
                "name": "Slijterij De Helm",
                "fictional": False,
                "notes": "Real shop; prices and stock are the snapshot.",
                "shipping": {"fee_cents": 695, "free_from_cents": 10000},
                "offers": [
                    {
                        "id": r["id"],
                        "price_cents": r["price_cents"],
                        "stock_bottles": r["stock_bottles"],
                    }
                    for r in records
                ],
            },
            {
                "id": "S2",
                "name": "Peat & Price",
                "fictional": True,
                "notes": "Fictional Islay specialist: about 12% cheaper, patchy elsewhere.",
                "shipping": {"fee_cents": 1295, "free_from_cents": 25000},
                "offers": fictional_offers(records, "S2"),
            },
            {
                "id": "S3",
                "name": "Cask Corner",
                "fictional": True,
                "notes": "Fictional premium shop: about 8% dearer, strong in world whisky.",
                "shipping": {"fee_cents": 0, "free_from_cents": 0},
                "offers": fictional_offers(records, "S3"),
            },
        ],
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"Wrote {len(records)} products to {OUT} ({OUT.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
