"""
validation/checks.py

Implements the seven validation checks V1–V7 as individual, testable functions.

All monetary arithmetic uses Decimal.  Never use float for comparisons.
Tolerance for monetary checks is exactly Decimal("0.01") per the assignment.

V7 scope (OQ-02 resolved):
  Checks line_total, net_by_vat_rate[*], vat_by_vat_rate[*],
  net_total, vat_total, gross_total.
  Excludes quantity, unit_price, price_unit, discount_percent,
  vat_rate, position, cash_discount.amount.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from helpers.financials import amounts_match, round_financial
from helpers.numbers import parse_german_number

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Carries the outcome of one check instance.

    Attributes:
        check_id:   "V1", "V2", … "V7"
        passed:     True = PASS, False = FAIL
        detail:     Human-readable description with values
        position:   Line-item position number, or None
        rate:       VAT rate string (e.g. "19"), or None
        expected:   Calculated/expected value, or None
        actual:     Printed/stored value, or None
        difference: abs(actual - expected) for monetary checks, or None
    """
    check_id:   str
    passed:     bool
    detail:     str
    position:   int | None = None
    rate:       str | None = None
    expected:   Any = None
    actual:     Any = None
    difference: Decimal | None = None

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOLERANCE = Decimal("0.01")
_ZERO      = Decimal("0")


def _d(value: Any) -> Decimal:
    """Convert a stored number to Decimal for arithmetic."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _is_invoice(doc: dict) -> bool:
    return doc.get("document_type") == "invoice"


def _is_credit_note(doc: dict) -> bool:
    return doc.get("document_type") == "credit_note"


# ---------------------------------------------------------------------------
# V1 — Line-item arithmetic check
# ---------------------------------------------------------------------------

def check_v1(doc: dict) -> list[CheckResult]:
    """V1: For every line item, qty × unit_price / price_unit × (1 − disc) == line_total.

    Sign convention:
      Invoice:     expected is positive.
      Credit note: expected is negated (quantity/unit_price remain positive).

    Unknown document_type produces an explicit FAIL result.
    Missing or empty line_items produces an explicit FAIL result.

    Returns one CheckResult per line item (or one FAIL for structural problems).
    """
    results: list[CheckResult] = []
    doc_type = doc.get("document_type", "")

    # Unknown document_type — cannot determine sign convention.
    if doc_type not in ("invoice", "credit_note"):
        return [CheckResult(
            check_id = "V1",
            passed   = False,
            detail   = (
                f"Cannot run V1: unknown document_type={doc_type!r}. "
                "Expected 'invoice' or 'credit_note'."
            ),
        )]

    line_items = doc.get("line_items")
    # Missing or empty line_items — required for invoice validation.
    if not line_items:
        return [CheckResult(
            check_id = "V1",
            passed   = False,
            detail   = "Cannot run V1: line_items is missing or empty.",
        )]

    sign = Decimal("-1") if doc_type == "credit_note" else Decimal("1")

    for item in line_items:
        pos       = item["position"]
        qty       = _d(item["quantity"])
        up        = _d(item["unit_price"])
        pu        = _d(item["price_unit"])
        disc_raw  = item.get("discount_percent")
        disc      = _d(disc_raw) / Decimal("100") if disc_raw is not None else _ZERO
        lt        = _d(item["line_total"])

        expected  = round_financial(sign * qty * up / pu * (Decimal("1") - disc))
        diff      = abs(lt - expected)
        passed    = amounts_match(lt, expected, _TOLERANCE)

        results.append(CheckResult(
            check_id   = "V1",
            passed     = passed,
            detail     = f"Pos {pos}: expected={expected} printed={lt} diff={diff}",
            position   = pos,
            expected   = expected,
            actual     = lt,
            difference = diff,
        ))

    return results


# ---------------------------------------------------------------------------
# V2 — Per-VAT-rate net total check
# ---------------------------------------------------------------------------

def check_v2(doc: dict, inv05_derived: bool = False) -> list[CheckResult]:
    """V2: For each VAT rate, sum(line_total) == net_by_vat_rate[rate].

    Field semantics:
      expected = calculated line-item sum for the VAT rate.
      actual   = stored/printed net_by_vat_rate value.

    Missing or empty line_items produces an explicit FAIL.
    Missing net_by_vat_rate groups produce an explicit FAIL per rate.

    Args:
        doc:           Parsed invoice dict.
        inv05_derived: When True, adds the INV-05 by-construction disclosure.

    Returns one CheckResult per VAT rate.
    """
    results: list[CheckResult] = []

    line_items = doc.get("line_items")
    if not line_items:
        return [CheckResult(
            check_id = "V2",
            passed   = False,
            detail   = "Cannot run V2: line_items is missing or empty.",
        )]

    net_by_vat = doc.get("totals", {}).get("net_by_vat_rate")
    if not net_by_vat:
        return [CheckResult(
            check_id = "V2",
            passed   = False,
            detail   = "Cannot run V2: totals.net_by_vat_rate is missing or empty.",
        )]

    # Build line-total sums grouped by VAT rate.
    sums: dict[str, Decimal] = {}
    for item in line_items:
        rate_key = str(item["vat_rate"])
        sums[rate_key] = sums.get(rate_key, _ZERO) + _d(item["line_total"])

    all_rates = sorted(set(sums) | set(net_by_vat))

    for rate in all_rates:
        line_sum    = sums.get(rate, _ZERO)
        printed_net = _d(net_by_vat[rate]) if rate in net_by_vat else None
        if printed_net is None:
            results.append(CheckResult(
                check_id = "V2",
                passed   = False,
                detail   = f"rate={rate}%: net_by_vat_rate key missing",
                rate     = rate,
            ))
            continue

        diff   = abs(line_sum - printed_net)
        passed = amounts_match(line_sum, printed_net, _TOLERANCE)
        suffix = ""
        if inv05_derived:
            suffix = (
                " [NOTE: net_by_vat_rate is derived from line items "
                "— V2 passes by construction, not against an "
                "independent printed per-rate net value]"
            )
        results.append(CheckResult(
            check_id   = "V2",
            passed     = passed,
            detail     = (
                f"rate={rate}%: line_sum={line_sum} "
                f"net={printed_net} diff={diff}{suffix}"
            ),
            rate       = rate,
            expected   = line_sum,    # calculated line-item sum
            actual     = printed_net, # stored/printed net
            difference = diff,
        ))

    return results


# ---------------------------------------------------------------------------
# V3 — VAT amount check
# ---------------------------------------------------------------------------

def check_v3(doc: dict) -> list[CheckResult]:
    """V3: For each VAT rate, net_by_vat_rate[rate] × rate/100 == vat_by_vat_rate[rate].

    Missing or empty net/VAT rate groups produce an explicit FAIL.
    """
    results: list[CheckResult] = []
    totals     = doc.get("totals", {})
    net_by_vat = totals.get("net_by_vat_rate")
    vat_by_vat = totals.get("vat_by_vat_rate")

    if not net_by_vat or not vat_by_vat:
        return [CheckResult(
            check_id = "V3",
            passed   = False,
            detail   = (
                "Cannot run V3: "
                + ("net_by_vat_rate" if not net_by_vat else "vat_by_vat_rate")
                + " is missing or empty."
            ),
        )]

    all_rates = sorted(set(net_by_vat) | set(vat_by_vat))
    for rate in all_rates:
        if rate not in net_by_vat or rate not in vat_by_vat:
            results.append(CheckResult(
                check_id = "V3",
                passed   = False,
                detail   = f"rate={rate}%: missing net or VAT entry",
                rate     = rate,
            ))
            continue
        net        = _d(net_by_vat[rate])
        printed    = _d(vat_by_vat[rate])
        calculated = round_financial(net * Decimal(rate) / Decimal("100"))
        diff       = abs(printed - calculated)
        passed     = amounts_match(printed, calculated, _TOLERANCE)
        results.append(CheckResult(
            check_id   = "V3",
            passed     = passed,
            detail     = (
                f"rate={rate}%: {net}×{rate}/100={calculated} "
                f"printed={printed} diff={diff}"
            ),
            rate       = rate,
            expected   = calculated,
            actual     = printed,
            difference = diff,
        ))

    return results


# ---------------------------------------------------------------------------
# V4 — Gross total reconciliation
# ---------------------------------------------------------------------------

def check_v4(doc: dict) -> CheckResult:
    """V4: net_total + vat_total == gross_total.

    All three totals are required.  A missing field produces a FAIL result
    rather than silently substituting zero.
    """
    totals = doc.get("totals", {})
    missing = [f for f in ("net_total", "vat_total", "gross_total")
               if f not in totals or totals[f] is None]
    if missing:
        return CheckResult(
            check_id = "V4",
            passed   = False,
            detail   = f"Cannot run V4: missing required totals field(s): {missing}",
        )

    net      = _d(totals["net_total"])
    vat      = _d(totals["vat_total"])
    gross    = _d(totals["gross_total"])
    expected = round_financial(net + vat)
    diff     = abs(gross - expected)
    passed   = amounts_match(gross, expected, _TOLERANCE)
    return CheckResult(
        check_id   = "V4",
        passed     = passed,
        detail     = (
            f"net_total={net} + vat_total={vat} = {expected} "
            f"gross_total={gross} diff={diff}"
        ),
        expected   = expected,
        actual     = gross,
        difference = diff,
    )


# ---------------------------------------------------------------------------
# V5 — Supplier VAT ID format
# ---------------------------------------------------------------------------

_VAT_ID_PATTERN = re.compile(r"^DE\d{9}$")


def check_v5(doc: dict) -> CheckResult:
    """V5: supplier.vat_id matches ^DE\\d{9}$."""
    vat_id = doc.get("supplier", {}).get("vat_id", "")
    passed = bool(_VAT_ID_PATTERN.fullmatch(vat_id))
    return CheckResult(
        check_id = "V5",
        passed   = passed,
        detail   = (
            f"supplier.vat_id={vat_id!r} "
            + ("PASS" if passed else "FAIL: expected DE + 9 digits")
        ),
        actual   = vat_id,
    )


# ---------------------------------------------------------------------------
# V6 — Date validation
# ---------------------------------------------------------------------------

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_iso_date(value: str, field_name: str) -> CheckResult | None:
    """Return a FAIL CheckResult if the date string is invalid, else None."""
    if not _ISO_DATE_RE.fullmatch(value):
        return CheckResult(
            check_id = "V6",
            passed   = False,
            detail   = f"{field_name}={value!r}: not a valid ISO 8601 date",
            actual   = value,
        )
    y, m, d = map(int, value.split("-"))
    try:
        date(y, m, d)
    except ValueError as exc:
        return CheckResult(
            check_id = "V6",
            passed   = False,
            detail   = f"{field_name}={value!r}: invalid calendar date ({exc})",
            actual   = value,
        )
    return None


def check_v6(doc: dict) -> list[CheckResult]:
    """V6: All present dates are valid; due_date >= document_date.

    document_date is required.  service_date, due_date, and
    cash_discount.until are optional (null is permitted).
    """
    results: list[CheckResult] = []

    # document_date is required — absence is a FAIL.
    doc_date_value = doc.get("document_date")
    if doc_date_value is None:
        results.append(CheckResult(
            check_id = "V6",
            passed   = False,
            detail   = "document_date is missing or null (required field)",
        ))
        # Cannot check due_date ordering without document_date; return early.
        return results

    optional_fields = [
        ("service_date",        doc.get("service_date")),
        ("due_date",            doc.get("due_date")),
        ("cash_discount.until", (doc.get("cash_discount") or {}).get("until")),
    ]
    all_fields = [("document_date", doc_date_value)] + optional_fields

    parsed: dict[str, date] = {}
    for field_name, value in all_fields:
        if value is None:
            continue
        fail = _validate_iso_date(value, field_name)
        if fail:
            results.append(fail)
        else:
            y, m, d = map(int, value.split("-"))
            parsed[field_name] = date(y, m, d)
            results.append(CheckResult(
                check_id = "V6",
                passed   = True,
                detail   = f"{field_name}={value}: valid",
                actual   = value,
            ))

    # due_date >= document_date
    if "document_date" in parsed and "due_date" in parsed:
        if parsed["due_date"] < parsed["document_date"]:
            results.append(CheckResult(
                check_id = "V6",
                passed   = False,
                detail   = (
                    f"due_date={parsed['due_date']} is before "
                    f"document_date={parsed['document_date']}"
                ),
            ))
        else:
            results.append(CheckResult(
                check_id = "V6",
                passed   = True,
                detail   = (
                    f"due_date={parsed['due_date']} >= "
                    f"document_date={parsed['document_date']}"
                ),
            ))

    return results


# ---------------------------------------------------------------------------
# V7 — Sign consistency
# ---------------------------------------------------------------------------

def check_v7(doc: dict) -> list[CheckResult]:
    """V7: Monetary fields have the correct sign for the document type.

    Checked fields (OQ-02 resolved):
      line_items[*].line_total
      totals.net_by_vat_rate[*]
      totals.vat_by_vat_rate[*]
      totals.net_total
      totals.vat_total
      totals.gross_total

    Excluded: quantity, unit_price, price_unit, discount_percent,
              vat_rate, position, cash_discount.amount.

    Zero is a FAIL — a required monetary amount must be non-zero.
    """
    results: list[CheckResult] = []
    doc_type = doc.get("document_type", "")
    if doc_type not in ("invoice", "credit_note"):
        results.append(CheckResult(
            check_id = "V7",
            passed   = False,
            detail   = f"Unknown document_type: {doc_type!r}",
        ))
        return results

    expect_positive = (doc_type == "invoice")

    def _sign_ok(value: Decimal) -> bool:
        return (value > _ZERO) if expect_positive else (value < _ZERO)

    # line_total for each item
    for item in doc.get("line_items", []):
        pos = item["position"]
        lt  = _d(item["line_total"])
        ok  = _sign_ok(lt)
        results.append(CheckResult(
            check_id = "V7",
            passed   = ok,
            detail   = (
                f"Pos {pos} line_total={lt}: "
                + ("PASS" if ok else
                   f"FAIL — expected {'positive' if expect_positive else 'negative'}")
            ),
            position = pos,
            actual   = lt,
        ))

    # totals dict amounts
    totals = doc.get("totals", {})
    for label, sub in [
        ("net_by_vat_rate", totals.get("net_by_vat_rate", {})),
        ("vat_by_vat_rate", totals.get("vat_by_vat_rate", {})),
    ]:
        for rate, amount in sub.items():
            v  = _d(amount)
            ok = _sign_ok(v)
            results.append(CheckResult(
                check_id = "V7",
                passed   = ok,
                detail   = (
                    f"{label}[{rate}]={v}: "
                    + ("PASS" if ok else
                       f"FAIL — expected {'positive' if expect_positive else 'negative'}")
                ),
                rate   = rate,
                actual = v,
            ))

    for fname in ("net_total", "vat_total", "gross_total"):
        v  = _d(totals.get(fname, 0))
        ok = _sign_ok(v)
        results.append(CheckResult(
            check_id = "V7",
            passed   = ok,
            detail   = (
                f"{fname}={v}: "
                + ("PASS" if ok else
                   f"FAIL — expected {'positive' if expect_positive else 'negative'}")
            ),
            actual = v,
        ))

    return results
