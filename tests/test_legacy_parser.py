"""
tests/test_legacy_parser.py

Tests for parsers.layout_legacy.parse_legacy_invoice.
Covers INV-01, INV-02, INV-03 and INV-04.

The reference JSON at reference/INV-01_expected_output.json is used as the
test oracle for INV-01 — not as an extraction input.  The parser must derive
every value independently from the PDF.

INV-02, INV-03, INV-04 values are taken from the approved Phase 2 analysis.
No fake reference JSON files are created for these documents.

How to run:
    source .venv/bin/activate
    pytest tests/test_legacy_parser.py -v
"""

from decimal import Decimal
from pathlib import Path

import pytest

from helpers.schema_io import load_json, load_schema, validate_output
from parsers.layout_legacy import parse_legacy_invoice

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PDF_INV01   = Path("input/INV-01_RE-2026-10418.pdf")
PDF_INV02   = Path("input/INV-02_RE-2026-10431.pdf")
PDF_INV03   = Path("input/INV-03_GS-2026-00872.pdf")
PDF_INV04   = Path("input/INV-04_RE-2026-10457.pdf")
REF_INV01   = Path("reference/INV-01_expected_output.json")
SCHEMA_PATH = Path("input/output_schema.json")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def inv01() -> dict:
    """Parse INV-01 (Decimal values intact)."""
    return parse_legacy_invoice(PDF_INV01)


@pytest.fixture(scope="module")
def inv02() -> dict:
    """Parse INV-02 (Decimal values intact)."""
    return parse_legacy_invoice(PDF_INV02)


@pytest.fixture(scope="module")
def inv03() -> dict:
    """Parse INV-03 credit note (Decimal values intact)."""
    return parse_legacy_invoice(PDF_INV03)


@pytest.fixture(scope="module")
def inv04() -> dict:
    """Parse INV-04 (Decimal values intact)."""
    return parse_legacy_invoice(PDF_INV04)


@pytest.fixture(scope="module")
def reference() -> dict:
    """Load INV-01 reference JSON with Decimal precision via load_json."""
    return load_json(REF_INV01)


@pytest.fixture(scope="module")
def schema() -> dict:
    """Load the output schema once."""
    return load_schema(SCHEMA_PATH)


# ===========================================================================
# INV-01 — Structural
# ===========================================================================

class TestINV01Structure:

    def test_returns_dict(self, inv01: dict) -> None:
        assert isinstance(inv01, dict)

    def test_has_six_line_items(self, inv01: dict) -> None:
        assert len(inv01["line_items"]) == 6

    def test_passes_schema_validation(self, inv01: dict, schema: dict) -> None:
        validate_output(inv01, schema)


# ===========================================================================
# INV-01 — Header fields
# ===========================================================================

class TestINV01Header:

    def test_document_type(self, inv01: dict) -> None:
        assert inv01["document_type"] == "invoice"

    def test_document_number(self, inv01: dict) -> None:
        assert inv01["document_number"] == "RE-2026-10418"

    def test_document_date(self, inv01: dict) -> None:
        assert inv01["document_date"] == "2026-10-06"

    def test_service_date(self, inv01: dict) -> None:
        assert inv01["service_date"] == "2026-10-02"

    def test_due_date(self, inv01: dict) -> None:
        assert inv01["due_date"] == "2026-11-05"

    def test_currency(self, inv01: dict) -> None:
        assert inv01["currency"] == "EUR"

    def test_order_reference(self, inv01: dict) -> None:
        assert inv01["order_reference"] == "4500093317"

    def test_delivery_note_number(self, inv01: dict) -> None:
        assert inv01["delivery_note_number"] == "LS-58821"

    def test_referenced_invoice_is_null(self, inv01: dict) -> None:
        assert inv01["referenced_invoice"] is None

    def test_supplier_name(self, inv01: dict) -> None:
        assert inv01["supplier"]["name"] == "Kessler Industrietechnik GmbH"

    def test_supplier_vat_id(self, inv01: dict) -> None:
        assert inv01["supplier"]["vat_id"] == "DE287364519"

    def test_buyer_name_excludes_department(self, inv01: dict) -> None:
        assert inv01["buyer"]["name"] == "Rheinwerk Anlagenbau AG"
        assert "Abt." not in inv01["buyer"]["name"]

    def test_buyer_street(self, inv01: dict) -> None:
        assert inv01["buyer"]["street"] == "Hafenstraße 88"

    def test_buyer_postal_code(self, inv01: dict) -> None:
        assert inv01["buyer"]["postal_code"] == "47119"

    def test_buyer_city(self, inv01: dict) -> None:
        assert inv01["buyer"]["city"] == "Duisburg"

    def test_buyer_customer_number(self, inv01: dict) -> None:
        assert inv01["buyer"]["customer_number"] == "40217"


# ===========================================================================
# INV-01 — Line items
# ===========================================================================

class TestINV01LineItems:

    def test_position_4_has_5_percent_discount(self, inv01: dict) -> None:
        pos4 = inv01["line_items"][3]
        assert pos4["position"] == 4
        assert pos4["discount_percent"] == Decimal("5")

    def test_position_5_has_price_unit_100(self, inv01: dict) -> None:
        pos5 = inv01["line_items"][4]
        assert pos5["position"] == 5
        assert pos5["price_unit"] == Decimal("100")

    def test_position_5_unit_price(self, inv01: dict) -> None:
        assert inv01["line_items"][4]["unit_price"] == Decimal("14.60")

    def test_positions_are_sequential(self, inv01: dict) -> None:
        assert [i["position"] for i in inv01["line_items"]] == [1, 2, 3, 4, 5, 6]

    def test_all_vat_rates_are_19(self, inv01: dict) -> None:
        for item in inv01["line_items"]:
            assert item["vat_rate"] == 19

    def test_no_discount_except_position_4(self, inv01: dict) -> None:
        for item in inv01["line_items"]:
            if item["position"] != 4:
                assert item["discount_percent"] is None

    def test_printed_line_totals(self, inv01: dict) -> None:
        expected = [
            Decimal("202.80"), Decimal("96.00"), Decimal("280.80"),
            Decimal("144.97"), Decimal("58.40"), Decimal("18.50"),
        ]
        for item, exp in zip(inv01["line_items"], expected):
            assert item["line_total"] == exp


# ===========================================================================
# INV-01 — Totals
# ===========================================================================

class TestINV01Totals:

    def test_net_by_vat_rate(self, inv01: dict) -> None:
        assert inv01["totals"]["net_by_vat_rate"]["19"] == Decimal("801.47")

    def test_vat_by_vat_rate(self, inv01: dict) -> None:
        assert inv01["totals"]["vat_by_vat_rate"]["19"] == Decimal("152.28")

    def test_net_total(self, inv01: dict) -> None:
        assert inv01["totals"]["net_total"] == Decimal("801.47")

    def test_vat_total(self, inv01: dict) -> None:
        assert inv01["totals"]["vat_total"] == Decimal("152.28")

    def test_gross_total(self, inv01: dict) -> None:
        assert inv01["totals"]["gross_total"] == Decimal("953.75")


# ===========================================================================
# INV-01 — Cash discount
# ===========================================================================

class TestINV01CashDiscount:

    def test_cash_discount_percent(self, inv01: dict) -> None:
        assert inv01["cash_discount"]["percent"] == Decimal("2")

    def test_cash_discount_until(self, inv01: dict) -> None:
        assert inv01["cash_discount"]["until"] == "2026-10-16"

    def test_cash_discount_amount(self, inv01: dict) -> None:
        assert inv01["cash_discount"]["amount"] == Decimal("19.08")


# ===========================================================================
# INV-01 — Exact reference comparison (Decimal)
# ===========================================================================

class TestINV01ReferenceComparison:
    """Verify the parsed output matches reference/INV-01_expected_output.json exactly."""

    def test_exact_output_equals_reference(
        self, inv01: dict, reference: dict
    ) -> None:
        # Both inv01 and reference use Decimal for numeric values (via load_json).
        # This single assertion catches any field-level mismatch.
        assert inv01 == reference, (
            "Parsed INV-01 output does not match reference JSON exactly. "
            "Differing keys: "
            + str([k for k in set(inv01) | set(reference) if inv01.get(k) != reference.get(k)])
        )


# ===========================================================================
# INV-02 — Three-page invoice, 26 items, two VAT rates
# ===========================================================================

class TestINV02Structure:

    def test_returns_dict(self, inv02: dict) -> None:
        assert isinstance(inv02, dict)

    def test_has_26_line_items(self, inv02: dict) -> None:
        assert len(inv02["line_items"]) == 26

    def test_passes_schema_validation(self, inv02: dict, schema: dict) -> None:
        validate_output(inv02, schema)

    def test_no_carry_forward_rows(self, inv02: dict) -> None:
        for item in inv02["line_items"]:
            assert "Übertrag" not in item["description"]
            assert item["position"] > 0


class TestINV02Header:

    def test_document_number(self, inv02: dict) -> None:
        assert inv02["document_number"] == "RE-2026-10431"

    def test_document_date(self, inv02: dict) -> None:
        assert inv02["document_date"] == "2026-10-09"

    def test_service_date(self, inv02: dict) -> None:
        assert inv02["service_date"] == "2026-10-07"

    def test_due_date(self, inv02: dict) -> None:
        assert inv02["due_date"] == "2026-11-08"

    def test_order_reference(self, inv02: dict) -> None:
        assert inv02["order_reference"] == "4500093402"

    def test_delivery_note_number(self, inv02: dict) -> None:
        assert inv02["delivery_note_number"] == "LS-58907"

    def test_document_type(self, inv02: dict) -> None:
        assert inv02["document_type"] == "invoice"


class TestINV02LineItems:

    def test_positions_10_to_260(self, inv02: dict) -> None:
        positions = [i["position"] for i in inv02["line_items"]]
        assert positions == list(range(10, 261, 10))

    def test_qty_1000_parsed_correctly(self, inv02: dict) -> None:
        # Pos 30: "1.000" → 1000 (German thousands separator)
        pos30 = next(i for i in inv02["line_items"] if i["position"] == 30)
        assert pos30["quantity"] == Decimal("1000")

    def test_qty_1500_parsed_correctly(self, inv02: dict) -> None:
        # Pos 160: "1.500" → 1500
        pos160 = next(i for i in inv02["line_items"] if i["position"] == 160)
        assert pos160["quantity"] == Decimal("1500")

    def test_fractional_quantity_12_5(self, inv02: dict) -> None:
        # Pos 70: Hydraulikschlauch, qty 12.5 m
        pos70 = next(i for i in inv02["line_items"] if i["position"] == 70)
        assert pos70["quantity"] == Decimal("12.5")

    def test_price_unit_100(self, inv02: dict) -> None:
        # Pos 30, 40, 50, 160, 170, 180 have PE=100
        pe100_positions = {30, 40, 50, 160, 170, 180}
        for item in inv02["line_items"]:
            if item["position"] in pe100_positions:
                assert item["price_unit"] == Decimal("100"), (
                    f"Pos {item['position']} should have PE=100"
                )

    def test_pos90_has_7_percent_vat(self, inv02: dict) -> None:
        pos90 = next(i for i in inv02["line_items"] if i["position"] == 90)
        assert pos90["vat_rate"] == 7
        assert pos90["article_number"] == "BU-90011"

    def test_pos200_has_7_percent_vat(self, inv02: dict) -> None:
        pos200 = next(i for i in inv02["line_items"] if i["position"] == 200)
        assert pos200["vat_rate"] == 7
        assert pos200["article_number"] == "BU-90034"

    def test_all_other_items_have_19_percent_vat(self, inv02: dict) -> None:
        for item in inv02["line_items"]:
            if item["position"] not in (90, 200):
                assert item["vat_rate"] == 19

    def test_pos20_has_10_percent_discount(self, inv02: dict) -> None:
        pos20 = next(i for i in inv02["line_items"] if i["position"] == 20)
        assert pos20["discount_percent"] == Decimal("10")

    def test_pos60_has_5_percent_discount(self, inv02: dict) -> None:
        pos60 = next(i for i in inv02["line_items"] if i["position"] == 60)
        assert pos60["discount_percent"] == Decimal("5")

    def test_continuation_description_pos10(self, inv02: dict) -> None:
        # Pos 10 has a continuation line: "Charge 2026-114, Zeichnung 7713-B"
        pos10 = next(i for i in inv02["line_items"] if i["position"] == 10)
        assert "Charge 2026-114" in pos10["description"]

    def test_printed_line_total_pos60_not_recalculated(self, inv02: dict) -> None:
        # Pos 60: 12 × 46.80 × 0.95 = 533.52
        pos60 = next(i for i in inv02["line_items"] if i["position"] == 60)
        assert pos60["line_total"] == Decimal("533.52")


class TestINV02Totals:

    def test_net_19(self, inv02: dict) -> None:
        assert inv02["totals"]["net_by_vat_rate"]["19"] == Decimal("4787.18")

    def test_net_7(self, inv02: dict) -> None:
        assert inv02["totals"]["net_by_vat_rate"]["7"] == Decimal("318.80")

    def test_vat_19(self, inv02: dict) -> None:
        assert inv02["totals"]["vat_by_vat_rate"]["19"] == Decimal("909.56")

    def test_vat_7(self, inv02: dict) -> None:
        assert inv02["totals"]["vat_by_vat_rate"]["7"] == Decimal("22.32")

    def test_net_total(self, inv02: dict) -> None:
        # 4787.18 + 318.80 = 5105.98 [D]
        assert inv02["totals"]["net_total"] == Decimal("5105.98")

    def test_vat_total(self, inv02: dict) -> None:
        # 909.56 + 22.32 = 931.88 [D]
        assert inv02["totals"]["vat_total"] == Decimal("931.88")

    def test_gross_total(self, inv02: dict) -> None:
        assert inv02["totals"]["gross_total"] == Decimal("6037.86")


class TestINV02PaymentTerms:

    def test_due_date(self, inv02: dict) -> None:
        assert inv02["due_date"] == "2026-11-08"

    def test_cash_discount_percent(self, inv02: dict) -> None:
        assert inv02["cash_discount"]["percent"] == Decimal("2")

    def test_cash_discount_until(self, inv02: dict) -> None:
        assert inv02["cash_discount"]["until"] == "2026-10-19"

    def test_cash_discount_amount(self, inv02: dict) -> None:
        assert inv02["cash_discount"]["amount"] == Decimal("120.76")


# ===========================================================================
# INV-03 — Credit note (Gutschrift), negative amounts
# ===========================================================================

class TestINV03Structure:

    def test_document_type_is_credit_note(self, inv03: dict) -> None:
        assert inv03["document_type"] == "credit_note"

    def test_has_three_line_items(self, inv03: dict) -> None:
        assert len(inv03["line_items"]) == 3

    def test_passes_schema_validation(self, inv03: dict, schema: dict) -> None:
        validate_output(inv03, schema)


class TestINV03Header:

    def test_document_number(self, inv03: dict) -> None:
        assert inv03["document_number"] == "GS-2026-00872"

    def test_document_date(self, inv03: dict) -> None:
        assert inv03["document_date"] == "2026-10-12"

    def test_service_date_is_null(self, inv03: dict) -> None:
        assert inv03["service_date"] is None

    def test_due_date_is_null(self, inv03: dict) -> None:
        assert inv03["due_date"] is None

    def test_referenced_invoice(self, inv03: dict) -> None:
        # Must be the number only — no "Bezug", "Rechnung", or date suffix
        assert inv03["referenced_invoice"] == "RE-2026-10133"
        assert "Bezug" not in (inv03["referenced_invoice"] or "")
        assert "v." not in (inv03["referenced_invoice"] or "")

    def test_order_reference(self, inv03: dict) -> None:
        assert inv03["order_reference"] == "4500092977"

    def test_delivery_note_number(self, inv03: dict) -> None:
        assert inv03["delivery_note_number"] == "LS-58733"

    def test_cash_discount_is_null(self, inv03: dict) -> None:
        assert inv03["cash_discount"] is None


class TestINV03LineItems:

    def test_quantities_are_positive(self, inv03: dict) -> None:
        # Quantities are printed positive on credit notes
        for item in inv03["line_items"]:
            assert item["quantity"] > 0

    def test_unit_prices_are_positive(self, inv03: dict) -> None:
        for item in inv03["line_items"]:
            assert item["unit_price"] > 0

    def test_line_totals_are_negative(self, inv03: dict) -> None:
        assert inv03["line_items"][0]["line_total"] == Decimal("-225.80")
        assert inv03["line_items"][1]["line_total"] == Decimal("-155.00")
        assert inv03["line_items"][2]["line_total"] == Decimal("-19.25")

    def test_pos1_quantity_and_price(self, inv03: dict) -> None:
        pos1 = inv03["line_items"][0]
        assert pos1["quantity"] == Decimal("2")
        assert pos1["unit_price"] == Decimal("112.90")
        assert pos1["price_unit"] == Decimal("1")

    def test_pos3_price_unit_100(self, inv03: dict) -> None:
        pos3 = inv03["line_items"][2]
        assert pos3["price_unit"] == Decimal("100")

    def test_continuation_descriptions(self, inv03: dict) -> None:
        # Each position has a reason text continuation line
        assert "RMA-2026-0388" in inv03["line_items"][0]["description"]
        assert "LS-58733" in inv03["line_items"][1]["description"]
        assert "Festigkeitsklasse" in inv03["line_items"][2]["description"]


class TestINV03Totals:

    def test_net_total_negative(self, inv03: dict) -> None:
        assert inv03["totals"]["net_total"] == Decimal("-400.05")

    def test_vat_total_negative(self, inv03: dict) -> None:
        assert inv03["totals"]["vat_total"] == Decimal("-76.01")

    def test_gross_total_negative(self, inv03: dict) -> None:
        assert inv03["totals"]["gross_total"] == Decimal("-476.06")

    def test_net_by_vat_rate_negative(self, inv03: dict) -> None:
        assert inv03["totals"]["net_by_vat_rate"]["19"] == Decimal("-400.05")

    def test_vat_by_vat_rate_negative(self, inv03: dict) -> None:
        assert inv03["totals"]["vat_by_vat_rate"]["19"] == Decimal("-76.01")


# ===========================================================================
# INV-04 — Two-page invoice with Pos 7 document arithmetic error
# ===========================================================================

class TestINV04Structure:

    def test_has_15_line_items(self, inv04: dict) -> None:
        assert len(inv04["line_items"]) == 15

    def test_passes_schema_validation(self, inv04: dict, schema: dict) -> None:
        validate_output(inv04, schema)

    def test_no_carry_forward_in_line_items(self, inv04: dict) -> None:
        for item in inv04["line_items"]:
            assert "Übertrag" not in item["description"]


class TestINV04Header:

    def test_document_number(self, inv04: dict) -> None:
        assert inv04["document_number"] == "RE-2026-10457"

    def test_document_date(self, inv04: dict) -> None:
        assert inv04["document_date"] == "2026-10-14"

    def test_service_date(self, inv04: dict) -> None:
        assert inv04["service_date"] == "2026-10-13"

    def test_due_date(self, inv04: dict) -> None:
        assert inv04["due_date"] == "2026-11-13"

    def test_order_reference(self, inv04: dict) -> None:
        assert inv04["order_reference"] == "4500093560"

    def test_delivery_note_number(self, inv04: dict) -> None:
        assert inv04["delivery_note_number"] == "LS-59012"


class TestINV04Pos7Discrepancy:
    """The document arithmetic error in Pos 7 must be preserved exactly."""

    def test_printed_line_total_is_1284_52(self, inv04: dict) -> None:
        pos7 = next(i for i in inv04["line_items"] if i["position"] == 7)
        assert pos7["line_total"] == Decimal("1284.52"), (
            f"Pos 7 line_total must be the PRINTED value 1284.52, got {pos7['line_total']}"
        )

    def test_unit_price_is_48_02(self, inv04: dict) -> None:
        pos7 = next(i for i in inv04["line_items"] if i["position"] == 7)
        assert pos7["unit_price"] == Decimal("48.02")

    def test_quantity_is_26(self, inv04: dict) -> None:
        pos7 = next(i for i in inv04["line_items"] if i["position"] == 7)
        assert pos7["quantity"] == Decimal("26")

    def test_discrepancy_is_36(self, inv04: dict) -> None:
        # Verify the discrepancy: 26 × 48.02 = 1248.52; printed = 1284.52
        pos7 = next(i for i in inv04["line_items"] if i["position"] == 7)
        calculated = pos7["quantity"] * pos7["unit_price"] / pos7["price_unit"]
        diff = pos7["line_total"] - calculated
        assert diff == Decimal("36.00"), (
            f"Expected discrepancy of 36.00, got {diff}"
        )


class TestINV04LineItems:

    def test_two_page_extraction_gives_15_items(self, inv04: dict) -> None:
        # Items 1–10 on page 1, items 11–15 on page 2
        positions = [i["position"] for i in inv04["line_items"]]
        assert positions == list(range(1, 16))

    def test_pos1_continuation_description(self, inv04: dict) -> None:
        pos1 = next(i for i in inv04["line_items"] if i["position"] == 1)
        assert "Zuschnitt" in pos1["description"]

    def test_pos2_has_5_percent_discount(self, inv04: dict) -> None:
        pos2 = next(i for i in inv04["line_items"] if i["position"] == 2)
        assert pos2["discount_percent"] == Decimal("5")

    def test_pos3_price_unit_100(self, inv04: dict) -> None:
        pos3 = next(i for i in inv04["line_items"] if i["position"] == 3)
        assert pos3["price_unit"] == Decimal("100")

    def test_pos14_has_7_percent_vat(self, inv04: dict) -> None:
        pos14 = next(i for i in inv04["line_items"] if i["position"] == 14)
        assert pos14["vat_rate"] == 7
        assert pos14["article_number"] == "BU-90011"


class TestINV04Totals:

    def test_net_19(self, inv04: dict) -> None:
        assert inv04["totals"]["net_by_vat_rate"]["19"] == Decimal("5213.22")

    def test_net_7(self, inv04: dict) -> None:
        assert inv04["totals"]["net_by_vat_rate"]["7"] == Decimal("69.80")

    def test_vat_19(self, inv04: dict) -> None:
        assert inv04["totals"]["vat_by_vat_rate"]["19"] == Decimal("990.51")

    def test_vat_7(self, inv04: dict) -> None:
        assert inv04["totals"]["vat_by_vat_rate"]["7"] == Decimal("4.89")

    def test_net_total(self, inv04: dict) -> None:
        # 5213.22 + 69.80 = 5283.02 [D]
        assert inv04["totals"]["net_total"] == Decimal("5283.02")

    def test_vat_total(self, inv04: dict) -> None:
        # 990.51 + 4.89 = 995.40 [D]
        assert inv04["totals"]["vat_total"] == Decimal("995.40")

    def test_gross_total(self, inv04: dict) -> None:
        assert inv04["totals"]["gross_total"] == Decimal("6278.42")


class TestINV04CashDiscount:

    def test_percent(self, inv04: dict) -> None:
        assert inv04["cash_discount"]["percent"] == Decimal("3")

    def test_until_derived(self, inv04: dict) -> None:
        # Derived [I]: 2026-10-14 + 7 days = 2026-10-21
        assert inv04["cash_discount"]["until"] == "2026-10-21"

    def test_amount(self, inv04: dict) -> None:
        assert inv04["cash_discount"]["amount"] == Decimal("188.35")


# ===========================================================================
# Robustness tests — totals validation
# ===========================================================================

class TestTotalsRobustness:
    """Verify that missing or incomplete totals raise ValueError rather than
    silently returning zero values."""

    def test_empty_word_list_raises_value_error(self) -> None:
        """_extract_totals with no words must raise, not return zeros."""
        from parsers.layout_legacy import _extract_totals
        with pytest.raises(ValueError, match="gross_total"):
            _extract_totals([])

    def test_words_with_no_rechnungsbetrag_raises(self) -> None:
        """A totals block missing the gross-total label must raise."""
        from parsers.layout_legacy import _extract_totals
        # Supply a net row and a VAT row but no Rechnungsbetrag row.
        # Using plausible coordinates in the totals region (x>330, y>250).
        fake_words = [
            (340.0, 270.0, 400.0, 282.0, "Nettobetrag"),
            (400.0, 270.0, 415.0, 282.0, "19"),
            (417.0, 270.0, 425.0, 282.0, "%"),
            (427.0, 270.0, 442.0, 282.0, "USt"),
            (540.0, 270.0, 567.0, 282.0, "801,47"),
            (340.0, 283.0, 355.0, 295.0, "zzgl."),
            (357.0, 283.0, 367.0, 295.0, "19"),
            (369.0, 283.0, 377.0, 295.0, "%"),
            (379.0, 283.0, 394.0, 295.0, "USt"),
            (396.0, 283.0, 411.0, 295.0, "auf"),
            (413.0, 283.0, 440.0, 295.0, "801,47"),
            (540.0, 283.0, 567.0, 295.0, "152,28"),
            # No Rechnungsbetrag row — gross_total cannot be extracted.
        ]
        with pytest.raises(ValueError, match="gross_total"):
            _extract_totals(fake_words)

    def test_all_four_legacy_invoices_extract_valid_totals(
        self, inv01: dict, inv02: dict, inv03: dict, inv04: dict
    ) -> None:
        """Confirm the existing four documents still produce valid totals."""
        for result, label in [
            (inv01, "INV-01"),
            (inv02, "INV-02"),
            (inv03, "INV-03"),
            (inv04, "INV-04"),
        ]:
            t = result["totals"]
            assert t["gross_total"] is not None, f"{label}: gross_total is None"
            assert isinstance(t["gross_total"], Decimal), f"{label}: gross_total not Decimal"
            assert t["net_by_vat_rate"], f"{label}: net_by_vat_rate is empty"
            assert t["vat_by_vat_rate"], f"{label}: vat_by_vat_rate is empty"
            assert set(t["net_by_vat_rate"].keys()) == set(t["vat_by_vat_rate"].keys()), (
                f"{label}: net and vat rate keys do not match"
            )
