# AI_USAGE.md — Supplier Invoice Fingerprint

## Tools used

**Kiro AI (VS Code extension) & ChatGPT** — used throughout the project for:
- Drafting implementation plans for each phase (reviewed and approved before code was written).
- Writing initial versions of all Python modules and tests.
- Reviewing and correcting bugs identified during independent testing.
- Generating documentation drafts (README, MARKING_NOTES, this file).

---

## Example 1 — V4 silently passing on an empty document

**What the AI initially produced:**

```python
def check_v4(doc: dict) -> CheckResult:
    totals = doc.get("totals", {})
    net   = _d(totals.get("net_total", 0))
    vat   = _d(totals.get("vat_total", 0))
    gross = _d(totals.get("gross_total", 0))
    ...
```

The `0` defaults meant that `check_v4({})` returned `passed=True` —
`0 + 0 = 0 = gross_total` was numerically correct, even though no data existed.

**Why it was incorrect:**

A required validation check must never pass when the data it needs is absent.
A PASS here would hide data-quality problems silently.

**How it was discovered:**

Ran `check_v4({}).passed` and saw `True`. The Phase 8
reconciliation task explicitly required fixing this.

**What was changed:**

All three `.get(..., 0)` calls were replaced with explicit presence checks that
produce a FAIL result naming the missing field(s). See `FAILURE_LOG.md` Entry 1.

---

## Example 2 — V2 expected/actual semantics reversed

**What the AI initially produced:**

```python
results.append(CheckResult(
    ...
    expected = printed_net,  # wrong: this is the "actual" stored value
    actual   = line_sum,     # wrong: this is the "expected" calculated value
    ...
))
```

**Why it was incorrect:**

The convention across V1, V3, and V4 is:
- `expected` = the value the formula calculates
- `actual` = the value stored/printed in the document

By swapping them in V2, the INV-04 FAIL result showed `expected=5213.22`
(the printed net) and `actual=5249.22` (the line sum). This is backwards:
when a check fails, the "expected" field should show what we computed and
the "actual" field should show what the document says.

**How it was discovered:**

Inspected the INV-04 V2 `CheckResult` and noticed the semantics
did not match V1's convention: for INV-04 V1 Pos 7, `expected=1248.52`
(calculated) and `actual=1284.52` (printed). V2 had the opposite assignment.

**What was changed:**

The two assignments were swapped in `check_v2()`. A regression test was added
to `test_checks.py` that explicitly asserts `r19.expected == Decimal("5249.22")`
(line sum) and `r19.actual == Decimal("5213.22")` (printed net) for INV-04.
