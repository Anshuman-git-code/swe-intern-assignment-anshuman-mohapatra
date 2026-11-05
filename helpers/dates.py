"""
helpers/dates.py

Converts German date strings to ISO 8601 (YYYY-MM-DD) and provides a
calendar-day-addition helper.

Two date formats appear in Kessler invoices:
  Short:    DD.MM.YYYY          e.g. "06.10.2026"
  Long:     D. Monatname YYYY   e.g. "19. Oktober 2026"

This module contains no invoice-specific layout or Skonto logic.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# German month name → month number.
# Keys are lowercase so we can match any capitalisation by calling .lower().
# ---------------------------------------------------------------------------
_GERMAN_MONTHS: dict[str, int] = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

# ---------------------------------------------------------------------------
# Short format: DD.MM.YYYY  (day may be 1 or 2 digits)
# Named groups make extraction readable.
# ---------------------------------------------------------------------------
_SHORT_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\.(?P<month>\d{2})\.(?P<year>\d{4})"
)

# ---------------------------------------------------------------------------
# Long German format: D. Monatname YYYY
# \w+ matches the month name (letters only in German month names, except ä/ö/ü
# which \w covers in Python's Unicode-aware regex).
# re.IGNORECASE handles Oktober / oktober / OKTOBER.
# ---------------------------------------------------------------------------
_LONG_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\.\s+(?P<month_name>\w+)\s+(?P<year>\d{4})",
    re.IGNORECASE,
)


def parse_german_date(text: str) -> str:
    """Convert a German date string to ISO 8601 format (YYYY-MM-DD).

    Supports two formats found in Kessler invoices:
      - Short:  "06.10.2026"        →  "2026-10-06"
      - Long:   "19. Oktober 2026"  →  "2026-10-19"

    Surrounding whitespace is stripped before matching.
    Month names are case-insensitive ("oktober" and "OKTOBER" both work).
    The date is validated as a real calendar date; impossible dates such as
    31 February raise ValueError.

    Args:
        text: A German date string in either recognised format.

    Returns:
        A string in ISO 8601 format: YYYY-MM-DD.

    Raises:
        ValueError: Unrecognised format, unknown month name, or impossible date.
    """
    stripped = text.strip()

    # ------------------------------------------------------------------
    # Try short format first: DD.MM.YYYY
    # re.fullmatch() requires the entire stripped string to match.
    # ------------------------------------------------------------------
    m = _SHORT_DATE_RE.fullmatch(stripped)
    if m:
        return _build_iso_date(
            day=int(m.group("day")),
            month=int(m.group("month")),
            year=int(m.group("year")),
            original=text,
        )

    # ------------------------------------------------------------------
    # Try long German format: D. Monatname YYYY
    # ------------------------------------------------------------------
    m = _LONG_DATE_RE.fullmatch(stripped)
    if m:
        month_name = m.group("month_name").lower()
        if month_name not in _GERMAN_MONTHS:
            raise ValueError(
                f"Unknown German month name: {m.group('month_name')!r} "
                f"(in date string: {text!r})"
            )
        return _build_iso_date(
            day=int(m.group("day")),
            month=_GERMAN_MONTHS[month_name],
            year=int(m.group("year")),
            original=text,
        )

    raise ValueError(
        f"Unrecognised date format: {text!r}. "
        "Expected 'DD.MM.YYYY' or 'D. Monatname YYYY'."
    )


def _build_iso_date(day: int, month: int, year: int, original: str) -> str:
    """Validate and format extracted day/month/year as an ISO date string.

    Delegates calendar validation to datetime.date, which raises ValueError
    automatically for impossible dates such as 31 February.

    Args:
        day:      Day of month as an integer.
        month:    Month number as an integer.
        year:     Year as an integer.
        original: Original input string — included in any error message.

    Returns:
        ISO date string YYYY-MM-DD.

    Raises:
        ValueError: If the date is not a valid calendar date.
    """
    try:
        # datetime.date raises ValueError for invalid calendar dates
        # (e.g. day=31, month=2 → "day is out of range for month").
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Invalid calendar date extracted from {original!r}: "
            f"day={day}, month={month}, year={year}. Original error: {exc}"
        ) from exc


def add_days(date_str: str, days: int) -> str:
    """Add a number of calendar days to an ISO date string.

    Handles month and year boundaries automatically via datetime.timedelta.
    This function is generic — it contains no Skonto or invoice-specific logic.
    The caller is responsible for documenting why they are adding a particular
    number of days (e.g. deriving a Skonto due date from a relative term).

    Args:
        date_str: An ISO 8601 date string (YYYY-MM-DD).
        days:     Number of calendar days to add. May be negative.

    Returns:
        A new ISO 8601 date string.

    Raises:
        ValueError: If date_str is not a valid ISO 8601 date.

    Example:
        add_days("2026-10-14", 7) → "2026-10-21"
        (Used by the extractor to derive INV-04's cash_discount.until from
         the printed term "innerhalb von 7 Tagen ab Rechnungsdatum".)
    """
    try:
        # date.fromisoformat() parses YYYY-MM-DD and validates the date.
        parsed = date.fromisoformat(date_str)
    except ValueError as exc:
        raise ValueError(
            f"Invalid ISO date string: {date_str!r}. Original error: {exc}"
        ) from exc

    return (parsed + timedelta(days=days)).isoformat()
