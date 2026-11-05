"""
tests/test_numbers.py

Unit tests for helpers.numbers.parse_german_number.

Test cases are drawn directly from the Phase 2 invoice analysis:
  - Actual values extracted from INV-01 through INV-05.
  - Edge cases identified in the Phase 3 approved plan.

How to run:
    source .venv/bin/activate
    pytest tests/test_numbers.py -v
"""

from decimal import Decimal

import pytest

from helpers.numbers import parse_german_number


# ===========================================================================
# Helpers
# ===========================================================================

def parse(text: str) -> Decimal:
    """Thin wrapper so test lines stay short."""
    return parse_german_number(text)


# ===========================================================================
# Normal cases — values that must parse successfully
# ===========================================================================

class TestNormalCases:
    """Values drawn from actual Kessler invoice extractions."""

    def test_simple_two_decimal(self) -> None:
        # INV-01 Pos 1 Gesamt: 202,80
        assert parse("202,80") == Decimal("202.80")

    def test_thousand_separator_with_decimal(self) -> None:
        # INV-02 totals: 1.234,56 pattern
        assert parse("1.234,56") == Decimal("1234.56")

    def test_thousand_separator_no_decimal(self) -> None:
        # INV-02 Pos 30 Menge: 1.000 → quantity 1000
        assert parse("1.000") == Decimal("1000")

    def test_large_amount_with_thousand_separator(self) -> None:
        # INV-02 net 19%: 4.787,18
        assert parse("4.787,18") == Decimal("4787.18")

    def test_fractional_quantity(self) -> None:
        # INV-02 Pos 70 Menge: 12,5 (metres of hose)
        assert parse("12,5") == Decimal("12.5")

    def test_trailing_minus_credit_note(self) -> None:
        # INV-03 Pos 1 Gesamt: 225,80-
        assert parse("225,80-") == Decimal("-225.80")

    def test_trailing_minus_totals(self) -> None:
        # INV-03 Nettobetrag: 400,05-
        assert parse("400,05-") == Decimal("-400.05")

    def test_trailing_minus_small_amount(self) -> None:
        # INV-03 Pos 3 Gesamt: 19,25- (PE=100)
        assert parse("19,25-") == Decimal("-19.25")

    def test_leading_minus(self) -> None:
        # Standard minus prefix notation
        assert parse("-225,80") == Decimal("-225.80")

    def test_three_decimal_places(self) -> None:
        # INV-05 Pos 3 unit price: 0,152 € per piece
        assert parse("0,152") == Decimal("0.152")

    def test_euro_suffix(self) -> None:
        # INV-05 prices include the € symbol: "14,60 €"
        assert parse("14,60 €") == Decimal("14.60")

    def test_percent_suffix(self) -> None:
        # INV-01/02 VAT rate column reads "19" but INV-05 column reads "19%"
        assert parse("19%") == Decimal("19")

    def test_whitespace_around_value(self) -> None:
        # Extracted text often has leading/trailing spaces
        assert parse("  8,45  ") == Decimal("8.45")

    def test_whitespace_between_value_and_euro(self) -> None:
        # "14,60 €" — space between number and symbol
        assert parse("14,60 €") == Decimal("14.60")

    def test_integer_no_decimal(self) -> None:
        # Simple integer quantity
        assert parse("24") == Decimal("24")

    def test_unit_price_two_decimal(self) -> None:
        # INV-01 Pos 2 unit price: 1,92
        assert parse("1,92") == Decimal("1.92")

    def test_gross_total_large(self) -> None:
        # INV-02 Rechnungsbetrag: 6.037,86
        assert parse("6.037,86") == Decimal("6037.86")

    def test_gross_total_with_trailing_eur(self) -> None:
        # In some contexts "953,75 EUR" or "953,75€" may appear
        # The function handles € but not the multi-char "EUR" — that is
        # a parser responsibility.  Test the € case.
        assert parse("953,75€") == Decimal("953.75")

    def test_vat_amount(self) -> None:
        # INV-01 VAT: 152,28
        assert parse("152,28") == Decimal("152.28")

    def test_zero(self) -> None:
        # Zero should parse cleanly
        assert parse("0") == Decimal("0")

    def test_zero_with_decimal(self) -> None:
        assert parse("0,00") == Decimal("0.00")

    def test_negative_zero_trailing(self) -> None:
        # Edge case: "-0,00" from a zero-value credit note line
        # Decimal("-0") is valid and finite
        assert parse("0,00-") == Decimal("0.00") or parse("0,00-") == Decimal("-0.00")
        # Either representation is acceptable; the important thing is no exception

    def test_quantity_fractional_metres(self) -> None:
        # INV-03 Pos 2 Menge: 12,5 m (hydraulic hose)
        assert parse("12,5") == Decimal("12.5")

    def test_large_thousand_separator_quantity(self) -> None:
        # INV-04 Pos 3 Menge: 1.000 Stk
        assert parse("1.000") == Decimal("1000")

    def test_large_quantity_1500(self) -> None:
        # INV-02 Pos 160 Menge: 1.500
        assert parse("1.500") == Decimal("1500")


# ===========================================================================
# Decimal precision — values must NOT be rounded inside the function
# ===========================================================================

class TestPrecision:
    """Verify that arbitrary precision is preserved."""

    def test_three_decimal_precision_preserved(self) -> None:
        result = parse("0,152")
        # Must be exactly 0.152 — not 0.15 or 0.16
        assert result == Decimal("0.152")
        # Confirm the decimal places are preserved
        assert str(result) == "0.152"

    def test_no_rounding_occurs(self) -> None:
        # 144,965 should not become 144.97 or 144.96 — that is financials' job
        result = parse("144,965")
        assert result == Decimal("144.965")

    def test_result_is_decimal_not_float(self) -> None:
        result = parse("202,80")
        assert isinstance(result, Decimal), (
            f"Expected Decimal, got {type(result).__name__}"
        )


# ===========================================================================
# Sign handling
# ===========================================================================

class TestSignHandling:
    """Verify sign detection for both notations."""

    def test_positive_has_no_sign(self) -> None:
        assert parse("100,00") > Decimal("0")

    def test_trailing_minus_is_negative(self) -> None:
        assert parse("100,00-") < Decimal("0")

    def test_leading_minus_is_negative(self) -> None:
        assert parse("-100,00") < Decimal("0")

    def test_trailing_minus_magnitude(self) -> None:
        # The magnitude must be the same as the positive version
        assert abs(parse("225,80-")) == parse("225,80")

    def test_leading_minus_magnitude(self) -> None:
        assert abs(parse("-225,80")) == parse("225,80")


# ===========================================================================
# Error cases — inputs that must raise ValueError
# ===========================================================================

class TestErrorCases:
    """Malformed or ambiguous inputs that must be rejected."""

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError):
            parse("")

    def test_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            parse("   ")

    def test_non_numeric_string(self) -> None:
        # "KW 42/2026" appears in INV-04 header — must never be passed here
        with pytest.raises(ValueError):
            parse("KW 42/2026")

    def test_malformed_grouping_two_digits(self) -> None:
        # "1.23" — the '.' is followed by only 2 digits, not 3
        # This is ambiguous in German notation and must be rejected
        with pytest.raises(ValueError):
            parse("1.23")

    def test_malformed_grouping_four_digits(self) -> None:
        # "1.2345" — four digits after the dot, not a valid thousands group
        with pytest.raises(ValueError):
            parse("1.2345")

    def test_conflicting_signs(self) -> None:
        # Both leading and trailing minus — nonsensical
        with pytest.raises(ValueError):
            parse("-225,80-")

    def test_double_thousands_group_irregular(self) -> None:
        # "1.2.345,67" — first group has only 1 digit, second has 3
        with pytest.raises(ValueError):
            parse("1.2.345,67")

    def test_suffix_only_euro(self) -> None:
        # "€" alone with nothing before it
        with pytest.raises(ValueError):
            parse("€")

    def test_suffix_only_percent(self) -> None:
        with pytest.raises(ValueError):
            parse("%")

    def test_minus_only(self) -> None:
        # "-" is not a number
        with pytest.raises(ValueError):
            parse("-")

    def test_text_with_letters(self) -> None:
        with pytest.raises(ValueError):
            parse("abc")

    def test_plain_decimal_point(self) -> None:
        # "1.5" — in German notation this would mean 15 (no decimal),
        # but "1.5" has only one digit after the dot, so our validator
        # rejects it as malformed grouping (not exactly 3 digits)
        with pytest.raises(ValueError):
            parse("1.5")

    def test_multiple_commas(self) -> None:
        # "1,2,3" — two decimal commas is not valid
        with pytest.raises(ValueError):
            parse("1,2,3")


# ===========================================================================
# Ungrouped integers — four or more digits without thousands separators
# These were incorrectly rejected by the old regex pattern.
# ===========================================================================

class TestUngroupedIntegers:
    """Four-or-more digit integers with no thousands separators are valid."""

    def test_ungrouped_four_digit_integer(self) -> None:
        # "1234" — valid ungrouped integer; old pattern rejected this
        assert parse("1234") == Decimal("1234")

    def test_ungrouped_four_digit_with_decimal(self) -> None:
        # "1234,56" — valid ungrouped with decimal part
        assert parse("1234,56") == Decimal("1234.56")

    def test_ungrouped_five_digit_with_decimal(self) -> None:
        # "12345,67" — five integer digits, no grouping
        assert parse("12345,67") == Decimal("12345.67")

    def test_double_thousand_group(self) -> None:
        # "1.234.567" — two correctly formed thousands groups
        assert parse("1.234.567") == Decimal("1234567")

    def test_malformed_four_digit_with_dot(self) -> None:
        # "1234.567" — looks like it could be grouped but "1234" has
        # 4 leading digits; neither branch of the new pattern matches
        with pytest.raises(ValueError):
            parse("1234.567")

    def test_malformed_two_digits_after_dot(self) -> None:
        # "1.23" — 2 digits after the dot, already tested above
        # repeated here to confirm the new pattern still rejects it
        with pytest.raises(ValueError):
            parse("1.23")

    def test_malformed_four_digits_after_dot(self) -> None:
        # "12.3456" — 4 digits after the dot
        with pytest.raises(ValueError):
            parse("12.3456")
