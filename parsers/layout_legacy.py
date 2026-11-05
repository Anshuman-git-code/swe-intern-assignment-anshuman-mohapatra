"""
parsers/layout_legacy.py

Extracts structured invoice data from Kessler Industrietechnik GmbH PDF
documents that use the legacy layout (INV-01 through INV-04, and INV-06 post-OCR).

Legacy layout column structure (x-coordinates in points, from Phase 2 analysis):
  Pos.        x ≈  51
  Art.-Nr.    x ≈  85
  Bezeichnung x ≈ 158   (description spans to ≈335)
  Menge       x ≈ 337
  ME          x ≈ 371
  Einzelpreis x ≈ 404   (value right-aligned around 432–454)
  PE          x ≈ 455   (price unit; blank = 1)
  Rab. %      x ≈ 477   (discount; blank = null)
  Gesamt €    x ≈ 516   (line total; value right-aligned around 526–552)
  USt %       x ≈ 563

Column x-boundaries used for word assignment:
  A word is assigned to a column when its x0 falls within the column's
  x-range defined by _COL_BOUNDS below.  This avoids ambiguity between
  the PE column (455–476) and the Rab.% column (477–515) for tokens like
  "1", "5", "100" that have no textual column label.

Multi-page architecture:
  Word coordinates from different pages must never be mixed in the same
  row-grouping pass.  Each page's words are processed independently.
  The header and buyer address are extracted from page 1.
  Line items are extracted per-page and concatenated.
  Totals are extracted from the page where "Nettobetrag" appears.
  Payment terms are parsed from the combined plain text.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from helpers.dates import add_days, parse_german_date
from helpers.numbers import parse_german_number
from helpers.pdf_reader import extract_page_words, extract_pages_text, open_pdf
from helpers.schema_io import load_schema, validate_output, write_json

# ---------------------------------------------------------------------------
# Column x-range boundaries (x0 of word must fall within [lo, hi)).
# ---------------------------------------------------------------------------
_COL_BOUNDS: dict[str, tuple[float, float]] = {
    "pos":         (  45.0,  80.0),
    "art_nr":      (  80.0, 155.0),
    "description": (155.0, 335.0),
    "menge":       (335.0, 370.0),
    "me":          (370.0, 402.0),
    "einzelpreis": (402.0, 455.0),
    "pe":          (455.0, 476.0),
    "rab":         (476.0, 515.0),
    "gesamt":      (515.0, 560.0),
    "ust":         (560.0, 600.0),
}

# Y-coordinate tolerance for grouping words into the same row.
_ROW_Y_TOL = 3.0

# Schema path.
_SCHEMA_PATH = Path("input/output_schema.json")


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------

def _col(x0: float) -> str | None:
    """Return the column name for a word at horizontal position x0."""
    for name, (lo, hi) in _COL_BOUNDS.items():
        if lo <= x0 < hi:
            return name
    return None


def _group_into_rows(
    words: list[tuple[float, float, float, float, str]],
    y_min: float,
    y_max: float,
) -> list[dict[str, list[str]]]:
    """Group word tokens from a single page into rows by approximate y-position.

    Only words with y0 between y_min and y_max are included.
    Words within _ROW_Y_TOL pts of each other share the same row.
    """
    rows: dict[float, dict[str, list[str]]] = {}
    for x0, y0, _x1, _y1, word in words:
        if not (y_min <= y0 <= y_max):
            continue
        matched_y = None
        for ey in rows:
            if abs(ey - y0) < _ROW_Y_TOL:
                matched_y = ey
                break
        if matched_y is None:
            matched_y = y0
            rows[matched_y] = {}
        col = _col(x0)
        if col is not None:
            rows[matched_y].setdefault(col, []).append(word)
    return [rows[y] for y in sorted(rows)]


def _first_word_after_label(
    words: list[tuple[float, float, float, float, str]],
    label: str,
    x_min: float = 340.0,
) -> str | None:
    """Find the value token(s) printed to the right of a header label."""
    label_y: float | None = None
    label_x1: float | None = None
    for x0, y0, x1, _y1, word in words:
        if word == label and x0 >= x_min:
            label_y = y0
            label_x1 = x1
            break
    if label_y is None:
        return None
    value_tokens = []
    for x0, y0, _x1, _y1, word in words:
        if abs(y0 - label_y) < _ROW_Y_TOL and x0 > label_x1 + 2:
            value_tokens.append((x0, word))
    value_tokens.sort(key=lambda t: t[0])
    return " ".join(w for _, w in value_tokens) if value_tokens else None


def _get_bestellung_value(
    words: list[tuple[float, float, float, float, str]],
) -> str | None:
    """Extract the value after 'Ihre Bestellung' label.

    The label is two tokens: 'Ihre' then 'Bestellung'.
    The value starts after both, at x > x1_of_Bestellung.
    """
    # Find 'Bestellung' (the second label word) on the right block.
    label_y: float | None = None
    label_x1: float | None = None
    for x0, y0, x1, _y1, word in words:
        if word == "Bestellung" and x0 >= 340:
            label_y = y0
            label_x1 = x1
            break
    if label_y is None:
        return None
    tokens = []
    for x0, y0, _x1, _y1, word in words:
        if abs(y0 - label_y) < _ROW_Y_TOL and x0 > label_x1 + 2:
            tokens.append((x0, word))
    tokens.sort(key=lambda t: t[0])
    return " ".join(w for _, w in tokens) if tokens else None


def _get_bezug_rechnung(
    words: list[tuple[float, float, float, float, str]],
) -> str | None:
    """Extract the 'Bezug Rechnung ...' value (credit notes only).

    The label is 'Bezug Rechnung' at x>340; we want only the reference number
    (e.g. 'RE-2026-10133'), not the label words or the date suffix.
    """
    label_y: float | None = None
    for x0, y0, _x1, _y1, word in words:
        if word == "Bezug" and x0 >= 340:
            label_y = y0
            break
    if label_y is None:
        return None
    # Collect all tokens on that row that are to the right of x≈420
    # (past the 'Rechnung' label token at x≈372).
    tokens = []
    for x0, y0, _x1, _y1, word in words:
        if abs(y0 - label_y) < _ROW_Y_TOL and x0 > 420:
            tokens.append((x0, word))
    tokens.sort(key=lambda t: t[0])
    raw = " ".join(w for _, w in tokens)
    # Strip the date suffix " v. DD.MM.YYYY"
    return re.sub(r"\s+v\.\s+\d{2}\.\d{2}\.\d{4}$", "", raw).strip() or None


def _extract_buyer_address(
    words: list[tuple[float, float, float, float, str]],
) -> dict:
    """Extract buyer name and address from the left-side address block (page 1).

    Address block occupies x < 200, y ≈ 125–205.
    Row order: company name / department (excluded) / street / postal+city
    """
    addr_words = [
        (x0, y0, word) for x0, y0, _x1, _y1, word in words
        if x0 < 200 and 125 < y0 < 205
    ]
    rows: dict[float, list[tuple[float, str]]] = {}
    for x0, y0, word in addr_words:
        matched_y = None
        for ey in rows:
            if abs(ey - y0) < _ROW_Y_TOL:
                matched_y = ey
                break
        if matched_y is None:
            matched_y = y0
            rows[matched_y] = []
        rows[matched_y].append((x0, word))

    sorted_rows = [
        " ".join(w for _, w in sorted(tokens, key=lambda t: t[0]))
        for _y, tokens in sorted(rows.items())
    ]

    name    = sorted_rows[0] if len(sorted_rows) > 0 else ""
    street  = sorted_rows[2] if len(sorted_rows) > 2 else ""
    pc_city = sorted_rows[3] if len(sorted_rows) > 3 else ""
    parts = pc_city.split()
    postal_code = parts[0] if parts else ""
    city = " ".join(parts[1:]) if len(parts) > 1 else ""

    return {"name": name, "street": street, "postal_code": postal_code, "city": city}


def _find_table_y_bounds(
    words: list[tuple[float, float, float, float, str]],
    page_no: int,
) -> tuple[float, float]:
    """Return (y_items_start, y_items_end) for the line-item table on this page.

    Page 1: table header at y≈294; items start below it.
    Continuation pages: table header at y≈138; 'Übertrag von Seite X' row at
    y≈155 follows immediately — items start after that carry-forward row.
    Items end just before 'Nettobetrag' or 'Übertrag' (outgoing carry-forward).
    """
    # Find the Pos. column header y.
    pos_ys = [y0 for x0, y0, _x1, _y1, w, *_ in words
               if w == "Pos." and x0 < 80]
    if not pos_ys:
        return (999.0, 0.0)  # no items on this page
    table_header_y = min(pos_ys)

    # Items start just below the table header (add a small margin).
    y_start = table_header_y + 12.0

    # On continuation pages, the first row after the header is
    # 'Übertrag von Seite X' — skip it by moving y_start past it.
    if page_no > 1:
        # Carry-forward row is typically 16 pts below the header.
        y_start = table_header_y + 28.0

    # Items end just before the first 'Nettobetrag' or outgoing 'Übertrag'
    # (the one at x≈158 in the Bezeichnung column).
    end_ys = []
    for x0, y0, _x1, _y1, w, *_ in words:
        if w == "Nettobetrag" and x0 > 330:
            end_ys.append(y0)
        if w == "Übertrag" and x0 < 200 and y0 > table_header_y + 30:
            end_ys.append(y0)
    y_end = min(end_ys) - 1.0 if end_ys else 800.0

    return (y_start, y_end)


def _last_numeric_token(
    tokens: list[tuple[float, str]],
    include_minus_suffix: bool = False,
) -> str | None:
    """Return the rightmost numeric-looking token in a row."""
    for _x, word in reversed(sorted(tokens, key=lambda t: t[0])):
        if word in ("EUR", "€", "%", "USt"):
            continue
        # German number: digits with optional thousands dots and decimal comma.
        # Optionally ends with '-' for credit notes.
        pattern = r"^\d[\d.,]*-?$" if include_minus_suffix else r"^\d[\d.,]*$"
        if re.match(pattern, word):
            return word
    return None


def _extract_line_items_from_page(
    words: list[tuple[float, float, float, float, str]],
    page_no: int,
) -> list[dict]:
    """Extract line-item rows from one page of a legacy invoice.

    Only processes words from a single page to prevent cross-page row merging.
    Returns a list of partial item dicts (may need description continuation
    folding from the caller).
    """
    y_start, y_end = _find_table_y_bounds(words, page_no)
    rows = _group_into_rows(words, y_start, y_end)

    items: list[dict] = []
    pending_continuation: list[str] = []
    pending_item: dict | None = None

    for row in rows:
        pos_tokens = row.get("pos", [])
        art_tokens = row.get("art_nr", [])

        # ── Continuation description row ──────────────────────────────────
        # A row with description text but no position or article number.
        if not pos_tokens and not art_tokens and row.get("description"):
            desc_text = " ".join(row["description"])
            # Ignore carry-forward rows ("Übertrag von Seite X")
            if "Übertrag" in desc_text:
                continue
            if pending_item is not None:
                pending_item["description"] += " " + desc_text
            continue

        # ── Carry-forward row (has a position-area token but no art_nr) ──
        # "Übertrag" also shows up in the gesamt column area as a value row.
        if not art_tokens:
            continue

        # ── Save any pending item ─────────────────────────────────────────
        if pending_item is not None:
            items.append(pending_item)

        # ── Parse the item row ────────────────────────────────────────────
        if not pos_tokens:
            pending_item = None
            continue
        raw_pos = pos_tokens[0]
        position = int(raw_pos)
        article_num = art_tokens[0]
        description = " ".join(row.get("description", []))

        # Menge (quantity) — required
        menge_tokens = row.get("menge", [])
        if not menge_tokens:
            raise ValueError(
                f"No quantity found for Pos {position} (Art.-Nr. {article_num})"
            )
        quantity = parse_german_number(menge_tokens[0])

        # ME (unit) — required
        me_tokens = row.get("me", [])
        if not me_tokens:
            raise ValueError(
                f"No unit found for Pos {position} (Art.-Nr. {article_num})"
            )
        unit = me_tokens[0]

        # Einzelpreis — required
        ep_tokens = row.get("einzelpreis", [])
        ep_str = "".join(t for t in ep_tokens if t != "€").strip()
        if not ep_str:
            raise ValueError(
                f"No unit_price found for Pos {position} (Art.-Nr. {article_num})"
            )
        unit_price = parse_german_number(ep_str)

        # PE (price unit) — blank is valid and means 1
        pe_tokens = row.get("pe", [])
        price_unit = parse_german_number(pe_tokens[0]) if pe_tokens else Decimal("1")

        # Rab.% (discount) — blank means null
        rab_tokens = row.get("rab", [])
        discount_percent: Decimal | None = (
            parse_german_number(rab_tokens[0]) if rab_tokens else None
        )

        # Gesamt € (line total) — required, stored as printed (BR-01)
        gesamt_tokens = row.get("gesamt", [])
        gesamt_str = "".join(t for t in gesamt_tokens if t != "€").strip()
        if not gesamt_str:
            raise ValueError(
                f"No line_total found for Pos {position} (Art.-Nr. {article_num})"
            )
        line_total = parse_german_number(gesamt_str)

        # USt % (VAT rate) — required
        ust_tokens = row.get("ust", [])
        if not ust_tokens:
            raise ValueError(
                f"No VAT rate found for Pos {position} (Art.-Nr. {article_num})"
            )
        vat_rate = int(parse_german_number(ust_tokens[0]))

        pending_item = {
            "position":         position,
            "article_number":   article_num,
            "description":      description,
            "quantity":         quantity,
            "unit":             unit,
            "unit_price":       unit_price,
            "price_unit":       price_unit,
            "discount_percent": discount_percent,
            "line_total":       line_total,
            "vat_rate":         vat_rate,
        }

    # Don't forget the last item.
    if pending_item is not None:
        items.append(pending_item)

    return items


def _extract_totals(
    words: list[tuple[float, float, float, float, str]],
) -> dict:
    """Extract printed totals from the legacy totals block on one page.

    The totals block is at x > 330, y > 250 (on any page).
    Handles both positive invoices and negative credit notes (trailing minus).

    Raises:
        ValueError: If the gross total is missing, or if net/VAT amounts
                    cannot be found for every VAT rate present in the block.
    """
    totals_words = [
        (x0, y0, word) for x0, y0, _x1, _y1, word in words
        if x0 > 330 and y0 > 250
    ]

    net_by_vat: dict[str, Decimal] = {}
    vat_by_vat: dict[str, Decimal] = {}
    gross_total: Decimal | None = None

    rows: dict[float, list[tuple[float, str]]] = {}
    for x0, y0, word in totals_words:
        matched_y = None
        for ey in rows:
            if abs(ey - y0) < _ROW_Y_TOL:
                matched_y = ey
                break
        if matched_y is None:
            matched_y = y0
            rows[matched_y] = []
        rows[matched_y].append((x0, word))

    for y, tokens in sorted(rows.items()):
        text_tokens = sorted(tokens, key=lambda t: t[0])
        row_text = " ".join(w for _, w in text_tokens)

        # "Nettobetrag 19 % USt  4.787,18"
        m = re.search(r"Nettobetrag\s+(\d+)\s*%\s*USt", row_text)
        if m:
            rate = m.group(1)
            amount_str = _last_numeric_token(tokens, include_minus_suffix=True)
            if amount_str:
                net_by_vat[rate] = parse_german_number(amount_str)
            continue

        # "zzgl. 19 % USt auf 4.787,18  909,56"
        m = re.search(r"zzgl\.\s+(\d+)\s*%\s*USt", row_text)
        if m:
            rate = m.group(1)
            amount_str = _last_numeric_token(tokens, include_minus_suffix=True)
            if amount_str:
                vat_by_vat[rate] = parse_german_number(amount_str)
            continue

        # "Rechnungsbetrag  953,75 EUR" or "Gutschriftsbetrag  476,06- EUR"
        if "Rechnungsbetrag" in row_text or "Gutschriftsbetrag" in row_text:
            amount_str = _last_numeric_token(tokens, include_minus_suffix=True)
            if amount_str:
                gross_total = parse_german_number(amount_str)

    # Validate that the gross total was found.
    if gross_total is None:
        raise ValueError(
            "Could not extract gross_total: 'Rechnungsbetrag' or "
            "'Gutschriftsbetrag' row not found in totals block."
        )

    # Validate that net and VAT dicts have matching keys.
    net_rates = set(net_by_vat.keys())
    vat_rates = set(vat_by_vat.keys())
    if net_rates != vat_rates:
        raise ValueError(
            f"Mismatch between net VAT-rate keys {net_rates} and "
            f"VAT amount keys {vat_rates} in totals block."
        )

    # Validate that every net and VAT rate has a non-None amount.
    for rate, amount in net_by_vat.items():
        if amount is None:
            raise ValueError(f"Missing net amount for VAT rate {rate!r}.")
    for rate, amount in vat_by_vat.items():
        if amount is None:
            raise ValueError(f"Missing VAT amount for VAT rate {rate!r}.")

    net_total = sum(net_by_vat.values(), Decimal("0")) if net_by_vat else Decimal("0")
    vat_total = sum(vat_by_vat.values(), Decimal("0")) if vat_by_vat else Decimal("0")

    return {
        "net_by_vat_rate": net_by_vat,
        "vat_by_vat_rate": vat_by_vat,
        "net_total":        net_total,
        "vat_total":        vat_total,
        "gross_total":      gross_total,
    }


def _extract_payment_terms(text: str, document_date: str | None) -> dict:
    """Extract due_date and cash_discount from the payment terms text.

    Handles:
      - Absolute Skonto: "Bei Zahlung bis DD.MM.YYYY abzüglich N % Skonto (= X EUR)."
      - Relative Skonto: "innerhalb von N Tagen ab Rechnungsdatum N % Skonto (= X EUR)."
      - No Skonto.
    """
    due_date: str | None = None
    cash_discount = None

    m = re.search(r"Zahlbar bis (\d{2}\.\d{2}\.\d{4})", text)
    if m:
        due_date = parse_german_date(m.group(1))

    # Absolute Skonto date
    m = re.search(
        r"Bei Zahlung bis (\d{2}\.\d{2}\.\d{4})\s+abzüglich\s+([\d,]+)\s*%\s*Skonto"
        r"\s*\(=\s*([\d,.]+)\s*EUR\)",
        text,
    )
    if m:
        cash_discount = {
            "percent": parse_german_number(m.group(2)),
            "until":   parse_german_date(m.group(1)),
            "amount":  parse_german_number(m.group(3)),
        }

    # Relative Skonto: "innerhalb von N Tagen ab Rechnungsdatum N % Skonto"
    if cash_discount is None:
        m = re.search(
            r"innerhalb von (\d+) Tagen ab Rechnungsdatum\s+([\d,]+)\s*%\s*Skonto"
            r"\s*\(=\s*([\d,.]+)\s*EUR\)",
            text,
        )
        if m and document_date is not None:
            n_days = int(m.group(1))
            # Derive absolute date [I] — interpreted, not printed.
            # INV-04: 2026-10-14 + 7 days = 2026-10-21
            until = add_days(document_date, n_days)
            cash_discount = {
                "percent": parse_german_number(m.group(2)),
                "until":   until,   # [I] derived from relative term
                "amount":  parse_german_number(m.group(3)),
            }

    return {"due_date": due_date, "cash_discount": cash_discount}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_legacy_invoice(pdf_path: Path) -> dict:
    """Parse a Kessler legacy-layout invoice or credit note PDF.

    Processes each page independently to prevent cross-page coordinate mixing.
    All printed monetary values are stored as extracted (BR-01).

    Args:
        pdf_path: Path to the legacy-layout PDF.

    Returns:
        A dict conforming to input/output_schema.json.

    Raises:
        ValueError: If a required field cannot be extracted.
    """
    with open_pdf(pdf_path) as doc:
        pages_text = extract_pages_text(doc)
        # Collect per-page word lists — do NOT flatten into one list.
        pages_words: list[list[tuple[float, float, float, float, str]]] = []
        for page_no, _ in pages_text:
            pages_words.append(extract_page_words(doc, page_no))

    full_text = "\n".join(t for _, t in pages_text)
    page1_words = pages_words[0]

    # ── Document type ────────────────────────────────────────────────────
    document_type = "credit_note" if "GUTSCHRIFT" in full_text else "invoice"

    # ── Header (from page 1) ──────────────────────────────────────────────
    if document_type == "credit_note":
        raw_doc_no = _first_word_after_label(page1_words, "Gutschrift-Nr.")
    else:
        raw_doc_no = _first_word_after_label(page1_words, "Rechnungs-Nr.")

    if not raw_doc_no:
        raise ValueError(f"Could not find document_number in: {pdf_path}")

    document_number = raw_doc_no
    raw_datum = _first_word_after_label(page1_words, "Datum")
    document_date = parse_german_date(raw_datum) if raw_datum else None

    raw_ld = _first_word_after_label(page1_words, "Leistungsdatum")
    service_date = parse_german_date(raw_ld) if raw_ld else None

    order_ref_raw = _get_bestellung_value(page1_words)
    order_reference = None
    if order_ref_raw:
        order_reference = re.sub(
            r"\s+vom\s+\d{2}\.\d{2}\.\d{4}$", "", order_ref_raw
        ).strip() or None

    delivery_note_number = _first_word_after_label(page1_words, "Lieferschein-Nr.")

    referenced_invoice = None
    if document_type == "credit_note":
        referenced_invoice = _get_bezug_rechnung(page1_words)

    # ── Supplier ──────────────────────────────────────────────────────────
    vat_match = re.search(r"USt-IdNr\.\s+(DE\d{9})", full_text)
    if not vat_match:
        raise ValueError(f"Could not find supplier VAT ID in: {pdf_path}")
    supplier = {
        "name":   "Kessler Industrietechnik GmbH",
        "vat_id": vat_match.group(1),
    }

    # ── Buyer (from page 1) ────────────────────────────────────────────────
    buyer_addr = _extract_buyer_address(page1_words)
    customer_number = _first_word_after_label(page1_words, "Kunden-Nr.") or ""
    buyer = {
        "name":            buyer_addr["name"],
        "street":          buyer_addr["street"],
        "postal_code":     buyer_addr["postal_code"],
        "city":            buyer_addr["city"],
        "customer_number": customer_number,
    }

    # ── Line items — process each page independently ──────────────────────
    all_items: list[dict] = []
    for page_idx, page_words in enumerate(pages_words):
        page_no = page_idx + 1
        page_items = _extract_line_items_from_page(page_words, page_no)
        all_items.extend(page_items)

    # ── Totals — find the page containing 'Nettobetrag' ───────────────────
    totals_words: list[tuple[float, float, float, float, str]] = []
    for page_words in pages_words:
        has_netto = any(
            w == "Nettobetrag"
            for _x0, _y0, _x1, _y1, w in page_words
        )
        if has_netto:
            totals_words = page_words
            break

    if not totals_words:
        raise ValueError(
            f"Could not find totals page: no 'Nettobetrag' marker found "
            f"in any page of {pdf_path}"
        )

    totals_raw = _extract_totals(totals_words)
    totals = {
        "net_by_vat_rate": totals_raw["net_by_vat_rate"],
        "vat_by_vat_rate": totals_raw["vat_by_vat_rate"],
        "net_total":        totals_raw["net_total"],
        "vat_total":        totals_raw["vat_total"],
        "gross_total":      totals_raw["gross_total"],
    }

    # ── Payment terms ──────────────────────────────────────────────────────
    payment = _extract_payment_terms(full_text, document_date)
    due_date = payment["due_date"]
    cash_discount = payment["cash_discount"]

    # ── Assemble result ────────────────────────────────────────────────────
    return {
        "document_type":        document_type,
        "document_number":      document_number,
        "document_date":        document_date,
        "service_date":         service_date,
        "due_date":             due_date,
        "currency":             "EUR",
        "supplier":             supplier,
        "buyer":                buyer,
        "order_reference":      order_reference,
        "delivery_note_number": delivery_note_number,
        "referenced_invoice":   referenced_invoice,
        "line_items":           all_items,
        "totals":               totals,
        "cash_discount":        cash_discount,
    }


def extract_and_write(pdf_path: Path, output_path: Path) -> dict:
    """Parse a legacy invoice, validate against the schema, and write to disk."""
    schema = load_schema(_SCHEMA_PATH)
    result = parse_legacy_invoice(pdf_path)
    validate_output(result, schema)
    write_json(result, output_path)
    return result
