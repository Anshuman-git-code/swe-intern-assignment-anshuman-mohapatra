"""
tests/test_checks.py

Tests for all seven validation checks (V1–V7) in validation/checks.py.

Uses the actual generated output JSON files as fixtures, loaded via
load_json() so all monetary values are Decimal.

How to run:
    source .venv/bin/activate
    pytest tests/test_checks.py -v
"""

from decimal import Decimal
from pathlib import Path

import pytest

from helpers.schema_io import load_json
from validation.checks import (
    CheckResult,
    check_v1, check_v2, check_v3, check_v4,
    check_v5, check_v6, check_v7,
)

# ---------------------------------------------------------------------------
# Fixtures — load actual output JSON once per module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def inv01() -> dict:
    return load_json(Path("outputs/INV-01.json"))

@pytest.fixture(scope="module")
def inv02() -> dict:
    return load_json(Path("outputs/INV-02.json"))

@pytest.fixture(scope="module")
def inv03() -> dict:
    return load_json(Path("outputs/INV-03.json"))

@pytest.fixture(scope="module")
def inv04() -> dict:
    return load_json(Path("outputs/INV-04.json"))

@pytest.fixture(scope="module")
def inv05() -> dict:
    return load_json(Path("outputs/INV-05.json"))


# ===========================================================================
# V1 — Line-item arithmetic
# ===========================================================================

class TestV1:

    def test_inv01_all_six_items_pass(self, inv01: dict) -> None:
        results = check_v1(inv01)
        assert len(results) == 6
        assert all(r.passed for r in results), (
            "Expected all 6 INV-01 items to pass V1"
        )

    def test_inv02_all_26_items_pass(self, inv02: dict) -> None:
        results = check_v1(inv02)
        assert len(results) == 26
        assert all(r.passed for r in results)

    def test_inv03_credit_note_all_pass(self, inv03: dict) -> None:
        results = check_v1(inv03)
        assert len(results) == 3
        assert all(r.passed for r in results), (
            "INV-03 credit-note items should pass with negated expected"
        )

    def test_inv04_pos7_fails(self, inv04: dict) -> None:
        results = check_v1(inv04)
        pos7 = next(r for r in results if r.position == 7)
        assert not pos7.passed
        assert pos7.difference == Decimal("36.00"), (
            f"Expected diff=36.00, got {pos7.difference}"
        )

    def test_inv04_pos7_expected_is_1248_52(self, inv04: dict) -> None:
        results = check_v1(inv04)
        pos7 = next(r for r in results if r.position == 7)
        assert pos7.expected == Decimal("1248.52")

    def test_inv04_pos7_actual_is_1284_52(self, inv04: dict) -> None:
        results = check_v1(inv04)
        pos7 = next(r for r in results if r.position == 7)
        assert pos7.actual == Decimal("1284.52")

    def test_inv04_all_other_items_pass(self, inv04: dict) -> None:
        results = check_v1(inv04)
        others = [r for r in results if r.position != 7]
        assert all(r.passed for r in others)

    def test_inv05_all_five_items_pass(self, inv05: dict) -> None:
        results = check_v1(inv05)
        assert len(results) == 5
        assert all(r.passed for r in results)

    def test_tolerance_boundary_exactly_001_passes(self, inv01: dict) -> None:
        # amounts_match uses <=, so diff==0.01 must be PASS.
        from validation.checks import _d, round_financial, _TOLERANCE, amounts_match
        a = Decimal("100.00")
        b = Decimal("100.01")
        assert amounts_match(a, b, _TOLERANCE) is True

    def test_tolerance_just_over_fails(self, inv01: dict) -> None:
        from validation.checks import amounts_match, _TOLERANCE
        a = Decimal("100.00")
        b = Decimal("100.02")
        assert amounts_match(a, b, _TOLERANCE) is False

    def test_returns_check_result_objects(self, inv01: dict) -> None:
        results = check_v1(inv01)
        assert all(isinstance(r, CheckResult) for r in results)

    def test_inv03_credit_note_expected_is_negative(self, inv03: dict) -> None:
        # For credit notes the expected value must be negative.
        results = check_v1(inv03)
        for r in results:
            assert r.expected < Decimal("0"), (
                f"Pos {r.position}: expected should be negative for credit note"
            )

    def test_unknown_document_type_produces_fail(self) -> None:
        doc = {"document_type": "unknown", "line_items": []}
        results = check_v1(doc)
        assert results and not results[0].passed
        assert "unknown" in results[0].detail.lower() or "document_type" in results[0].detail

    def test_missing_line_items_produces_fail(self) -> None:
        doc = {"document_type": "invoice"}
        results = check_v1(doc)
        assert results and not results[0].passed

    def test_empty_line_items_produces_fail(self) -> None:
        doc = {"document_type": "invoice", "line_items": []}
        results = check_v1(doc)
        assert results and not results[0].passed


# ===========================================================================
# V2 — Per-VAT-rate net total
# ===========================================================================

class TestV2:

    def test_inv01_19pct_passes(self, inv01: dict) -> None:
        results = check_v2(inv01)
        r19 = next(r for r in results if r.rate == "19")
        assert r19.passed

    def test_inv02_both_rates_pass(self, inv02: dict) -> None:
        results = check_v2(inv02)
        assert any(r.rate == "19" and r.passed for r in results)
        assert any(r.rate == "7"  and r.passed for r in results)

    def test_inv04_19pct_fails(self, inv04: dict) -> None:
        results = check_v2(inv04)
        r19 = next(r for r in results if r.rate == "19")
        assert not r19.passed
        assert r19.difference == Decimal("36.00"), (
            f"Expected V2 diff=36.00, got {r19.difference}"
        )

    def test_inv04_7pct_passes(self, inv04: dict) -> None:
        results = check_v2(inv04)
        r7 = next(r for r in results if r.rate == "7")
        assert r7.passed

    def test_inv05_by_construction_disclosed(self, inv05: dict) -> None:
        # With inv05_derived=True the detail note must mention construction.
        results = check_v2(inv05, inv05_derived=True)
        assert all(r.passed for r in results)
        assert any("by construction" in r.detail.lower() for r in results), (
            "INV-05 V2 results must include the by-construction disclosure"
        )

    def test_missing_vat_key_fails(self) -> None:
        doc = {
            "document_type": "invoice",
            "line_items": [
                {"position": 1, "line_total": Decimal("100.00"), "vat_rate": 19}
            ],
            "totals": {
                "net_by_vat_rate": {},  # missing "19" key
                "vat_by_vat_rate": {},
                "net_total": Decimal("100.00"),
                "vat_total": Decimal("19.00"),
                "gross_total": Decimal("119.00"),
            },
        }
        results = check_v2(doc)
        assert any(not r.passed for r in results)

    def test_v2_expected_is_line_sum_actual_is_printed_net(self, inv04: dict) -> None:
        # For INV-04 19%: line_sum=5249.22 (expected), printed net=5213.22 (actual)
        results = check_v2(inv04)
        r19 = next(r for r in results if r.rate == "19")
        assert r19.expected == Decimal("5249.22"), (
            f"expected should be line-item sum=5249.22, got {r19.expected}"
        )
        assert r19.actual == Decimal("5213.22"), (
            f"actual should be printed net=5213.22, got {r19.actual}"
        )

    def test_missing_line_items_produces_fail(self) -> None:
        doc = {"document_type": "invoice", "totals": {"net_by_vat_rate": {"19": Decimal("100")}}}
        results = check_v2(doc)
        assert results and not results[0].passed

    def test_missing_net_by_vat_rate_produces_fail(self) -> None:
        doc = {
            "document_type": "invoice",
            "line_items": [{"position": 1, "line_total": Decimal("100"), "vat_rate": 19}],
            "totals": {},
        }
        results = check_v2(doc)
        assert results and not results[0].passed


# ===========================================================================
# V3 — VAT amount check
# ===========================================================================

class TestV3:

    def test_inv01_19pct_passes(self, inv01: dict) -> None:
        results = check_v3(inv01)
        r19 = next(r for r in results if r.rate == "19")
        assert r19.passed

    def test_inv02_both_rates_pass(self, inv02: dict) -> None:
        results = check_v3(inv02)
        assert all(r.passed for r in results)

    def test_inv04_v3_passes(self, inv04: dict) -> None:
        # V3 uses printed net; INV-04 printed net (5213.22) × 0.19 = 990.51 ✓
        results = check_v3(inv04)
        assert all(r.passed for r in results)

    def test_inv03_negative_rates_pass(self, inv03: dict) -> None:
        results = check_v3(inv03)
        assert all(r.passed for r in results)

    def test_inv05_both_rates_pass(self, inv05: dict) -> None:
        results = check_v3(inv05)
        assert all(r.passed for r in results)

    def test_mismatched_vat_fails(self) -> None:
        doc = {
            "totals": {
                "net_by_vat_rate": {"19": Decimal("100.00")},
                "vat_by_vat_rate": {"19": Decimal("99.00")},  # wrong
            }
        }
        results = check_v3(doc)
        assert any(not r.passed for r in results)

    def test_missing_net_by_vat_rate_produces_fail(self) -> None:
        doc = {"totals": {"vat_by_vat_rate": {"19": Decimal("19.00")}}}
        results = check_v3(doc)
        assert results and not results[0].passed

    def test_missing_vat_by_vat_rate_produces_fail(self) -> None:
        doc = {"totals": {"net_by_vat_rate": {"19": Decimal("100.00")}}}
        results = check_v3(doc)
        assert results and not results[0].passed


# ===========================================================================
# V4 — Gross total reconciliation
# ===========================================================================

class TestV4:

    def test_inv01_passes(self, inv01: dict) -> None:
        assert check_v4(inv01).passed

    def test_inv02_passes(self, inv02: dict) -> None:
        assert check_v4(inv02).passed

    def test_inv03_passes(self, inv03: dict) -> None:
        assert check_v4(inv03).passed

    def test_inv04_passes(self, inv04: dict) -> None:
        # net=5283.02 + vat=995.40 = 6278.42 ✓
        r = check_v4(inv04)
        assert r.passed
        assert r.expected == Decimal("6278.42")

    def test_inv05_passes(self, inv05: dict) -> None:
        assert check_v4(inv05).passed

    def test_gross_mismatch_fails(self) -> None:
        doc = {
            "totals": {
                "net_total": Decimal("100.00"),
                "vat_total": Decimal("19.00"),
                "gross_total": Decimal("120.00"),   # wrong: should be 119.00
            }
        }
        r = check_v4(doc)
        assert not r.passed

    def test_missing_net_total_fails(self) -> None:
        doc = {"totals": {"vat_total": Decimal("19"), "gross_total": Decimal("119")}}
        r = check_v4(doc)
        assert not r.passed
        assert "net_total" in r.detail

    def test_missing_vat_total_fails(self) -> None:
        doc = {"totals": {"net_total": Decimal("100"), "gross_total": Decimal("119")}}
        r = check_v4(doc)
        assert not r.passed
        assert "vat_total" in r.detail

    def test_missing_gross_total_fails(self) -> None:
        doc = {"totals": {"net_total": Decimal("100"), "vat_total": Decimal("19")}}
        r = check_v4(doc)
        assert not r.passed
        assert "gross_total" in r.detail

    def test_empty_doc_fails(self) -> None:
        r = check_v4({})
        assert not r.passed


# ===========================================================================
# V5 — Supplier VAT ID
# ===========================================================================

class TestV5:

    def test_valid_vat_id_passes(self, inv01: dict) -> None:
        r = check_v5(inv01)
        assert r.passed
        assert r.actual == "DE287364519"

    def test_all_five_documents_pass(
        self, inv01, inv02, inv03, inv04, inv05
    ) -> None:
        for doc, label in [(inv01,"INV-01"),(inv02,"INV-02"),
                            (inv03,"INV-03"),(inv04,"INV-04"),(inv05,"INV-05")]:
            assert check_v5(doc).passed, f"{label} V5 should pass"

    def test_malformed_vat_id_fails(self) -> None:
        doc = {"supplier": {"vat_id": "DE12345678"}}   # 8 digits, not 9
        assert not check_v5(doc).passed

    def test_missing_de_prefix_fails(self) -> None:
        doc = {"supplier": {"vat_id": "123456789"}}
        assert not check_v5(doc).passed

    def test_empty_vat_id_fails(self) -> None:
        doc = {"supplier": {"vat_id": ""}}
        assert not check_v5(doc).passed


# ===========================================================================
# V6 — Date validation
# ===========================================================================

class TestV6:

    def test_inv01_all_dates_valid(self, inv01: dict) -> None:
        results = check_v6(inv01)
        date_results = [r for r in results if r.check_id == "V6"]
        assert all(r.passed for r in date_results)

    def test_all_five_documents_pass(
        self, inv01, inv02, inv03, inv04, inv05
    ) -> None:
        for doc, label in [(inv01,"INV-01"),(inv02,"INV-02"),
                            (inv03,"INV-03"),(inv04,"INV-04"),(inv05,"INV-05")]:
            fails = [r for r in check_v6(doc) if not r.passed]
            assert not fails, f"{label} V6 failures: {[r.detail for r in fails]}"

    def test_invalid_date_fails(self) -> None:
        doc = {"document_date": "2026-13-01", "service_date": None,
               "due_date": None, "cash_discount": None}
        results = check_v6(doc)
        assert any(not r.passed for r in results)

    def test_due_date_before_document_date_fails(self) -> None:
        doc = {"document_date": "2026-10-14", "service_date": None,
               "due_date": "2026-10-01",   # before document_date
               "cash_discount": None}
        results = check_v6(doc)
        ordering_fails = [r for r in results if "before" in r.detail]
        assert ordering_fails, "Should fail due_date ordering"

    def test_due_date_equal_to_document_date_passes(self) -> None:
        doc = {"document_date": "2026-10-14", "service_date": None,
               "due_date": "2026-10-14", "cash_discount": None}
        results = check_v6(doc)
        ordering = [r for r in results if "due_date" in r.detail and ">=" in r.detail]
        assert any(r.passed for r in ordering)

    def test_null_optional_dates_skipped(self) -> None:
        # Null service_date must not cause a failure
        doc = {"document_date": "2026-10-12", "service_date": None,
               "due_date": None, "cash_discount": None}
        results = check_v6(doc)
        assert all(r.passed for r in results)

    def test_malformed_iso_string_fails(self) -> None:
        doc = {"document_date": "06.10.2026",  # German format, not ISO
               "service_date": None, "due_date": None, "cash_discount": None}
        results = check_v6(doc)
        assert any(not r.passed for r in results)

    def test_missing_document_date_fails(self) -> None:
        # document_date is required — absence must produce a FAIL, not empty list
        doc = {"service_date": None, "due_date": None, "cash_discount": None}
        results = check_v6(doc)
        assert results and not results[0].passed

    def test_empty_doc_fails(self) -> None:
        results = check_v6({})
        assert results and not results[0].passed


# ===========================================================================
# V7 — Sign consistency
# ===========================================================================

class TestV7:

    def test_inv03_credit_note_all_pass(self, inv03: dict) -> None:
        results = check_v7(inv03)
        assert all(r.passed for r in results), (
            "INV-03 V7 should pass — all monetary fields are negative"
        )

    def test_inv03_all_line_totals_negative(self, inv03: dict) -> None:
        results = check_v7(inv03)
        lt_results = [r for r in results if r.position is not None]
        assert all(r.actual < Decimal("0") for r in lt_results)

    def test_inv01_invoice_all_pass(self, inv01: dict) -> None:
        results = check_v7(inv01)
        assert all(r.passed for r in results)

    def test_inv02_invoice_all_pass(self, inv02: dict) -> None:
        results = check_v7(inv02)
        assert all(r.passed for r in results)

    def test_inv04_invoice_all_pass(self, inv04: dict) -> None:
        results = check_v7(inv04)
        assert all(r.passed for r in results)

    def test_inv05_invoice_all_pass(self, inv05: dict) -> None:
        results = check_v7(inv05)
        assert all(r.passed for r in results)

    def test_wrong_sign_line_total_fails(self) -> None:
        # Invoice with a negative line_total must fail V7
        doc = {
            "document_type": "invoice",
            "line_items": [
                {"position": 1, "line_total": Decimal("-100.00"), "vat_rate": 19}
            ],
            "totals": {
                "net_by_vat_rate": {"19": Decimal("100.00")},
                "vat_by_vat_rate": {"19": Decimal("19.00")},
                "net_total": Decimal("100.00"),
                "vat_total": Decimal("19.00"),
                "gross_total": Decimal("119.00"),
            },
        }
        results = check_v7(doc)
        lt_fail = next(r for r in results if r.position == 1)
        assert not lt_fail.passed

    def test_zero_line_total_fails(self) -> None:
        # Zero is neither positive nor negative — must fail
        doc = {
            "document_type": "invoice",
            "line_items": [
                {"position": 1, "line_total": Decimal("0.00"), "vat_rate": 19}
            ],
            "totals": {
                "net_by_vat_rate": {"19": Decimal("0.00")},
                "vat_by_vat_rate": {"19": Decimal("0.00")},
                "net_total": Decimal("0.00"),
                "vat_total": Decimal("0.00"),
                "gross_total": Decimal("0.00"),
            },
        }
        results = check_v7(doc)
        assert any(not r.passed for r in results)

    def test_positive_quantity_on_credit_note_not_checked(self, inv03: dict) -> None:
        # All V7 results should pass for INV-03.
        # If quantity were checked, some items would fail (quantities are positive).
        results = check_v7(inv03)
        assert all(r.passed for r in results), (
            "Positive quantities on credit notes must NOT cause V7 failures"
        )

    def test_cash_discount_amount_not_checked(self, inv01: dict) -> None:
        # V7 should not include any result referencing cash_discount
        results = check_v7(inv01)
        assert not any("cash_discount" in r.detail for r in results)

    def test_unknown_document_type_fails(self) -> None:
        doc = {
            "document_type": "unknown",
            "line_items": [],
            "totals": {},
        }
        results = check_v7(doc)
        assert results and not results[0].passed

    def test_empty_line_items_invoice_totals_still_checked(self) -> None:
        doc = {
            "document_type": "invoice",
            "line_items": [],
            "totals": {
                "net_by_vat_rate": {"19": Decimal("100.00")},
                "vat_by_vat_rate": {"19": Decimal("19.00")},
                "net_total": Decimal("100.00"),
                "vat_total": Decimal("19.00"),
                "gross_total": Decimal("119.00"),
            },
        }
        results = check_v7(doc)
        assert all(r.passed for r in results)


# ===========================================================================
# V7 — missing monetary groups do not disappear silently
# ===========================================================================

class TestV7MissingGroups:
    """V7 must not silently skip documents with empty or missing totals."""

    def test_no_line_items_totals_still_checked(self) -> None:
        # An invoice with empty line_items but valid totals should have
        # totals-field results (they can still be positive/negative).
        doc = {
            "document_type": "invoice",
            "line_items": [],
            "totals": {
                "net_by_vat_rate": {"19": Decimal("100.00")},
                "vat_by_vat_rate": {"19": Decimal("19.00")},
                "net_total":  Decimal("100.00"),
                "vat_total":  Decimal("19.00"),
                "gross_total": Decimal("119.00"),
            },
        }
        results = check_v7(doc)
        # Totals are positive → all pass
        assert results, "V7 must produce results even with empty line_items"
        assert all(r.passed for r in results)

    def test_missing_totals_dict_still_returns_results(self) -> None:
        # An invoice with no totals key at all.
        doc = {
            "document_type": "invoice",
            "line_items": [
                {"position": 1, "line_total": Decimal("100.00"), "vat_rate": 19}
            ],
        }
        results = check_v7(doc)
        # The line_total check should fire; totals checks with missing dicts
        # should not cause a crash — they simply produce no VAT-dict results.
        assert any(r.position == 1 for r in results)
