"""
helpers/financials.py

Decimal-based rounding and tolerance-comparison utilities for financial values.

Two rules govern when each function applies:

  round_financial  — for CALCULATED or DERIVED monetary amounts only.
                     Never apply to raw printed values or to unit_price.
                     INV-05 Pos 3 unit_price is 0.152 and must stay 0.152.

  amounts_match    — for comparing two Decimal amounts within a tolerance.
                     Used by every V1–V4 validation check.

Neither function contains any Kessler-specific invoice logic.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# The target precision object used by quantize().
# Decimal("0.01") acts as a template: "give me a result with exactly 2 dp."
# Defined once at module level so it is not recreated on every call.
# ---------------------------------------------------------------------------
_TWO_PLACES = Decimal("0.01")

# ---------------------------------------------------------------------------
# Zero as a Decimal, used for tolerance validation.
# ---------------------------------------------------------------------------
_ZERO = Decimal("0")


def round_financial(value: Decimal) -> Decimal:
    """Round a Decimal to exactly 2 decimal places using ROUND_HALF_UP.

    Use this function only for calculated or derived monetary amounts
    (e.g. the V1 expected comparator, or a derived net_total).  Never
    apply it to raw printed values or to unit_price — those must be
    stored exactly as extracted from the document.

    ROUND_HALF_UP rounds halfway cases away from zero, matching the
    convention used by suppliers when printing invoice totals:
        Decimal("144.965") → Decimal("144.97")   (away from zero)
        Decimal("-144.965") → Decimal("-144.97")  (away from zero = more negative)

    Args:
        value: A Decimal to be rounded.

    Returns:
        A Decimal with exactly 2 decimal places.

    Examples:
        >>> round_financial(Decimal("144.965"))
        Decimal('144.97')
        >>> round_financial(Decimal("-225.800"))
        Decimal('-225.80')
    """
    # quantize() rounds `value` to the precision expressed by _TWO_PLACES.
    # Decimal("0.01") means "two decimal places".
    # ROUND_HALF_UP is the standard "school" rounding rule used by suppliers.
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    """quantize rounds value to match the precision of _TWO_PLACES. 
    The rounding=ROUND_HALF_UP argument overrides Python's default ROUND_HALF_EVEN. 
    Without it, Decimal("144.965") would round to 144.96 (because 6 is even) — the 
    wrong result for invoice arithmetic.

    Why quantize instead of round(value, 2)? Python's built-in round() uses ROUND_HALF_EVEN and 
    does not accept a Decimal rounding mode argument. quantize is the correct, explicit way 
    to control both the precision and the rounding rule at the same time.

    Why never on unit_price? INV-05 Pos 3 has unit_price = Decimal("0.152"). 
    Applying round_financial would produce Decimal("0.15") — a silent correction 
    of a printed value, violating BR-01. This function is only for calculated amounts 
    like qty × unit_price / price_unit × (1 − discount).
    """

def amounts_match(
    a: Decimal,
    b: Decimal,
    tolerance: Decimal = Decimal("0.01"),
) -> bool:
    """Return True when the absolute difference between a and b is within tolerance.

    The comparison is:  abs(a - b) <= tolerance

    Using <= (less than OR EQUAL) means a difference exactly equal to the
    tolerance still counts as a match.  The assignment specifies "within ±0.01",
    so a difference of exactly 0.01 must pass.

    The default tolerance of Decimal("0.01") matches the assignment requirement
    for checks V1–V4.  Pass a different tolerance only when explicitly required.

    Args:
        a:         First Decimal amount.
        b:         Second Decimal amount.
        tolerance: Maximum allowed absolute difference.  Must be non-negative.
                   Defaults to Decimal("0.01").

    Returns:
        True  if abs(a - b) <= tolerance.
        False if abs(a - b) >  tolerance.

    Raises:
        ValueError: If tolerance is negative.

    Examples:
        >>> amounts_match(Decimal("801.47"), Decimal("801.47"))
        True
        >>> amounts_match(Decimal("1284.52"), Decimal("1248.52"))  # INV-04 Pos 7
        False
    """
    # Reject nonsensical tolerance before doing any arithmetic.
    # abs(a - b) is always >= 0, so a negative tolerance could never be
    # satisfied and would silently produce wrong FAIL results everywhere.
    if tolerance < _ZERO:
        raise ValueError(
            f"tolerance must be non-negative, got {tolerance!r}"
        )

    # abs() gives the distance between the two values regardless of order.
    # We do not round a or b before comparing — that is the caller's job
    # if rounding is needed.  This function compares the values as given.
    return abs(a - b) <= tolerance
    """a - b gives the signed difference. abs(...) removes the sign — the result is always ≥ 0, 
    so the order of a and b does not matter. <= (not <) implements the "within ±0.01" spec: a difference 
    of exactly 0.01 is still a match.

    Why <=? The assignment says "within ±0.01". At the boundary (diff = 0.01), rounding a 
    printed value that is off by exactly one cent should still pass. The < operator would 
    incorrectly reject the boundary case.

    Why two separate functions? round_financial is about transforming a value (producing a 
    new rounded value). amounts_match is about comparing two existing values. These are 
    different operations with different callers — the validator calls amounts_match; the 
    calculator calls round_financial. Mixing them into one function would make each harder 
    to test, understand, and reuse.
    """