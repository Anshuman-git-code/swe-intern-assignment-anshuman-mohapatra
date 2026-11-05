# Supplier Invoice Fingerprint

**Assignment:** Software Engineer Intern (Data & Development) — Fingerprint Challenge  
**Candidate:** Anshuman Mohapatra  
**Deadline:** Thursday, 5 November 2026, 1:00 PM IST

---

## What this project does

This project reads PDF invoices and credit notes from **Kessler Industrietechnik GmbH**
and produces a validated JSON file for each document. A separate validation step
checks the arithmetic and reports discrepancies — including errors that originate
in the source document itself.

**Supported documents:** INV-01 through INV-05 (five invoices/credit notes).  
**INV-06** (scanned image-only) was an optional OCR bonus and is not implemented.

---

## Prerequisites

- Python 3.14 (Homebrew: `/opt/homebrew/bin/python3`)
- Git

---

## Setup

```bash
# Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Verify
python -c "import pymupdf; print('PyMuPDF', pymupdf.__version__)"
python -c "import jsonschema; print('jsonschema OK')"
python -c "import pytest; print('pytest', pytest.__version__)"
```

---

## Extracting invoices

### Extract one invoice

```bash
source .venv/bin/activate
python extract.py input/INV-01_RE-2026-10418.pdf
# Output: outputs/INV-01_RE-2026-10418.json
```

### Extract all five invoices

```bash
source .venv/bin/activate
for f in input/INV-0[1-5]*.pdf; do python extract.py "$f"; done
```

The extractor detects the layout automatically and validates the output against
`input/output_schema.json` before writing.

---

## Generating the validation report

```bash
source .venv/bin/activate
python validate.py outputs/
# Output: outputs/validation_report.md
```

---

## Running the automated tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

Expected result: **458 tests, all passing**.

---

## Project structure

```
deeplogic-ai-assignment/
│
├── input/              # Source PDFs and output_schema.json (do not modify)
├── reference/          # Assignment brief; INV-01 reference output
├── outputs/            # Generated JSON outputs and validation_report.md
│
├── helpers/            # Generic utilities (no Kessler-specific logic)
│   ├── numbers.py      # German number → Decimal
│   ├── financials.py   # round_financial(), amounts_match()
│   ├── dates.py        # German date → ISO 8601; add_days()
│   ├── pdf_reader.py   # Safe PDF opening and text/word extraction
│   └── schema_io.py    # JSON loading, schema validation, JSON writing
│
├── parsers/
│   ├── layout_legacy.py  # INV-01 to INV-04 (legacy layout)
│   └── layout_modern.py  # INV-05 (modern layout)
│
├── validation/
│   ├── checks.py       # V1–V7 check functions
│   └── report.py       # Markdown report generator
│
├── tests/              # pytest test suite (458 tests)
│
├── extract.py          # CLI: python extract.py <pdf>
├── validate.py         # CLI: python validate.py outputs/
├── requirements.txt
└── README.md
```

---

## Architecture overview

### Layout detection

`extract.py` reads the first page of the PDF and looks for the label
`"Rechnung Nr."` (modern layout) versus `"Rechnungs-Nr."` or `"Gutschrift-Nr."`
(legacy layout). Detection uses text anchors, not the filename.

### Legacy layout parser (`parsers/layout_legacy.py`)

Handles INV-01, INV-02, INV-03, INV-04. Processes each page independently to
avoid cross-page row merging. Uses word bounding boxes (x-coordinates) to
distinguish the PE and Rab.% columns from the numeric values around them.

### Modern layout parser (`parsers/layout_modern.py`)

Handles INV-05. The modern layout has different column names, long-form German
dates, no PE column, and standalone discount rows starting with `"abzgl."`.
Both parsers call the same generic helper functions.

### Generic helpers

All five helpers in `helpers/` are layout-agnostic and reused by both parsers:
- `numbers.py` — converts German-format numbers to `Decimal`
- `financials.py` — rounds monetary amounts; compares with ±0.01 tolerance
- `dates.py` — parses German dates; adds calendar days
- `pdf_reader.py` — opens PDFs safely; extracts text and word coordinates
- `schema_io.py` — loads/validates JSON Schema; writes JSON with Decimal support

### Financial arithmetic

All monetary calculations use `decimal.Decimal` (not `float`) to avoid binary
rounding errors. `float` is used only at the final JSON serialisation step in
`helpers/schema_io.py`.

---

## Validation checks V1–V7

| Check | Rule | INV-01–03, INV-05 | INV-04 |
|-------|------|-------------------|--------|
| V1 | `qty × unit_price ÷ PE × (1 − disc) = line_total` | PASS | **FAIL Pos 7** |
| V2 | Sum of line_total per VAT rate = net_by_vat_rate | PASS | **FAIL 19%** |
| V3 | net × rate/100 = vat amount | PASS | PASS |
| V4 | net_total + vat_total = gross_total | PASS | PASS |
| V5 | supplier.vat_id matches `^DE\d{9}$` | PASS | PASS |
| V6 | dates valid; due_date ≥ document_date | PASS | PASS |
| V7 | correct sign for document type | PASS | PASS |

**INV-04 V1 and V2 failures are document-originated.** The printed line total
for Position 7 (`1,284.52`) does not equal `26 × 48.02 = 1,248.52` (difference
= +36.00). The extractor stores the printed value as-is per business rule BR-01.
This is a correct, valuable finding — not a program bug.

**INV-05 V2 passes by construction.** The modern layout prints only a combined
net total; per-VAT-rate net amounts are derived from line items. V2 compares
derived values against themselves and cannot independently verify a printed
per-rate net. The validation report discloses this limitation.

---

## Known limitations

- **INV-06 OCR:** The scanned image-only invoice was an optional bonus and is
  not implemented.
- **Supplier name hardcoded:** `"Kessler Industrietechnik GmbH"` is hardcoded
  in the parsers. For a different supplier this would need extraction.
- **Column coordinates:** The coordinate-based column detection uses boundaries
  tuned for the exact page geometry of these six invoices. A layout with
  significantly different margins might require adjustment.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyMuPDF | 2.1 | PDF text and coordinate extraction |
| jsonschema | 4.26.0 | JSON Schema validation |
| pytest | 9.2.0 | Automated testing |
