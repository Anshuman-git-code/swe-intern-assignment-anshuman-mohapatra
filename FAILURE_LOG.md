# FAILURE_LOG.md — Supplier Invoice Fingerprint

At least five genuine bugs found and fixed during development.

---

## Entry 1 — V4 silently PASS on empty document

**What went wrong:** `check_v4({})` returned PASS.

The initial implementation used `totals.get("net_total", 0)` to substitute
zero when a required total was missing. With all three totals missing (zero),
`0 + 0 = 0 = 0`, so the check passed.

**How it was noticed:** During Phase 7/8 reconciliation, an independent review
ran `check_v4({})` and observed the result was `passed=True`. A check that
cannot find any data must never pass.

**What was changed:** Replaced all three `get(..., 0)` calls with explicit
presence checks. Any missing field now returns an immediate FAIL result naming
the missing field.

```python
# Before (wrong):
net = _d(totals.get("net_total", 0))

# After (correct):
missing = [f for f in ("net_total","vat_total","gross_total")
           if f not in totals or totals[f] is None]
if missing:
    return CheckResult(check_id="V4", passed=False,
                       detail=f"Cannot run V4: missing {missing}")
```

**How the fix was verified:** `check_v4({}).passed` is now `False`. Tests for
each individually missing field were added to `test_checks.py`.

---

## Entry 2 — V2 `expected` and `actual` fields reversed

**What went wrong:** In `check_v2()`, `expected` held the printed net amount
and `actual` held the calculated line-item sum — the opposite of V1, V3, and V4
conventions.

For INV-04 the result showed `expected=5213.22` (printed) and
`actual=5249.22` (calculated), which is backwards: "expected" should mean
what the formula computes and "actual" should mean what the document states.

**How it was noticed:** A reviewer inspected the INV-04 V2 result and noticed
that the `expected` field for a failing check should be the value we calculated
(5249.22), not the value already in the document (5213.22).

**What was changed:** Swapped the assignments in `check_v2()`:

```python
# After (correct):
expected = line_sum    # calculated line-item sum
actual   = printed_net # stored/printed net
```

**How the fix was verified:** Added `test_v2_expected_is_line_sum_actual_is_printed_net`
which asserts `r19.expected == Decimal("5249.22")` and
`r19.actual == Decimal("5213.22")` for INV-04.

---

## Entry 3 — `format_document_section` silently omitting checks with empty results

**What went wrong:** When a check returned an empty result list (e.g. `check_v1({})`
returned `[]`), `format_document_section` skipped that check entirely. A reader
of the report would have no indication that V1 had not been run.

**How it was noticed:** The reconciliation review called
`format_document_section("TEST", {"V1": []})` and found the resulting Markdown
contained only the document heading with no check sections at all — not even a
FAIL indicator.

**What was changed:** The loop in `format_document_section` now always outputs
all seven check sections. An empty result list produces an explicit FAIL message:

```python
if not results:
    lines.append(f"\n### {check_id} — ❌ FAIL\n")
    lines.append(f"- ❌ No results produced for {check_id}. ...")
    continue
```

**How the fix was verified:** `test_validation_report.py::TestEmptyResultsNotSilentlyOmitted`
contains four tests confirming that empty V1, empty V4, all-empty, and
missing-key inputs all produce visible FAIL sections.

---

## Entry 4 — Legacy parser `order_reference` included the date suffix

**What went wrong:** The first implementation of the multi-token `"Ihre Bestellung"`
label used a function that found the first matching token (`"Bestellung"`) and
then collected all tokens to its right on the same line. This collected
`"4500093317 vom 22.09.2026"` but the schema requires only `"4500093317"`.

A later regression showed that the function was using the x1 boundary of the
`"Bestellung"` token rather than `"Ihre"`, causing it to incorrectly include
`"vom"` and the date in the value.

**How it was noticed:** The `test_exact_output_equals_reference` test for INV-01
failed with `order_reference` = `"vom 22.09.2026"` instead of `"4500093317"`.

**What was changed:** `_get_bestellung_value()` was rewritten to locate the
`"Bestellung"` token specifically (the second word of the label), then collect
value tokens to the right, and finally strip the `" vom DD.MM.YYYY"` suffix
with a regex.

**How the fix was verified:** `test_inv01_exact_reference_match` passes. The
exact `assert parsed == reference` comparison would catch any recurrence.

---

## Entry 5 — INV-05 PE column boundary caused unit_price to absorb the PE value

**What went wrong:** On INV-05, Pos 5 (`KI-20811`) had `unit_price=14.601`
instead of `14.6`, and `price_unit=1.0` instead of `100.0`. The token `"100"`
at x=456.37 was landing in the `einzelpreis` column (x range 402–458) instead
of the `pe` column (x range 455–476).

**How it was noticed:** The field-by-field comparison against the reference JSON
showed two mismatches on line item Pos 5.

**What was changed:** The `einzelpreis` column upper boundary was tightened
from 458 to 455, so x=456.37 correctly falls in the `pe` column. This was
determined by examining the exact word coordinates from `page.get_text("words")`.

**How the fix was verified:** `test_position_5_has_price_unit_100` and
`test_position_5_unit_price` both pass. The full reference comparison
`assert parsed == reference` would catch any recurrence.

---

## Note on INV-04 Pos 7

The printed line total `1,284.52` for Position 7 is inconsistent with
`26 × 48.02 = 1,248.52`. This is **not an extractor bug** — it is a
discrepancy in the source document. The extractor correctly stores the
printed value per BR-01, and the validator correctly reports it as a FAIL.
