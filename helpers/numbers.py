"""
helpers/numbers.py

Converts German-formatted number strings to Decimal values.

German number format rules used in Kessler invoices:
  - Thousands separator: period '.'  e.g. 1.234 means one thousand two hundred thirty-four
  - Decimal separator:   comma ','  e.g. 1.234,56 means 1234.56
  - Credit-note amounts: trailing minus  e.g. 225,80-  means -225.80
  - INV-05 values carry a trailing € or % symbol that must be stripped first.

This module contains no invoice-specific layout logic.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------------------------
# Regex that describes a valid unsigned German number string after suffix
# and sign stripping.
#
# Pattern:  r"^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?$"
#
# The integer part uses an alternation — two mutually exclusive branches:
#
#   Branch A:  \d+
#       One or more digits with NO thousands dots at all.
#       Accepts ungrouped integers of any length: "0", "24", "1234", "12345".
#       The old pattern (\d{1,3}) only allowed up to 3 leading digits, which
#       incorrectly rejected valid ungrouped values like "1234" or "1234,56".
#
#   Branch B:  \d{1,3}(?:\.\d{3})+
#       Grouped-thousands format: 1-3 leading digits, then ONE OR MORE groups
#       of (a dot + exactly three digits).  The + requires at least one group.
#       Accepts:  "1.000"  "1.234,56"  "4.787,18"  "1.234.567"
#       Rejects:  "1.23"    (2 digits after dot — not a valid thousands group)
#                 "12.3456" (4 digits after dot)
#                 "1234.567"(4 leading digits exceed \d{1,3} in branch B;
#                             branch A matches "1234" but ".567" is left
#                             unconsumed, so fullmatch() still fails)
#
#   Optional decimal:  (?:,\d+)?
#       A comma followed by one or more digits.  Applies to either branch.
#
# Accepted:  "0"  "24"  "202,80"  "12,5"  "1.000"  "1.234,56"  "4.787,18"
#            "0,152"  "1234"  "1234,56"  "12345,67"  "1.234.567"
# Rejected:  "1.23"  "12.3456"  "1234.567"  "1.2.345"  "1,2,3"
# ---------------------------------------------------------------------------
_GERMAN_NUMBER_PATTERN = re.compile(
    r"^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?$"
)


def parse_german_number(text: str) -> Decimal:
    """Convert a German-formatted number string to a Decimal.

    Handles all number formats found in Kessler invoices:
      "202,80"     -> Decimal("202.80")
      "1.234,56"   -> Decimal("1234.56")
      "1.000"      -> Decimal("1000")
      "12,5"       -> Decimal("12.5")
      "225,80-"    -> Decimal("-225.80")   trailing-minus (credit notes)
      "-225,80"    -> Decimal("-225.80")   leading minus
      "0,152"      -> Decimal("0.152")     three decimal places preserved
      "14,60 €"    -> Decimal("14.60")     € symbol stripped
      "19%"        -> Decimal("19")        % symbol stripped

    Args:
        text: Raw number string as extracted from a Kessler PDF.

    Returns:
        An exact Decimal representation.  Never rounded.

    Raises:
        ValueError: For any of these conditions:
            - Empty string (before or after stripping)
            - Conflicting leading and trailing minus signs
            - Malformed thousands grouping (e.g. "1.23")
            - String that cannot be parsed as a Decimal
            - Non-finite result (Infinity, NaN)
    """
    # ------------------------------------------------------------------
    # Stage 1: strip surrounding whitespace
    # ------------------------------------------------------------------
    working = text.strip()

    # ------------------------------------------------------------------
    # Stage 2: strip trailing suffix symbols (€, %) and adjacent spaces.
    # Loop so that "14,60 € " (space after symbol) is handled correctly.
    # rstrip removes characters from the right end in any order/quantity.
    # ------------------------------------------------------------------
    while working.endswith(("€", "%", " ")):
        working = working.rstrip("€% ")

    # ------------------------------------------------------------------
    # Stage 3: detect and record sign; reject conflicting signs.
    # Leading minus: "-225,80"
    # Trailing minus: "225,80-"  (German credit-note convention, INV-03)
    # ------------------------------------------------------------------
    has_leading  = working.startswith("-")
    has_trailing = working.endswith("-")

    if has_leading and has_trailing:
        # e.g. "-225,80-" — both signs present, which is invalid
        raise ValueError(
            f"Conflicting signs in number string: {text!r}"
        )

    negative = has_leading or has_trailing

    # Strip whichever sign is present so the remaining string is unsigned.
    if has_leading:
        working = working[1:]   # remove the leading '-'
    if has_trailing:
        working = working[:-1]  # remove the trailing '-'

    # ------------------------------------------------------------------
    # Stage 4: reject empty string after all stripping so far.
    # Catches inputs like "", "  ", "€", "-" or "-€".
    # ------------------------------------------------------------------
    if not working:
        raise ValueError(
            f"Number string is empty after stripping: {text!r}"
        )

    # ------------------------------------------------------------------
    # Stage 5: validate German thousands grouping.
    # re.fullmatch() requires the ENTIRE string to match the pattern.
    # This rejects "1.23" (only 2 digits after the dot — ambiguous),
    # "1.2.345" (irregular grouping), "abc", etc.
    # ------------------------------------------------------------------
    if not _GERMAN_NUMBER_PATTERN.fullmatch(working):
        raise ValueError(
            f"Malformed German number string: {text!r}  "
            f"(stripped: {working!r})"
        )

    # ------------------------------------------------------------------
    # Stage 6: remove validated thousands separators.
    # At this point every '.' is confirmed to be a thousands separator.
    # "1.234,56" -> "1234,56"
    # "1.000"    -> "1000"
    # ------------------------------------------------------------------
    working = working.replace(".", "")

    # ------------------------------------------------------------------
    # Stage 7: replace decimal comma with decimal point.
    # "1234,56" -> "1234.56"
    # "1000"    -> "1000"   (no comma = integer, no change)
    # ------------------------------------------------------------------
    working = working.replace(",", ".")

    # ------------------------------------------------------------------
    # Stage 8: construct Decimal.
    # Decimal(string) is exact — no binary rounding.
    # InvalidOperation is raised by Decimal for strings it cannot parse
    # (e.g. multiple decimal points slipping through somehow).
    # ------------------------------------------------------------------
    try:
        result = Decimal(working)
    except InvalidOperation:
        raise ValueError(
            f"Cannot construct Decimal from: {text!r}  "
            f"(normalised: {working!r})"
        ) from None

    # ------------------------------------------------------------------
    # Stage 9: reject non-finite values.
    # Decimal("Infinity") and Decimal("NaN") are valid Decimal objects
    # but are not meaningful invoice amounts.
    # ------------------------------------------------------------------
    if not result.is_finite():
        raise ValueError(
            f"Non-finite Decimal value from: {text!r}"
        )

    # ------------------------------------------------------------------
    # Stage 10: apply sign and return.
    # Never round here — callers that need 2dp rounding use
    # helpers.financials.round_financial().
    # ------------------------------------------------------------------
    return -result if negative else result
