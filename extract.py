#!/usr/bin/env python3
"""
extract.py — Kessler Industrietechnik GmbH invoice extractor.

Usage:
    python extract.py <path-to-pdf>

Output:
    outputs/<pdf-filename>.json   (validated against input/output_schema.json)

Exit codes:
    0  success
    1  usage error or file not found
    2  processing error (parse failure, schema validation failure)
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# All imports must succeed before any CLI work begins.
# ---------------------------------------------------------------------------
try:
    from helpers.pdf_reader import open_pdf, extract_pages_text
    from helpers.schema_io import load_schema, validate_output, write_json
    from parsers.layout_legacy import parse_legacy_invoice
    from parsers.layout_modern import parse_modern_invoice
except ImportError as exc:
    print(f"Import error: {exc}", file=sys.stderr)
    print("Make sure you have activated the virtual environment:", file=sys.stderr)
    print("  source .venv/bin/activate", file=sys.stderr)
    sys.exit(1)

_SCHEMA_PATH = Path("input/output_schema.json")
_OUTPUTS_DIR = Path("outputs")


def detect_layout(pdf_path: Path) -> str:
    """Detect the invoice layout by inspecting the first page's text.

    Returns:
        "modern" if the document contains the modern-layout anchor "Rechnung Nr."
        "legacy" for all other Kessler documents (invoices and credit notes).

    Detection uses structural text anchors, not the document filename or number.
    """
    with open_pdf(pdf_path) as doc:
        pages = extract_pages_text(doc)
    text = pages[0][1] if pages else ""
    # Modern layout is identified by its distinctive invoice-number label.
    if "Rechnung Nr." in text:
        return "modern"
    return "legacy"


def extract_invoice(pdf_path: Path, output_dir: Path = _OUTPUTS_DIR) -> tuple[Path, str]:
    """Extract a single invoice PDF to JSON.

    Args:
        pdf_path:   Path to the source PDF.
        output_dir: Directory to write the JSON output.

    Returns:
        (output_path, layout) — path of the written file and detected layout name.

    Raises:
        FileNotFoundError:  PDF not found.
        ValueError:         Parse or validation failure.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")

    layout = detect_layout(pdf_path)

    # Output filename follows the assignment convention:
    # outputs/<pdf-stem>.json  e.g. outputs/INV-01_RE-2026-10418.json
    output_path = output_dir / (pdf_path.stem + ".json")
    output_dir.mkdir(parents=True, exist_ok=True)

    schema = load_schema(_SCHEMA_PATH)

    if layout == "modern":
        result = parse_modern_invoice(pdf_path)
    else:
        result = parse_legacy_invoice(pdf_path)

    validate_output(result, schema)
    write_json(result, output_path)
    return output_path, layout


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python extract.py <path-to-pdf>\n"
            "Example: python extract.py input/INV-01_RE-2026-10418.pdf",
            file=sys.stderr,
        )
        return 1

    pdf_path = Path(sys.argv[1])

    try:
        output_path, layout = extract_invoice(pdf_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Processing error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 2

    print(f"Layout:   {layout}")
    print(f"Input:    {pdf_path}")
    print(f"Output:   {output_path}")
    print(f"Schema:   valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
