"""The host-side checks for demo 3's exported files, on synthetic files (no VM needed)."""

import base64
import zlib

from whisky_sandbox_demo.demos.monty_smol import EXPECTED_FILES, verify_artifacts

from .conftest import GOOD_SELECTION, make_plan


def reportlab_style_pdf(*texts: str) -> bytes:
    """A minimal PDF whose content stream is ASCII85 + Flate encoded, like ReportLab's."""
    content = "".join(f"BT ({t}) Tj ET\n" for t in texts).encode("latin-1")
    stream = base64.a85encode(zlib.compress(content)) + b"~>"
    return b"%PDF-1.4\n1 0 obj\n<< /Filter [ /ASCII85Decode /FlateDecode ] >>\nstream\n" + (
        stream + b"endstream\nendobj\n%%EOF\n"
    )


def write_pack(tmp_path, plan, *, cards_texts, sheet_texts, csv_total_offset=0):
    pack = tmp_path / "pack"
    pack.mkdir()
    (tmp_path / EXPECTED_FILES["cards_pdf"]).write_bytes(reportlab_style_pdf(*cards_texts))
    (tmp_path / EXPECTED_FILES["answer_sheet_pdf"]).write_bytes(reportlab_style_pdf(*sheet_texts))
    (tmp_path / EXPECTED_FILES["flavour_chart_png"]).write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    rows = ["label,whisky_id,name,supplier,bottles,unit_price_eur,line_total_eur"]
    for w in plan.whiskies:
        cents = w.line_total_cents + csv_total_offset
        rows.append(
            f"{w.label},{w.whisky_id},{w.name},{plan.supplier_name},{w.bottles},"
            f"{w.unit_price_cents / 100:.2f},{cents / 100:.2f}"
        )
    rows.append(f"TOTAL,,,,,,{plan.total_cost_cents / 100:.2f}")
    (tmp_path / EXPECTED_FILES["shopping_list_csv"]).write_text("\n".join(rows) + "\n")


def test_valid_pack_passes(tmp_path):
    plan = make_plan(*GOOD_SELECTION)
    names = [w.name for w in plan.whiskies]
    write_pack(
        tmp_path, plan, cards_texts=["Card A", "Card B", "Card C", "Card D"], sheet_texts=names
    )
    results = verify_artifacts(tmp_path, plan)
    assert all(ok for ok, _ in results.values()), results


def test_cards_that_reveal_a_whisky_fail(tmp_path):
    plan = make_plan(*GOOD_SELECTION)
    names = [w.name for w in plan.whiskies]
    write_pack(tmp_path, plan, cards_texts=["A", "B", "C", f"D - {names[3]}"], sheet_texts=names)
    ok, detail = verify_artifacts(tmp_path, plan)["cards_pdf"]
    assert not ok and names[3] in detail


def test_csv_with_wrong_totals_fails(tmp_path):
    plan = make_plan(*GOOD_SELECTION)
    names = [w.name for w in plan.whiskies]
    write_pack(tmp_path, plan, cards_texts=list("ABCD"), sheet_texts=names, csv_total_offset=100)
    assert not verify_artifacts(tmp_path, plan)["shopping_list_csv"][0]


def test_missing_files_fail(tmp_path):
    results = verify_artifacts(tmp_path, make_plan(*GOOD_SELECTION))
    assert not any(ok for ok, _ in results.values())
