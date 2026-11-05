"""
tests/test_modern_parser.py

Tests for parsers.layout_modern.parse_modern_invoice against INV-05.

Values are drawn from the approved Phase 2 invoice analysis (Section 6).
No reference JSON file exists for INV-05; all assertions are derived from
the Phase 2 findings and the actual PDF.

How to run:
    source .venv/bin/activate
    pytest tests/test_modern_parser.py -v
"""

from decimal import Decimal
from pathlib import Path

import pytest

from helpers.schema_io import load_schema, validate_output
from parsers.layout_modern import parse_modern_invoice

PDF_INV05   = Path("input/INV-05_2026-R-00117.pdf")
SCHEMA_PATH = Path("input/output_schema.json")


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def inv05() -> dict:
    """Parse INV-05 (Decimal values intact)."""
    return parse_modern_invoice(PDF_INV05)


@pytest.fixture(scope="module")
def schema() -> dict:
    from helpers.schema_io import load_schema
    return load_schema(SCHEMA_PATH)


# ===========================================================================
# Structure
# ===========================================================================

class TestINV05Structure:

    def test_returns_dict(self, inv05: dict) -> None:
        assert isinstance(inv05, dict)

    def test_has_five_line_items(self, inv05: dict) -> None:
        assert len(inv05["line_items"]) == 5

    def test_passes_schema_validation(self, inv05: dict, schema: dict) -> None:
        validate_output(inv05, schema)


# ===========================================================================
# Header
# ===========================================================================

class TestINV05Header:

    def test_document_type(self, inv05: dict) -> None:
        assert inv05["document_type"] == "invoice"

    def test_document_number(self, inv05: dict) -> None:
        assert inv05["document_number"] == "2026-R-00117"

    def test_document_date(self, inv05: dict) -> None:
        # Long-form German date: "19. Oktober 2026"
        assert inv05["document_date"] == "2026-10-19"

    def test_service_date(self, inv05: dict) -> None:
        assert inv05["service_date"] == "2026-10-16"

    def test_due_date(self, inv05: dict) -> None:
        assert inv05["due_date"] == "2026-11-18"

    def test_currency(self, inv05: dict) -> None:
        assert inv05["currency"] == "EUR"

    def test_order_reference(self, inv05: dict) -> None:
        assert inv05["order_reference"] == "4500093701"

    def test_delivery_note_number(self, inv05: dict) -> None:
        assert inv05["delivery_note_number"] == "LS-59188"

    def test_referenced_invoice_is_null(self, inv05: dict) -> None:
        assert inv05["referenced_invoice"] is None

    def test_cash_discount_is_null(self, inv05: dict) -> None:
        # "Kein Skontoabzug." → null
        assert inv05["cash_discount"] is None


# ===========================================================================
# Supplier and buyer
# ===========================================================================

class TestINV05SupplierBuyer:

    def test_supplier_name(self, inv05: dict) -> None:
        assert inv05["supplier"]["name"] == "Kessler Industrietechnik GmbH"

    def test_supplier_vat_id(self, inv05: dict) -> None:
        assert inv05["supplier"]["vat_id"] == "DE287364519"

    def test_buyer_name_excludes_attention_line(self, inv05: dict) -> None:
        # "z. Hd. Kreditorenbuchhaltung" must not be in buyer.name
        assert inv05["buyer"]["name"] == "Rheinwerk Anlagenbau AG"
        assert "z. Hd." not in inv05["buyer"]["name"]

    def test_buyer_street(self, inv05: dict) -> None:
        assert inv05["buyer"]["street"] == "Hafenstraße 88"

    def test_buyer_postal_code(self, inv05: dict) -> None:
        assert inv05["buyer"]["postal_code"] == "47119"

    def test_buyer_city(self, inv05: dict) -> None:
        assert inv05["buyer"]["city"] == "Duisburg"

    def test_buyer_customer_number(self, inv05: dict) -> None:
        assert inv05["buyer"]["customer_number"] == "40217"


# ===========================================================================
# Line items — common
# ===========================================================================

class TestINV05LineItemsCommon:

    def test_positions_normalized(self, inv05: dict) -> None:
        # "001"→1, "002"→2 etc.
        assert [i["position"] for i in inv05["line_items"]] == [1, 2, 3, 4, 5]

    def test_all_price_units_are_1(self, inv05: dict) -> None:
        # No PE column in modern layout → always 1
        for item in inv05["line_items"]:
            assert item["price_unit"] == Decimal("1"), (
                f"Pos {item['position']} should have price_unit=1"
            )

    def test_vat_rate_pos1_to_4_is_19(self, inv05: dict) -> None:
        for item in inv05["line_items"][:4]:
            assert item["vat_rate"] == 19

    def test_vat_rate_pos5_is_7(self, inv05: dict) -> None:
        assert inv05["line_items"][4]["vat_rate"] == 7


# ===========================================================================
# Line items — position-specific
# ===========================================================================

class TestINV05Pos1:

    def test_article_number(self, inv05: dict) -> None:
        assert inv05["line_items"][0]["article_number"] == "KI-40112"

    def test_description(self, inv05: dict) -> None:
        assert "Rillenkugellager" in inv05["line_items"][0]["description"]
        assert "6205-2RS" in inv05["line_items"][0]["description"]

    def test_quantity(self, inv05: dict) -> None:
        assert inv05["line_items"][0]["quantity"] == Decimal("30")

    def test_unit(self, inv05: dict) -> None:
        assert inv05["line_items"][0]["unit"] == "Stk"

    def test_unit_price(self, inv05: dict) -> None:
        assert inv05["line_items"][0]["unit_price"] == Decimal("8.69")

    def test_no_discount(self, inv05: dict) -> None:
        assert inv05["line_items"][0]["discount_percent"] is None

    def test_line_total(self, inv05: dict) -> None:
        assert inv05["line_items"][0]["line_total"] == Decimal("260.70")


class TestINV05Pos2Discount:
    """Position 2 has a standalone 'abzgl.' discount row."""

    def test_article_number(self, inv05: dict) -> None:
        assert inv05["line_items"][1]["article_number"] == "KI-31009"

    def test_discount_percent_folded(self, inv05: dict) -> None:
        # Discount row "abzgl. Sonderrabatt 3 %" → discount_percent = 3
        assert inv05["line_items"][1]["discount_percent"] == Decimal("3")

    def test_line_total_is_post_discount(self, inv05: dict) -> None:
        # Pre-discount printed: 465.60; discount: -13.97; net: 451.63 [D]
        assert inv05["line_items"][1]["line_total"] == Decimal("451.63")

    def test_no_extra_discount_item(self, inv05: dict) -> None:
        # Must have exactly 5 items — discount row must NOT be a 6th item
        assert len(inv05["line_items"]) == 5

    def test_discount_not_in_description(self, inv05: dict) -> None:
        # Discount row text must not appear in the description
        assert "abzgl." not in inv05["line_items"][1]["description"]

    def test_unit_price(self, inv05: dict) -> None:
        assert inv05["line_items"][1]["unit_price"] == Decimal("116.40")


class TestINV05Pos3ThreeDecimal:
    """Position 3 has a three-decimal unit price and a continuation line."""

    def test_article_number(self, inv05: dict) -> None:
        assert inv05["line_items"][2]["article_number"] == "KI-20811"

    def test_unit_price_three_decimal_places(self, inv05: dict) -> None:
        # Must remain Decimal("0.152") — not rounded to 0.15 or 0.16
        price = inv05["line_items"][2]["unit_price"]
        assert price == Decimal("0.152"), (
            f"unit_price must be Decimal('0.152'), got {price!r}"
        )
        assert str(price) == "0.152"

    def test_continuation_description(self, inv05: dict) -> None:
        # "Preis je Stück (neue Preisliste 2026/2)" appended
        desc = inv05["line_items"][2]["description"]
        assert "neue Preisliste" in desc

    def test_quantity(self, inv05: dict) -> None:
        assert inv05["line_items"][2]["quantity"] == Decimal("600")

    def test_line_total(self, inv05: dict) -> None:
        assert inv05["line_items"][2]["line_total"] == Decimal("91.20")


class TestINV05Pos4:

    def test_article_number(self, inv05: dict) -> None:
        assert inv05["line_items"][3]["article_number"] == "KI-77002"

    def test_quantity(self, inv05: dict) -> None:
        assert inv05["line_items"][3]["quantity"] == Decimal("12")

    def test_unit_price(self, inv05: dict) -> None:
        assert inv05["line_items"][3]["unit_price"] == Decimal("10.15")

    def test_line_total(self, inv05: dict) -> None:
        assert inv05["line_items"][3]["line_total"] == Decimal("121.80")


class TestINV05Pos5:

    def test_article_number(self, inv05: dict) -> None:
        assert inv05["line_items"][4]["article_number"] == "BU-90034"

    def test_vat_rate_7(self, inv05: dict) -> None:
        assert inv05["line_items"][4]["vat_rate"] == 7

    def test_line_total(self, inv05: dict) -> None:
        assert inv05["line_items"][4]["line_total"] == Decimal("49.80")


# ===========================================================================
# Totals
# ===========================================================================

class TestINV05Totals:

    def test_net_by_vat_rate_19_derived(self, inv05: dict) -> None:
        # Derived [D] from line items: 260.70 + 451.63 + 91.20 + 121.80 = 925.33
        assert inv05["totals"]["net_by_vat_rate"]["19"] == Decimal("925.33")

    def test_net_by_vat_rate_7_derived(self, inv05: dict) -> None:
        # Derived [D] from Pos 5: 49.80
        assert inv05["totals"]["net_by_vat_rate"]["7"] == Decimal("49.80")

    def test_vat_by_vat_rate_19_printed(self, inv05: dict) -> None:
        # [P] printed as "MwSt 19%  175,81 €"
        assert inv05["totals"]["vat_by_vat_rate"]["19"] == Decimal("175.81")

    def test_vat_by_vat_rate_7_printed(self, inv05: dict) -> None:
        assert inv05["totals"]["vat_by_vat_rate"]["7"] == Decimal("3.49")

    def test_net_total_printed(self, inv05: dict) -> None:
        # [P] printed as "Summe netto  975,13 €"
        assert inv05["totals"]["net_total"] == Decimal("975.13")

    def test_vat_total_derived(self, inv05: dict) -> None:
        # [D] 175.81 + 3.49 = 179.30
        assert inv05["totals"]["vat_total"] == Decimal("179.30")

    def test_gross_total_printed(self, inv05: dict) -> None:
        # [P] printed as "Gesamtbetrag  1.154,43 €"
        assert inv05["totals"]["gross_total"] == Decimal("1154.43")


# ===========================================================================
# Robustness — missing required modern fields
# ===========================================================================

class TestINV05Robustness:

    def test_empty_word_list_raises_for_net_total(self) -> None:
        # With no words, 'Summe netto' is checked first — that's what raises.
        from parsers.layout_modern import _extract_modern_totals
        with pytest.raises(ValueError, match="net_total"):
            _extract_modern_totals([], [])

    def test_words_missing_summe_netto_raises(self) -> None:
        from parsers.layout_modern import _extract_modern_totals
        # Supply a Gesamtbetrag but no Summe netto
        fake_words = [
            (340.0, 400.0, 400.0, 412.0, "Gesamtbetrag"),
            (520.0, 400.0, 567.0, 412.0, "1.154,43"),
            (561.0, 400.0, 572.0, 412.0, "€"),
        ]
        with pytest.raises(ValueError, match="Summe netto"):
            _extract_modern_totals(fake_words, [])
