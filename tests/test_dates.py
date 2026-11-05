"""
tests/test_dates.py

Unit tests for helpers.dates.parse_german_date and add_days.

All test cases correspond to actual date formats found in INV-01 through INV-05,
plus boundary conditions from the approved Phase 3 plan.

How to run:
    source .venv/bin/activate
    pytest tests/test_dates.py -v
"""

import pytest

from helpers.dates import add_days, parse_german_date


# ===========================================================================
# parse_german_date — short format (DD.MM.YYYY)
# ===========================================================================

class TestShortFormat:
    """Short date format: DD.MM.YYYY"""

    def test_inv01_document_date(self) -> None:
        # INV-01 Datum: 06.10.2026
        assert parse_german_date("06.10.2026") == "2026-10-06"

    def test_inv02_document_date(self) -> None:
        # INV-02 Datum: 09.10.2026
        assert parse_german_date("09.10.2026") == "2026-10-09"

    def test_single_digit_day(self) -> None:
        # The short-format regex allows 1 or 2 digit days.
        # A day without a leading zero must still parse correctly.
        assert parse_german_date("5.03.2026") == "2026-03-05"

    def test_leading_trailing_whitespace(self) -> None:
        # Extracted text often has surrounding spaces.
        assert parse_german_date("  06.10.2026  ") == "2026-10-06"


# ===========================================================================
# parse_german_date — long format (D. Monatname YYYY)
# ===========================================================================

class TestLongFormat:
    """Long German date format: D. Monatname YYYY"""

    def test_inv05_document_date(self) -> None:
        # INV-05 Rechnungsdatum: 19. Oktober 2026
        assert parse_german_date("19. Oktober 2026") == "2026-10-19"

    def test_inv05_due_date(self) -> None:
        # INV-05 payment terms: 18. November 2026
        assert parse_german_date("18. November 2026") == "2026-11-18"

    def test_inv05_service_date(self) -> None:
        # INV-05 Lieferdatum: 16. Oktober 2026
        assert parse_german_date("16. Oktober 2026") == "2026-10-16"

    def test_umlaut_month_märz(self) -> None:
        # März contains the umlaut ä — must be in the month map and match.
        assert parse_german_date("1. März 2026") == "2026-03-01"

    def test_lowercase_month_name(self) -> None:
        # Case-insensitive: "oktober" must match the same as "Oktober".
        assert parse_german_date("19. oktober 2026") == "2026-10-19"

    def test_uppercase_month_name(self) -> None:
        # All-caps month name must also be handled.
        assert parse_german_date("19. OKTOBER 2026") == "2026-10-19"

    def test_long_format_whitespace_stripped(self) -> None:
        # Surrounding whitespace stripped before matching.
        assert parse_german_date("  18. November 2026  ") == "2026-11-18"


# ===========================================================================
# parse_german_date — error cases
# ===========================================================================

class TestParseDateErrors:
    """Inputs that must raise ValueError."""

    def test_impossible_date_feb_31(self) -> None:
        # 31 February does not exist; datetime.date validates this.
        with pytest.raises(ValueError):
            parse_german_date("31.02.2026")

    def test_invalid_month_name(self) -> None:
        # "Octember" is not in the German month map.
        with pytest.raises(ValueError):
            parse_german_date("19. Octember 2026")

    def test_unrecognised_format(self) -> None:
        # A completely unrecognised string must raise ValueError.
        with pytest.raises(ValueError):
            parse_german_date("not a date")

    def test_trailing_unrelated_content_rejected(self) -> None:
        # re.fullmatch() rejects anything after the date.
        # "06.10.2026 extra" must not match the short-format pattern.
        with pytest.raises(ValueError):
            parse_german_date("06.10.2026 extra content")


# ===========================================================================
# add_days
# ===========================================================================

class TestAddDays:
    """Calendar-day addition, including boundary cases."""

    def test_inv04_skonto_derivation(self) -> None:
        # INV-04 Skonto: document date 2026-10-14 plus 7 days.
        # This is the standard test case for the relative-term interpretation.
        assert add_days("2026-10-14", 7) == "2026-10-21"

    def test_month_boundary(self) -> None:
        # Adding days that cross a month boundary.
        assert add_days("2026-10-31", 5) == "2026-11-05"

    def test_year_boundary(self) -> None:
        # Adding days that cross a year boundary.
        assert add_days("2026-12-30", 5) == "2027-01-04"

    def test_invalid_iso_date_raises(self) -> None:
        # A string that is not a valid ISO date must raise ValueError.
        with pytest.raises(ValueError):
            add_days("not-a-date", 7)
