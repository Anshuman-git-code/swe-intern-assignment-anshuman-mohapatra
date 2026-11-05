"""
helpers/pdf_reader.py

Safe PDF opening and text/word extraction using PyMuPDF (pymupdf 2.1).

Three functions are provided:
  open_pdf              — context manager; opens and closes the document safely.
  extract_pages_text    — plain text per page (1-based page numbers).
  extract_page_words    — word bounding boxes per page for column detection.

None of these functions contain Kessler-specific parsing logic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pymupdf


@contextmanager
def open_pdf(path: Path) -> Iterator[pymupdf.Document]:
    """Context manager that opens a PDF file safely and yields the Document.

    Opens the file using PyMuPDF, checks for password protection, and yields
    the open Document.  The document is always closed when the context exits,
    even if an exception is raised inside the with-block.

    Usage:
        with open_pdf(Path("input/INV-01_RE-2026-10418.pdf")) as doc:
            pages = extract_pages_text(doc)
        # doc is closed here automatically

    Args:
        path: Path to the PDF file.

    Yields:
        An open pymupdf.Document.

    Raises:
        FileNotFoundError: The file does not exist.
        ValueError:        The file is corrupt, empty, or password-protected.
                           The original PyMuPDF exception is chained as the cause.
    """
    # Raise FileNotFoundError before pymupdf sees the path, so the error
    # message clearly names the missing file.
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    # pymupdf.open() raises FileDataError (a subclass of RuntimeError) for
    # corrupt files and EmptyFileError (a subclass of FileDataError) for
    # zero-byte files.  Both are caught here and re-raised as ValueError
    # with the original exception chained for debugging.
    try:
        doc = pymupdf.open(str(path))
    except pymupdf.FileDataError as exc:
        raise ValueError(
            f"Cannot open PDF (corrupt or not a valid PDF file): {path}. "
            f"Original error: {exc}"
        ) from exc

    # Detect password protection.  needs_pass is non-zero when the document
    # is encrypted and has not yet been authenticated.
    if doc.needs_pass:
        doc.close()
        raise ValueError(
            f"PDF is password-protected and cannot be read: {path}"
        )

    # Yield inside try/finally so the document is closed even if the caller's
    # code raises an exception inside the with-block.
    try:
        yield doc
    finally:
        doc.close()


def extract_pages_text(doc: pymupdf.Document) -> list[tuple[int, str]]:
    """Extract plain text from every page of an open PDF document.

    Returns a list of (page_number, text) tuples.  Page numbers are 1-based
    to match what is printed on the document footer (e.g. "Seite 1 von 3").

    Image-only pages (like INV-06) return an empty string rather than raising
    an error.  The caller decides how to handle empty text.

    Args:
        doc: An open pymupdf.Document, typically from open_pdf().

    Returns:
        A list of (page_number, text) tuples, one per page.
        Page numbers start at 1.
    """
    result = []
    for zero_based_idx in range(doc.page_count):
        page = doc[zero_based_idx]
        text = page.get_text()          # returns "" for image-only pages
        result.append((zero_based_idx + 1, text))
    return result


def extract_page_words(
    doc: pymupdf.Document,
    page_number: int,
) -> list[tuple[float, float, float, float, str]]:
    """Extract word-level bounding boxes from one page of an open PDF document.

    Plain text extraction (get_text) does not preserve column positions.
    This function returns each word with its (x0, y0, x1, y1) bounding box
    in points (1 point = 1/72 inch), origin at the top-left corner.

    Parsers use x-coordinates to assign tokens to the correct column.
    For example, on INV-01 page 1 the "PE" header is at x≈459.9 and the
    "Rab." header is at x≈477.9 — distinguishable only with coordinates.

    Image-only pages return an empty list rather than raising an error.

    Note: float() is used here for bounding-box coordinates — geometric
    measurements, not financial values.  All financial values use Decimal.

    Args:
        doc:         An open pymupdf.Document.
        page_number: 1-based page number (1 = first page).

    Returns:
        A list of (x0, y0, x1, y1, word) tuples.

    Raises:
        ValueError: If page_number < 1 or page_number > doc.page_count.
    """
    if page_number < 1 or page_number > doc.page_count:
        raise ValueError(
            f"page_number {page_number} is out of range for a document "
            f"with {doc.page_count} page(s). Valid range: 1–{doc.page_count}."
        )

    # page_number is 1-based; PyMuPDF's index is 0-based.
    page = doc[page_number - 1]

    # get_text("words") returns tuples:
    # (x0, y0, x1, y1, word, block_no, line_no, word_no)
    # We keep only the first 5 elements (position + word text).
    # float() here converts PyMuPDF's coordinate values — geometric, not financial.
    raw_words = page.get_text("words")
    return [(float(x0), float(y0), float(x1), float(y1), word)
            for x0, y0, x1, y1, word, *_ in raw_words]
