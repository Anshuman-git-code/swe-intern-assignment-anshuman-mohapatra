# MARKING_NOTES.md — Supplier Invoice Fingerprint

This file documents how every output field is located, extracted, and validated
for each Kessler invoice layout. Provenance tags: [P] = printed directly,
[D] = derived from printed values, [I] = interpreted from a relative term.

---

## Field extraction reference

| Field | JSON path | Layout | Location / anchor | Parser / helper | Robustness | What breaks it | Provenance |
|-------|-----------|--------|-------------------|-----------------|-----------|----------------|------------|
| document_type | `.document_type` | both | Document heading: `"RECHNUNG"` → invoice; `"GUTSCHRIFT"` → credit_note; `"Rechnung"` (sentence-case) → invoice (modern) | `layout_legacy.py` / `layout_modern.py` | Checks exact heading text | A completely different heading word | [P] |
| document_number | `.document_number` | legacy | Label `"Rechnungs-Nr."` or `"Gutschrift-Nr."` on right side (x>340); value is the token(s) to its right | `_first_word_after_label()` | Label text is consistent across all legacy docs | Label change or multi-token value | [P] |
| document_number | `.document_number` | modern | Label `"Rechnung Nr."` on left side (x≈51); value at x≈147 | `_label_value()` | Label is unique on the page | Two-token label split differently | [P] |
| document_date | `.document_date` | legacy | Label `"Datum"` (x≈345); value to the right | `parse_german_date()` | Short format DD.MM.YYYY | Label missing or date format change | [P] |
| document_date | `.document_date` | modern | Label `"Rechnungsdatum"` (x≈51); value at x≈147 — long German format | `parse_german_date()` | Handles D. Monatname YYYY | New month name or format | [P] |
| service_date | `.service_date` | legacy | Label `"Leistungsdatum"` | `parse_german_date()` | Absent on credit note → null | Label rename | [P] or null |
| service_date | `.service_date` | modern | Label `"Lieferdatum"` | `parse_german_date()` | — | — | [P] |
| due_date | `.due_date` | both | Payment terms line: `"Zahlbar bis DD.MM.YYYY"` or `"(bis D. Monatname YYYY)"` (modern) | `_extract_payment_terms()` | Regex on payment text | Different payment-terms phrasing | [P] |
| currency | `.currency` | both | Always `"EUR"` — constant | hardcoded | Kessler always invoices in EUR | Multi-currency invoices | [P] |
| supplier.name | `.supplier.name` | both | Hardcoded — consistent across all documents | hardcoded | Reliable for this supplier | Supplier name change | [P] |
| supplier.vat_id | `.supplier.vat_id` | both | Footer line: `"USt-IdNr. DE287364519"` — regex `USt-IdNr\.\s+(DE\d{9})` | regex in `parse_legacy_invoice()` | Appears on every page footer | Footer position change | [P] |
| buyer.name | `.buyer.name` | legacy | Address block, first row at y≈130, x<200 | `_extract_buyer_address()` | Skips dept line (y≈144) and street (y≈157) | Extra address lines above the name | [P] |
| buyer.name | `.buyer.name` | modern | Right-side block (x≥330), first row; filters out `"z. Hd."` attention line | `_extract_modern_buyer()` | Explicitly excludes attention line | Attention line appearing before company name | [P] |
| buyer.street | `.buyer.street` | legacy | Address block row at y≈157 | `_extract_buyer_address()` | Fixed y-band order | Reordered address lines | [P] |
| buyer.postal_code | `.buyer.postal_code` | both | First token of postal+city row (y≈183 legacy, y≈170 modern) | address extractors | Fixed position | Multi-line city | [P] |
| buyer.city | `.buyer.city` | both | Remaining tokens after postal code on same row | address extractors | — | Postal code with space inside | [P] |
| buyer.customer_number | `.buyer.customer_number` | legacy | Label `"Kunden-Nr."` | `_first_word_after_label()` | Consistent label | — | [P] |
| buyer.customer_number | `.buyer.customer_number` | modern | Label `"Kundennummer"` | `_label_value()` | — | — | [P] |
| order_reference | `.order_reference` | legacy | Label `"Ihre Bestellung"`; date suffix stripped: `r"\s+vom\s+\d{2}\.\d{2}\.\d{4}$"` | `_get_bestellung_value()` + regex | Schema requires number only | Date format in suffix changes | [P] (stripped) |
| order_reference | `.order_reference` | modern | Label `"Bestellnummer"` | `_label_value()` | No date suffix in modern layout | — | [P] |
| delivery_note_number | `.delivery_note_number` | legacy | Label `"Lieferschein-Nr."` | `_first_word_after_label()` | — | — | [P] |
| delivery_note_number | `.delivery_note_number` | modern | Label `"Lieferschein"` | `_label_value()` (x_value_max=330) | x cap prevents picking up supplier address on same y | Supplier address line moving | [P] |
| referenced_invoice | `.referenced_invoice` | legacy | Label `"Bezug Rechnung"` on credit notes; value starts after label tokens (x>420); date suffix stripped | `_get_bezug_rechnung()` | Credit notes only; null for invoices | Label change | [P] (stripped) or null |
| line_items[n].position | `.line_items[n].position` | legacy | Token in `pos` column (x≈45–77) on item row; `int()` strips leading zeros | column detection | Consistent column | Column position shift | [P] |
| line_items[n].position | `.line_items[n].position` | modern | Token in `pos` column (x≈45–77); `"001"` → `int()` = 1 | column detection | — | — | [P] |
| line_items[n].article_number | `.line_items[n].article_number` | legacy | Token in `art_nr` column (x≈80–155) | column detection | Consistent with known article prefixes | Width change of description column | [P] |
| line_items[n].article_number | `.line_items[n].article_number` | modern | Token in `artikel` column (x≈141–209) | column detection | Column boundary tuned to 141.73 observed | Supplier reflows table | [P] |
| line_items[n].description | `.line_items[n].description` | both | `beschreibung` column; continuation rows (no pos/art) appended with space; discount rows excluded | `_extract_line_items_from_page()` / `_extract_modern_line_items()` | Continuation row detection by absence of pos+art tokens | Continuation rows gaining position tokens | [P] |
| line_items[n].quantity | `.line_items[n].quantity` | legacy | `menge` column (x≈335–370); `parse_german_number()` handles `"1.000"` → 1000 | `parse_german_number()` | Handles thousands separator and fractions | Quantity in a new column | [P] |
| line_items[n].quantity | `.line_items[n].quantity` | modern | `menge` column (x≈77–107) | — | — | — | [P] |
| line_items[n].unit | `.line_items[n].unit` | legacy | `me` column (x≈370–402) | column detection | — | — | [P] |
| line_items[n].unit | `.line_items[n].unit` | modern | `einh` column (x≈107–141) | column detection | — | — | [P] |
| line_items[n].unit_price | `.line_items[n].unit_price` | legacy | `einzelpreis` column (x≈402–455); `€` stripped | `parse_german_number()` | `Decimal` preserves 3dp (e.g. 0.152) | Column shrink causes PE token to shift in | [P] |
| line_items[n].unit_price | `.line_items[n].unit_price` | modern | `preis` column (x≈426–478); `€` stripped | — | — | — | [P] |
| line_items[n].price_unit | `.line_items[n].price_unit` | legacy | `pe` column (x≈455–476); blank → `Decimal("1")` | column detection | Blank PE is a legitimate "1" default | Token from neighbouring column crossing boundary | [P] or default 1 |
| line_items[n].price_unit | `.line_items[n].price_unit` | modern | No PE column exists → always `Decimal("1")` | hardcoded default | Modern layout has no PE column | Layout adding PE column | default [P] |
| line_items[n].discount_percent | `.line_items[n].discount_percent` | legacy | `rab` column (x≈476–515); blank → null | column detection | Distinct from PE column | Column boundary shift | [P] or null |
| line_items[n].discount_percent | `.line_items[n].discount_percent` | modern | Standalone `"abzgl."` row detected in `beschreibung` column; percent extracted with regex `(\d+)\s*%` | `_extract_modern_line_items()` | Row starts with "abzgl." — unique anchor | Different discount row format | [P] |
| line_items[n].line_total | `.line_items[n].line_total` | legacy | `gesamt` column (x≈515–560); trailing-minus for credit notes parsed by `parse_german_number()` | — | **Printed value stored as-is** — never recalculated | — | [P] |
| line_items[n].line_total | `.line_items[n].line_total` | modern | `betrag` column (x≈530–595); pre-discount Betrag then adjusted by discount row amount | `_extract_modern_line_items()` | Post-discount total derived: 465.60 − 13.97 = 451.63 | Discount row format change | [D] for Pos 002; [P] otherwise |
| line_items[n].vat_rate | `.line_items[n].vat_rate` | legacy | `ust` column (x≈560–600); `int()` applied | column detection | Bare integer in column | Column shift | [P] |
| line_items[n].vat_rate | `.line_items[n].vat_rate` | modern | `mwst` column (x≈478–530); `"%"` stripped then `int()` | — | — | — | [P] |
| totals.net_by_vat_rate | `.totals.net_by_vat_rate` | legacy | Label `"Nettobetrag N % USt"` in totals block (x>330); rate from regex; amount from rightmost numeric token | `_extract_totals()` | Handles trailing-minus for credit notes | Label rename | [P] |
| totals.net_by_vat_rate | `.totals.net_by_vat_rate` | modern | No printed per-rate net → derived from line-item sums grouped by VAT rate | `_extract_modern_totals()` | V2 passes by construction; not an independent check | — | [D] |
| totals.vat_by_vat_rate | `.totals.vat_by_vat_rate` | legacy | `"zzgl. N % USt auf Y"` row | `_extract_totals()` | — | — | [P] |
| totals.vat_by_vat_rate | `.totals.vat_by_vat_rate` | modern | `"MwSt N%"` rows | `_extract_modern_totals()` | — | — | [P] |
| totals.net_total | `.totals.net_total` | legacy | Sum of `net_by_vat_rate.values()` | computed | — | — | [D] |
| totals.net_total | `.totals.net_total` | modern | Printed `"Summe netto"` value | `_extract_modern_totals()` | — | — | [P] |
| totals.vat_total | `.totals.vat_total` | both | Sum of `vat_by_vat_rate.values()` | computed | — | — | [D] |
| totals.gross_total | `.totals.gross_total` | legacy | `"Rechnungsbetrag"` or `"Gutschriftsbetrag"` row | `_extract_totals()` | Raises ValueError if missing | Label change | [P] |
| totals.gross_total | `.totals.gross_total` | modern | `"Gesamtbetrag"` row | `_extract_modern_totals()` | — | — | [P] |
| cash_discount.percent | `.cash_discount.percent` | legacy | Payment terms text: regex `([\d,]+)\s*%\s*Skonto` | `_extract_payment_terms()` | Covers both absolute and relative formats | Phrasing change | [P] |
| cash_discount.until | `.cash_discount.until` | legacy | Absolute: `"Bei Zahlung bis DD.MM.YYYY"` → date [P]; Relative: `"innerhalb von N Tagen"` → `document_date + N days` | `add_days()` | INV-04 uses relative term | New relative-date phrasing | [P] or [I] |
| cash_discount.amount | `.cash_discount.amount` | legacy | `"(= X EUR)"` from Skonto line | `parse_german_number()` | — | Parenthesis format change | [P] |
| cash_discount | `.cash_discount` | modern | `"Kein Skontoabzug."` → null | text detection | — | Different no-Skonto phrasing | null [P] |

---

## INV-05 layout change — 200-word answer

INV-05 introduced a new invoice format from Kessler. The changes required
were:

1. **A new parser module** (`parsers/layout_modern.py`). The metadata block
   moved from the right side to the left, date labels changed (e.g.
   `Rechnungsdatum` instead of `Datum`), date format changed to long German
   (`19. Oktober 2026`), and the table column structure changed entirely —
   no PE column, no Rab.% column, and a new `"abzgl."` standalone discount row.

2. **Layout detection** in `extract.py` checks for `"Rechnung Nr."` (modern)
   versus `"Rechnungs-Nr."` (legacy) in the first page's text. This is a
   structural anchor, not a filename pattern, so it works even if Kessler
   changes their numbering scheme.

3. **No changes to any generic helper.** `parse_german_number()`,
   `parse_german_date()`, `round_financial()`, `amounts_match()`,
   `open_pdf()`, `load_schema()`, and `write_json()` are shared by both
   parsers without modification.

4. **The legacy parser was not modified.** INV-01 through INV-04 continue
   to work exactly as before.

The separation between generic helpers and layout-specific parsers meant that
adding modern support required zero changes to previously working code —
only new code was added.
