"""
parsers/layout_modern.py

Extracts structured invoice data from Kessler Industrietechnik GmbH PDF
documents that use the modern layout (INV-05 and later).

Modern layout — key differences from legacy:
  - Metadata labels on the LEFT (x≈51), values to their right (x≈147)
  - Logo and 'seit 1987' tagline top-right
  - Buyer address on the RIGHT (x≈334+)
  - 'z. Hd.' attention line excluded from buyer.name (not 'Abt.')
  - 'DEUTSCHLAND' country line: no schema field, discarded
  - Date format: 'D. Monatname YYYY' (long German) — uses parse_german_date()
  - Table column headers: Pos | Menge Einh. | Artikel | Beschreibung |
    Preis/Einh. | MwSt | Betrag
  - NO PE column — price_unit = Decimal("1") for all items
  - Discounts shown as standalone 'abzgl.' rows, not in a Rab.% column
  - Preis/Einh. values include trailing '€' symbol
  - MwSt values include trailing '%' symbol (e.g. '19%', '7%')
  - Totals: 'Summe netto' (combined, no per-rate net labels)
    → net_by_vat_rate must be DERIVED from line items [D]

Modern layout column x-boundaries (from Phase 2 word-coordinate analysis):
  Pos         x ≈  51–76
  Menge       x ≈  77–107
  Einh.       x ≈ 108–141
  Artikel     x ≈ 142–209
  Beschreibung x ≈ 210–425
  Preis/Einh. x ≈ 426–477
  MwSt        x ≈ 478–541
  Betrag      x ≈ 542–595
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from helpers.dates import parse_german_date
from helpers.numbers import parse_german_number
from helpers.pdf_reader import extract_page_words, extract_pages_text, open_pdf
from helpers.schema_io import load_schema, validate_output, write_json

# ---------------------------------------------------------------------------
# Column x-range boundaries for the modern layout.
# ---------------------------------------------------------------------------
_MOD_COL_BOUNDS: dict[str, tuple[float, float]] = {
    "pos":          ( 45.0,  77.0),
    "menge":        ( 77.0, 107.0),   # "30" at x=92.60; stops before 107
    "einh":         (107.0, 141.0),   # "Stk" at x=107.72
    "artikel":      (141.0, 209.0),   # "KI-40112" at x=141.73
    "beschreibung": (209.0, 426.0),   # "abzgl." and descriptions at x=209.76+
    "preis":        (426.0, 478.0),
    "mwst":         (478.0, 530.0),
    "betrag":       (530.0, 595.0),
}

_ROW_Y_TOL = 3.0
_SCHEMA_PATH = Path("input/output_schema.json")

# Y-bounds for line-item rows on the single modern page.
# Table header at y≈257; items start below that; totals start at y≈393.
_ITEMS_Y_MIN = 269.0
_ITEMS_Y_MAX = 390.0


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------

def _mod_col(x0: float) -> str | None:
    """Return the modern-layout column name for a word at x0."""
    for name, (lo, hi) in _MOD_COL_BOUNDS.items():
        if lo <= x0 < hi:
            return name
    return None


def _group_rows(
    words: list[tuple[float, float, float, float, str]],
    y_min: float,
    y_max: float,
) -> list[dict[str, list[str]]]:
    """Group word tokens into rows by approximate y-position."""
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
        col = _mod_col(x0)
        if col is not None:
            rows[matched_y].setdefault(col, []).append(word)
    return [rows[y] for y in sorted(rows)]


def _label_value(
    words: list[tuple[float, float, float, float, str]],
    label: str,
    x_label_max: float = 200.0,
    x_value_min: float = 140.0,
    x_value_max: float = 330.0,  # stop before right-side supplier/buyer block
) -> str | None:
    """Find the value on the same y-band as a left-side metadata label."""
    label_y: float | None = None
    label_x1: float | None = None
    for x0, y0, x1, _y1, word in words:
        if word == label and x0 < x_label_max:
            label_y = y0
            label_x1 = x1
            break
    if label_y is None:
        return None
    tokens = []
    for x0, y0, _x1, _y1, word in words:
        if (abs(y0 - label_y) < _ROW_Y_TOL
                and x0 >= x_value_min
                and x0 > (label_x1 or 0)
                and x0 < x_value_max):
            tokens.append((x0, word))
    tokens.sort(key=lambda t: t[0])
    return " ".join(w for _, w in tokens) if tokens else None


def _extract_modern_buyer(
    words: list[tuple[float, float, float, float, str]],
) -> dict:
    """Extract buyer name and address from the right-side block (x≈334+).

    Modern address block order (confirmed from Phase 2 coordinates):
      y≈130: company name   "Rheinwerk Anlagenbau AG"
      y≈144: attention line "z. Hd. Kreditorenbuchhaltung"  ← excluded
      y≈157: street         "Hafenstraße 88"
      y≈170: postal + city  "47119 Duisburg"
      y≈183: country        "DEUTSCHLAND"  ← no schema field, discarded
    """
    addr_words = [
        (x0, y0, word) for x0, y0, _x1, _y1, word in words
        if x0 >= 330 and 125 < y0 < 200
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
        (y, " ".join(w for _, w in sorted(tokens, key=lambda t: t[0])))
        for y, tokens in sorted(rows.items())
    ]

    # Filter out attention line ("z. Hd.") and country line ("DEUTSCHLAND")
    usable = [
        text for _y, text in sorted_rows
        if not text.startswith("z.") and text != "DEUTSCHLAND"
    ]

    name     = usable[0] if len(usable) > 0 else ""
    street   = usable[1] if len(usable) > 1 else ""
    pc_city  = usable[2] if len(usable) > 2 else ""
    parts    = pc_city.split()
    postal_code = parts[0] if parts else ""
    city = " ".join(parts[1:]) if len(parts) > 1 else ""

    return {"name": name, "street": street, "postal_code": postal_code, "city": city}


def _extract_modern_line_items(
    words: list[tuple[float, float, float, float, str]],
) -> list[dict]:
    """Extract line items from the modern table using word bounding boxes.

    Handles:
    - Leading-zero position numbers ('001' → 1)
    - Menge/Einh. merged into adjacent columns (Menge at x≈77, Einh. at x≈108)
    - Preis/Einh. with trailing '€' symbol — stripped before parsing
    - MwSt with trailing '%' symbol — stripped before parsing
    - Betrag with trailing '€' symbol — stripped before parsing
    - No PE column — price_unit = Decimal("1") for all items
    - Standalone 'abzgl.' discount row folded into the preceding item
    - Continuation description rows appended to the preceding item
    """
    rows = _group_rows(words, _ITEMS_Y_MIN, _ITEMS_Y_MAX)

    items: list[dict] = []
    pending_item: dict | None = None

    for row in rows:
        pos_tokens = row.get("pos", [])
        artikel_tokens = row.get("artikel", [])
        beschreibung_tokens = row.get("beschreibung", [])
        beschreibung_text = " ".join(beschreibung_tokens)

        # ── Standalone discount row: starts with 'abzgl.' ─────────────────
        # "abzgl." at x=209.76 lands in beschreibung (209–426).
        # It has no pos token.
        if not pos_tokens and beschreibung_text.startswith("abzgl."):
            # Extract discount percent from the beschreibung text: "3 %" → "3"
            disc_match = re.search(r"(\d[\d,]*)\s*%", beschreibung_text)
            if disc_match and pending_item is not None:
                pending_item["discount_percent"] = parse_german_number(disc_match.group(1))
                # Extract discount amount from betrag column (e.g. "-13,97")
                betrag_tokens = row.get("betrag", [])
                betrag_str = "".join(t for t in betrag_tokens if t != "€").strip()
                if betrag_str:
                    discount_amount = parse_german_number(betrag_str)
                    # line_total = pre-discount amount + discount_amount (which is negative)
                    # [D] derived: 465.60 + (-13.97) = 451.63
                    pending_item["line_total"] = pending_item["line_total"] + discount_amount
            continue

        # ── Continuation description row ───────────────────────────────────
        # Has neither pos nor artikel, but has beschreibung text.
        # Must not be an abzgl. row (those are caught above).
        if not pos_tokens and not artikel_tokens and beschreibung_tokens:
            if pending_item is not None:
                pending_item["description"] += " " + beschreibung_text
            continue

        # ── Regular item row ────────────────────────────────────────────────
        if pos_tokens and artikel_tokens:
            # Save previous pending item
            if pending_item is not None:
                items.append(pending_item)

            position = int(pos_tokens[0])  # strip leading zeros: "001" → 1
            article_num = artikel_tokens[0]
            description = beschreibung_text

            menge_tokens = row.get("menge", [])
            if not menge_tokens:
                raise ValueError(f"No quantity for Pos {position} ({article_num})")
            quantity = parse_german_number(menge_tokens[0])

            einh_tokens = row.get("einh", [])
            if not einh_tokens:
                raise ValueError(f"No unit for Pos {position} ({article_num})")
            unit = einh_tokens[0]

            # Preis/Einh. — strip '€' and parse
            preis_tokens = row.get("preis", [])
            preis_str = "".join(t for t in preis_tokens if t != "€").strip()
            if not preis_str:
                raise ValueError(f"No unit_price for Pos {position} ({article_num})")
            unit_price = parse_german_number(preis_str)

            # No PE column in modern layout — always 1
            price_unit = Decimal("1")
            discount_percent = None

            # MwSt — strip '%' and parse as integer
            mwst_tokens = row.get("mwst", [])
            mwst_str = "".join(t for t in mwst_tokens if t != "%").strip()
            if not mwst_str:
                raise ValueError(f"No VAT rate for Pos {position} ({article_num})")
            vat_rate = int(parse_german_number(mwst_str))

            # Betrag — strip '€', may be negative for credit notes
            betrag_tokens = row.get("betrag", [])
            betrag_str = "".join(t for t in betrag_tokens if t != "€").strip()
            if not betrag_str:
                raise ValueError(f"No line_total for Pos {position} ({article_num})")
            line_total = parse_german_number(betrag_str)

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

    if pending_item is not None:
        items.append(pending_item)

    return items


def _extract_modern_totals(
    words: list[tuple[float, float, float, float, str]],
    line_items: list[dict],
) -> dict:
    """Extract modern-layout totals.

    The modern layout prints only:
      'Summe netto'  — combined net total [P]
      'MwSt 19%'     — VAT for 19% group [P]
      'MwSt 7%'      — VAT for 7% group [P]
      'Gesamtbetrag' — gross total [P]

    There are NO printed per-rate net labels. 'net_by_vat_rate' is derived
    from line-item sums grouped by VAT rate [D].

    V2 for INV-05 will therefore pass by construction — the derived per-rate
    nets are compared against themselves. The validation report must disclose
    this limitation.

    Raises:
        ValueError: If gross_total or Summe netto cannot be extracted.
    """
    totals_words = [
        (x0, y0, word) for x0, y0, _x1, _y1, word in words
        if x0 > 330 and y0 > 380
    ]

    net_total: Decimal | None = None
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

    for _y, tokens in sorted(rows.items()):
        text = " ".join(w for _, w in sorted(tokens, key=lambda t: t[0]))

        # "Summe netto  975,13 €"
        if text.startswith("Summe") and "netto" in text:
            amount_str = _rightmost_amount(tokens)
            if amount_str:
                net_total = parse_german_number(amount_str)
            continue

        # "MwSt 19%  175,81 €" or "MwSt 7%  3,49 €"
        m = re.search(r"MwSt\s+(\d+)%", text)
        if m:
            rate = m.group(1)
            amount_str = _rightmost_amount(tokens)
            if amount_str:
                vat_by_vat[rate] = parse_german_number(amount_str)
            continue

        # "Gesamtbetrag  1.154,43 €"
        if "Gesamtbetrag" in text:
            amount_str = _rightmost_amount(tokens)
            if amount_str:
                gross_total = parse_german_number(amount_str)

    if net_total is None:
        raise ValueError("Could not extract net_total: 'Summe netto' not found.")
    if gross_total is None:
        raise ValueError("Could not extract gross_total: 'Gesamtbetrag' not found.")

    # Derive per-VAT-rate nets from line items [D].
    # This is a construction — there are no independently printed per-rate nets.
    net_by_vat: dict[str, Decimal] = {}
    for item in line_items:
        rate_key = str(item["vat_rate"])
        net_by_vat[rate_key] = net_by_vat.get(rate_key, Decimal("0")) + item["line_total"]

    vat_total = sum(vat_by_vat.values(), Decimal("0")) if vat_by_vat else Decimal("0")

    return {
        "net_by_vat_rate": net_by_vat,    # [D] derived from line items
        "vat_by_vat_rate": vat_by_vat,    # [P] printed
        "net_total":        net_total,     # [P] printed as "Summe netto"
        "vat_total":        vat_total,     # [D] sum of vat_by_vat
        "gross_total":      gross_total,   # [P] printed as "Gesamtbetrag"
    }


def _rightmost_amount(tokens: list[tuple[float, str]]) -> str | None:
    """Return the rightmost token that looks like a German number."""
    for _x, word in reversed(sorted(tokens, key=lambda t: t[0])):
        if word in ("€", "%", "netto"):
            continue
        if re.match(r"^\d[\d.,]*-?$", word):
            return word
    return None


def _extract_modern_payment_terms(text: str) -> dict:
    """Extract due_date and cash_discount from modern payment-terms text.

    Modern format: "Zahlungsziel: 30 Tage netto (bis 18. November 2026). Kein Skontoabzug."
    """
    due_date: str | None = None

    # "bis 18. November 2026" — long-form German date inside parentheses
    m = re.search(r"bis\s+(\d{1,2}\.\s+\w+\s+\d{4})", text)
    if m:
        due_date = parse_german_date(m.group(1).strip())

    # "Kein Skontoabzug" → cash_discount is null
    cash_discount = None

    return {"due_date": due_date, "cash_discount": cash_discount}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_modern_invoice(pdf_path: Path) -> dict:
    """Parse a Kessler modern-layout invoice PDF.

    Handles the new Kessler invoice format introduced from October 2026
    (INV-05 and later). Uses word bounding boxes for column detection.
    All printed monetary values are stored as extracted (BR-01).

    Args:
        pdf_path: Path to the modern-layout PDF.

    Returns:
        A dict conforming to input/output_schema.json.

    Raises:
        ValueError: If a required field cannot be extracted.
    """
    with open_pdf(pdf_path) as doc:
        pages_text = extract_pages_text(doc)
        all_words = extract_page_words(doc, 1)
    full_text = pages_text[0][1]

    # ── Document type ─────────────────────────────────────────────────────
    # Modern layout always uses "Rechnung" heading — invoices only in dataset.
    document_type = "invoice"

    # ── Document number: "Rechnung Nr.  2026-R-00117" ─────────────────────
    # "Nr." is at x≈94 y≈53; value is at x≈147 on the same y-band.
    document_number = _label_value(all_words, "Nr.")
    if not document_number:
        raise ValueError(f"Could not find document_number in: {pdf_path}")

    # ── Dates (long-form German) ──────────────────────────────────────────
    raw_doc_date_tokens = []
    raw_ld_tokens = []

    # Rechnungsdatum label is at x≈51, y≈65; values follow at x≈147
    # We need to collect multi-token dates: "19." "Oktober" "2026"
    for label, store in [("Rechnungsdatum", raw_doc_date_tokens),
                          ("Lieferdatum",    raw_ld_tokens)]:
        label_y: float | None = None
        label_x1: float | None = None
        for x0, y0, x1, _y1, w in all_words:
            if w == label and x0 < 200:
                label_y = y0
                label_x1 = x1
                break
        if label_y is not None:
            for x0, y0, _x1, _y1, w in all_words:
                # Stop before the logo area (x ≥ 430 on y-bands shared with header)
                if abs(y0 - label_y) < _ROW_Y_TOL and x0 > (label_x1 or 0) + 2 and x0 < 430:
                    store.append((x0, w))
            store.sort(key=lambda t: t[0])

    raw_doc_date = " ".join(w for _, w in raw_doc_date_tokens)
    raw_ld       = " ".join(w for _, w in raw_ld_tokens)

    document_date = parse_german_date(raw_doc_date) if raw_doc_date else None
    service_date  = parse_german_date(raw_ld) if raw_ld else None

    # ── Other header fields ───────────────────────────────────────────────
    customer_number      = _label_value(all_words, "Kundennummer")
    order_ref_raw        = _label_value(all_words, "Bestellnummer")
    delivery_note_number = _label_value(all_words, "Lieferschein")

    # No date suffix to strip for Bestellnummer in the modern layout.
    order_reference = order_ref_raw.strip() if order_ref_raw else None

    # ── Supplier ──────────────────────────────────────────────────────────
    vat_match = re.search(r"USt-IdNr\.\s+(DE\d{9})", full_text)
    if not vat_match:
        raise ValueError(f"Could not find supplier VAT ID in: {pdf_path}")
    supplier = {
        "name":   "Kessler Industrietechnik GmbH",
        "vat_id": vat_match.group(1),
    }

    # ── Buyer (right-side address block) ──────────────────────────────────
    buyer_addr = _extract_modern_buyer(all_words)
    buyer = {
        "name":            buyer_addr["name"],
        "street":          buyer_addr["street"],
        "postal_code":     buyer_addr["postal_code"],
        "city":            buyer_addr["city"],
        "customer_number": customer_number or "",
    }

    # ── Line items ─────────────────────────────────────────────────────────
    line_items = _extract_modern_line_items(all_words)

    # ── Totals ─────────────────────────────────────────────────────────────
    totals_raw = _extract_modern_totals(all_words, line_items)
    totals = {
        "net_by_vat_rate": totals_raw["net_by_vat_rate"],
        "vat_by_vat_rate": totals_raw["vat_by_vat_rate"],
        "net_total":        totals_raw["net_total"],
        "vat_total":        totals_raw["vat_total"],
        "gross_total":      totals_raw["gross_total"],
    }

    # ── Payment terms ──────────────────────────────────────────────────────
    payment = _extract_modern_payment_terms(full_text)
    due_date     = payment["due_date"]
    cash_discount = payment["cash_discount"]

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
        "referenced_invoice":   None,
        "line_items":           line_items,
        "totals":               totals,
        "cash_discount":        cash_discount,
    }


def extract_and_write(pdf_path: Path, output_path: Path) -> dict:
    """Parse a modern invoice, validate against the schema, and write to disk."""
    schema = load_schema(_SCHEMA_PATH)
    result = parse_modern_invoice(pdf_path)
    validate_output(result, schema)
    write_json(result, output_path)
    return result
