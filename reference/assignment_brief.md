Skip navigation
🧪
Assignment – Software Engineer Intern (Data & Development) – Fingerprint Challenge
Role: Software Engineer Intern (Data & Development) Deadline: Thursday, 5 November 2026, 1:00 PM IST (expected effort: 8–12 hours) Submit via: the submission form linked in your invitation email

0. The situation
You have just joined our Data & Development team. Our customer Rheinwerk Anlagenbau AG receives documents from its supplier Kessler Industrietechnik GmbH and wants them processed automatically.

Your job is to build a fingerprint for this supplier: a small, robust Python extractor that turns each Kessler PDF into structured JSON, plus a validation step that proves the numbers add up – or shows exactly where they don't.

All companies, people, numbers and documents in this assignment are fictional.

1. Files
Download everything from the assignment pack: https://drive.google.com/drive/folders/1VDcaysHvqWPhgrheRhsAy3ej1ZA1549C

File

What it is

INV-01_RE-2026-10418.pdf

Simple one-page invoice

INV-02_RE-2026-10431.pdf

Three-page invoice

INV-03_GS-2026-00872.pdf

Credit note (Gutschrift)

INV-04_RE-2026-10457.pdf

Two-page invoice

INV-05_2026-R-00117.pdf

Same supplier, after it changed its invoice layout

INV-06_BONUS_scan_RE-2026-10466.pdf

Optional bonus: a scanned (image-only) invoice

INV-01_expected_output.json

The correct output for INV-01 – use it to check yourself

output_schema.json

The exact output format (field names, types, meaning)

Read output_schema.json completely before you start. The field descriptions contain rules.

2. Business rules (read twice)
Extract what is printed. Never "fix" a value silently. If something printed is inconsistent, extract it as printed and report it in the validation step.

Amounts use German formatting (1.234,56). Output plain numbers (1234.56). Dates are output as YYYY-MM-DD.

unit_price is per price_unit (the PE / Preiseinheit column). If a price is per 100 pieces, price_unit is 100.

Credit notes are output with negative line totals and totals.

Extra lines printed under an item (batch numbers, notes, references) belong to that item's description.

Rows that are not items – carry-over amounts, sub-totals, headers repeated on a new page – must not appear in line_items.

If a discount is shown as its own row under an item, apply it to that item (discount_percent, discounted line_total) – do not output it as a separate item.

Cash discount (Skonto) terms are informational only. Report them in cash_discount; never subtract them from totals.

buyer.name is the company name only – no department or "attention of" lines.

3. What you must build
Task 1 – Extractor
python extract.py <path-to-pdf> writes outputs/<pdf-file-name>.json that validates against output_schema.json.

Your output for INV-01 must match INV-01_expected_output.json (field order and whitespace don't matter).

Produce outputs for INV-01 to INV-05 (and INV-06 if you attempt the bonus).

Any PDF library is fine. Keep supplier-specific logic clearly separated from generic helpers (number parsing, date parsing, writing JSON).

Task 2 – Validation report
python validate.py outputs/ writes outputs/validation_report.md with, for each document, a PASS/FAIL line for each check and the numbers behind it:

Check

Rule

V1

Every line: quantity × unit_price ÷ price_unit × (1 − discount) equals line_total (±0.01)

V2

Per VAT rate: sum of line_total equals net_by_vat_rate (±0.01)

V3

Per VAT rate: net × rate equals vat_by_vat_rate (±0.01)

V4

net_total + vat_total equals gross_total (±0.01)

V5

Supplier VAT ID looks like a German VAT ID (DE + 9 digits)

V6

Dates are valid; due_date (if present) is not before document_date

V7

Credit notes: all amounts negative; invoices: all amounts positive

If a check fails, say which line, expected vs. printed, and the difference. A FAIL caused by the document itself is a correct, valuable result – not a bug in your code.

Task 3 – Fingerprint notes (MARKING_NOTES.md)
For every output field: how you locate it (anchor text, position, column), why that is robust, and what would break it. Then answer in max. 200 words:

INV-05 is the same supplier after a layout change. What did you have to change, and how did you structure your code so that supporting the new layout did not break the old one?

Task 4 – Failure log (FAILURE_LOG.md)
At least 5 entries, each with: what went wrong (your bug or an AI suggestion that was wrong) → how you noticed → what you changed → how you verified the fix. Honest, specific entries score far higher than polished ones.

Bonus – Scanned page
Produce outputs/INV-06_BONUS_scan_RE-2026-10466.json using OCR. Partial results are welcome – tell us in the README which fields you trust and which you don't.

4. AI usage
You may use ChatGPT, Copilot, Claude or any other tool. Add AI_USAGE.md:

which tools you used and for what,

two concrete examples where the AI's answer was wrong or incomplete for these documents, and how you found out.

In the interview we will give you a new document from the same supplier and ask you to talk us through the changes in your own code, live. Make sure you understand every line you submit.

5. Deliverables
Private GitHub repository named swe-intern-assignment-<your-name>, shared with GitHub users deeplogicaitech and csvinay, containing:

extract.py, validate.py and any modules

requirements.txt

outputs/ – one JSON per document + validation_report.md

README.md – setup, how to run, design overview, known limitations

MARKING_NOTES.md, FAILURE_LOG.md, AI_USAGE.md

No secrets, no virtual environment folders

Explanation video (max. 10 minutes) – Google Drive link with access "Anyone with the link". Show:

running the extractor and validator on all documents,

one tricky case you solved and how,

what your validation report found and what you think it means.

Submission form – repository link, video link, your resume link.

6. How we evaluate
Accuracy of your outputs against our reference results · quality of your validation report · how well you understood the documents (notes and failure log) · clarity of your video · originality.

Work alone. Submissions are compared with each other; shared or copied work is rejected.

All the best – we look forward to your submission!




Contents
0. The situation
1. Files
2. Business rules (read twice)
3. What you must build
Task 1 – Extractor
Task 2 – Validation report
Task 3 – Fingerprint notes (MARKING_NOTES.md)
Task 4 – Failure log (FAILURE_LOG.md)
Bonus – Scanned page
4. AI usage
5. Deliverables
6. How we evaluate
 Outline
Assignment – Software Engineer Intern (Data & Development) – Fingerprint Challenge
Role: Software Engineer Intern (Data & Development) Deadline: Thursday, 5 November 2026, 1:00 PM IST (expected effort: 8–12 hours) Submit via: the submission form linked in your invitation email

0. The situation
You have just joined our Data & Development team. Our customer Rheinwerk Anlagenbau AG receives documents from its supplier Kessler Industrietechnik GmbH and wants them processed automatically.

Your job is to build a fingerprint for this supplier: a small, robust Python extractor that turns each Kessler PDF into structured JSON, plus a validation step that proves the numbers add up – or shows exactly where they don't.

All companies, people, numbers and documents in this assignment are fictional.

1. Files
Download everything from the assignment pack: https://drive.google.com/drive/folders/1VDcaysHvqWPhgrheRhsAy3ej1ZA1549C

File

What it is

INV-01_RE-2026-10418.pdf

Simple one-page invoice

INV-02_RE-2026-10431.pdf

Three-page invoice

INV-03_GS-2026-00872.pdf

Credit note (Gutschrift)

INV-04_RE-2026-10457.pdf

Two-page invoice

INV-05_2026-R-00117.pdf

Same supplier, after it changed its invoice layout

INV-06_BONUS_scan_RE-2026-10466.pdf

Optional bonus: a scanned (image-only) invoice

INV-01_expected_output.json

The correct output for INV-01 – use it to check yourself

output_schema.json

The exact output format (field names, types, meaning)

Read output_schema.json completely before you start. The field descriptions contain rules.

2. Business rules (read twice)
Extract what is printed. Never "fix" a value silently. If something printed is inconsistent, extract it as printed and report it in the validation step.

Amounts use German formatting (1.234,56). Output plain numbers (1234.56). Dates are output as YYYY-MM-DD.

unit_price is per price_unit (the PE / Preiseinheit column). If a price is per 100 pieces, price_unit is 100.

Credit notes are output with negative line totals and totals.

Extra lines printed under an item (batch numbers, notes, references) belong to that item's description.

Rows that are not items – carry-over amounts, sub-totals, headers repeated on a new page – must not appear in line_items.

If a discount is shown as its own row under an item, apply it to that item (discount_percent, discounted line_total) – do not output it as a separate item.

Cash discount (Skonto) terms are informational only. Report them in cash_discount; never subtract them from totals.

buyer.name is the company name only – no department or "attention of" lines.

3. What you must build
Task 1 – Extractor
python extract.py <path-to-pdf> writes outputs/<pdf-file-name>.json that validates against output_schema.json.

Your output for INV-01 must match INV-01_expected_output.json (field order and whitespace don't matter).

Produce outputs for INV-01 to INV-05 (and INV-06 if you attempt the bonus).

Any PDF library is fine. Keep supplier-specific logic clearly separated from generic helpers (number parsing, date parsing, writing JSON).

Task 2 – Validation report
python validate.py outputs/ writes outputs/validation_report.md with, for each document, a PASS/FAIL line for each check and the numbers behind it:

Check

Rule

V1

Every line: quantity × unit_price ÷ price_unit × (1 − discount) equals line_total (±0.01)

V2

Per VAT rate: sum of line_total equals net_by_vat_rate (±0.01)

V3

Per VAT rate: net × rate equals vat_by_vat_rate (±0.01)

V4

net_total + vat_total equals gross_total (±0.01)

V5

Supplier VAT ID looks like a German VAT ID (DE + 9 digits)

V6

Dates are valid; due_date (if present) is not before document_date

V7

Credit notes: all amounts negative; invoices: all amounts positive

If a check fails, say which line, expected vs. printed, and the difference. A FAIL caused by the document itself is a correct, valuable result – not a bug in your code.

Task 3 – Fingerprint notes (MARKING_NOTES.md)
For every output field: how you locate it (anchor text, position, column), why that is robust, and what would break it. Then answer in max. 200 words:

INV-05 is the same supplier after a layout change. What did you have to change, and how did you structure your code so that supporting the new layout did not break the old one?

Task 4 – Failure log (FAILURE_LOG.md)
At least 5 entries, each with: what went wrong (your bug or an AI suggestion that was wrong) → how you noticed → what you changed → how you verified the fix. Honest, specific entries score far higher than polished ones.

Bonus – Scanned page
Produce outputs/INV-06_BONUS_scan_RE-2026-10466.json using OCR. Partial results are welcome – tell us in the README which fields you trust and which you don't.

4. AI usage
You may use ChatGPT, Copilot, Claude or any other tool. Add AI_USAGE.md:

which tools you used and for what,

two concrete examples where the AI's answer was wrong or incomplete for these documents, and how you found out.

In the interview we will give you a new document from the same supplier and ask you to talk us through the changes in your own code, live. Make sure you understand every line you submit.

5. Deliverables
Private GitHub repository named swe-intern-assignment-<your-name>, shared with GitHub users deeplogicaitech and csvinay, containing:

extract.py, validate.py and any modules

requirements.txt

outputs/ – one JSON per document + validation_report.md

README.md – setup, how to run, design overview, known limitations

MARKING_NOTES.md, FAILURE_LOG.md, AI_USAGE.md

No secrets, no virtual environment folders

Explanation video (max. 10 minutes) – Google Drive link with access "Anyone with the link". Show:

running the extractor and validator on all documents,

one tricky case you solved and how,

what your validation report found and what you think it means.

Submission form – repository link, video link, your resume link.

6. How we evaluate
Accuracy of your outputs against our reference results · quality of your validation report · how well you understood the documents (notes and failure log) · clarity of your video · originality.

Work alone. Submissions are compared with each other; shared or copied work is rejected.

All the best – we look forward to your submission!



