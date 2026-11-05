"""
tests/test_financials.py

Unit tests for helpers.financials.round_financial and amounts_match.

All financial values use Decimal, never float literals.
Test cases are drawn from the Phase 3 approved plan and from
actual invoice values found in INV-01 through INV-04.

How to run:
    source .venv/bin/activate
    pytest tests/test_financials.py -v
"""

from decimal import Decimal

import pytest

from helpers.financials import amounts_match, round_financial


# ===========================================================================
# round_financial — 6 tests
# ===========================================================================

class TestRoundFinancial:
    """Verify ROUND_HALF_UP behaviour and correct 2-decimal-place output."""

    def test_halfway_rounds_up(self) -> None:
        # 144.965 is exactly halfway between 144.96 and 144.97.
        # ROUND_HALF_UP sends it away from zero → 144.97.
        # Python's default rounding (ROUND_HALF_EVEN) would give 144.96
        # because 6 is even.  Suppliers use ROUND_HALF_UP.
        assert round_financial(Decimal("144.965")) == Decimal("144.97")

    def test_below_halfway_rounds_down(self) -> None:
        # 144.964 is closer to 144.96 than 144.97 → rounds down.
        assert round_financial(Decimal("144.964")) == Decimal("144.96")

    def test_already_two_decimal_places(self) -> None:
        # INV-01 net total: 202.80 is already at 2 dp — value unchanged.
        assert round_financial(Decimal("202.80")) == Decimal("202.80")

    def test_negative_amount_extra_places(self) -> None:
        # INV-03 credit-note line total stored with extra precision.
        # -225.800 → -225.80 (trailing zero collapsed to 2 dp).
        assert round_financial(Decimal("-225.800")) == Decimal("-225.80")

    def test_zero(self) -> None:
        # Zero should round cleanly to 0.00.
        assert round_financial(Decimal("0.000")) == Decimal("0.00")

    def test_negative_halfway_rounds_away_from_zero(self) -> None:
        # ROUND_HALF_UP means "away from zero".
        # For a negative number, away from zero is MORE negative.
        # -144.965 → -144.97 (not -144.96).
        # This is the expected behaviour for credit-note calculations.
        assert round_financial(Decimal("-144.965")) == Decimal("-144.97")


# ===========================================================================
# amounts_match — 7 tests
# ===========================================================================

class TestAmountsMatch:
    """Verify tolerance comparison with Decimal arithmetic only."""

    def test_equal_values_match(self) -> None:
        # INV-01 V4: 801.47 + 152.28 = 953.75 printed.  Both sides equal.
        assert amounts_match(Decimal("801.47"), Decimal("801.47")) is True

    def test_difference_exactly_at_tolerance_matches(self) -> None:
        # A difference of exactly 0.01 is within ±0.01 (the <= boundary).
        # 801.47 vs 801.46: diff = 0.01 → must be True.
        assert amounts_match(Decimal("801.47"), Decimal("801.46")) is True

    def test_difference_exceeds_tolerance_fails(self) -> None:
        # 801.47 vs 801.45: diff = 0.02 > 0.01 → False.
        assert amounts_match(Decimal("801.47"), Decimal("801.45")) is False

    def test_inv04_pos7_document_error_fails(self) -> None:
        # INV-04 Pos 7: printed line total 1284.52, calculated 26 × 48.02 = 1248.52.
        # Difference = 36.00 — this is the document-originated arithmetic error.
        # V1 must report FAIL.  amounts_match must return False here.
        assert amounts_match(Decimal("1284.52"), Decimal("1248.52")) is False

    def test_equal_negative_amounts_match(self) -> None:
        # INV-03 credit note: both sides are -225.80.
        assert amounts_match(Decimal("-225.80"), Decimal("-225.80")) is True

    def test_custom_tolerance_within_range(self) -> None:
        # With tolerance=0.05: diff of 0.04 is within range → True.
        assert amounts_match(
            Decimal("5.00"),
            Decimal("5.04"),
            tolerance=Decimal("0.05"),
        ) is True

    def test_negative_tolerance_raises_value_error(self) -> None:
        # A negative tolerance is nonsensical: abs(a-b) >= 0 always,
        # so it could never be satisfied and would silently always return False.
        with pytest.raises(ValueError):
            amounts_match(
                Decimal("100.00"),
                Decimal("100.00"),
                tolerance=Decimal("-0.01"),
            )
