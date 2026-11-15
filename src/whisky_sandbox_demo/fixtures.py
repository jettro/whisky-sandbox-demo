"""Load the bundled whisky and supplier snapshot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

from whisky_sandbox_demo.models import Offer, Supplier, Whisky


@dataclass(frozen=True)
class Fixtures:
    snapshot_date: str
    source_note: str
    whiskies: dict[str, Whisky]
    suppliers: dict[str, Supplier]

    def offer(self, supplier_id: str, whisky_id: str) -> Offer | None:
        supplier = self.suppliers.get(supplier_id)
        if supplier is None:
            return None
        return next((o for o in supplier.offers if o.whisky_id == whisky_id), None)


def _read(name: str) -> dict:
    return json.loads(files("whisky_sandbox_demo.data").joinpath(name).read_text("utf-8"))


@cache
def load_fixtures() -> Fixtures:
    whisky_doc = _read("whiskies.json")
    supplier_doc = _read("suppliers.json")
    whiskies = [Whisky.model_validate(w) for w in whisky_doc["whiskies"]]
    suppliers = [Supplier.model_validate(s) for s in supplier_doc["suppliers"]]
    return Fixtures(
        snapshot_date=whisky_doc["snapshot_date"],
        source_note=whisky_doc["source"],
        whiskies={w.id: w for w in whiskies},
        suppliers={s.id: s for s in suppliers},
    )
