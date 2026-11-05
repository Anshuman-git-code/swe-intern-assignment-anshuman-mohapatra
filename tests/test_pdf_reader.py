"""
tests/test_pdf_reader.py

Unit tests for helpers.pdf_reader.

Uses actual project PDFs from input/.  Corrupt-file tests use tempfile so
no supplied source files are modified.

How to run:
    source .venv/bin/activate
    pytest tests/test_pdf_reader.py -v
"""

import tempfile
from pathlib import Path

import pytest
import pymupdf

from helpers.pdf_reader import extract_page_words, extract_pages_text, open_pdf

# ---------------------------------------------------------------------------
# Real PDF paths — verified present in the project.
# ---------------------------------------------------------------------------
INV_01 = Path("input/INV-01_RE-2026-10418.pdf")
INV_02 = Path("input/INV-02_RE-2026-10431.pdf")
INV_06 = Path("input/INV-06_BONUS_scan_RE-2026-10466.pdf")


# ===========================================================================
# open_pdf — context manager behaviour
# ===========================================================================

class TestOpenPdf:
    """Verify safe opening, yielding, and closing of PDF documents."""

    def test_open_inv01_one_page(self) -> None:
        # INV-01 is a single-page invoice.
        with open_pdf(INV_01) as doc:
            assert doc.page_count == 1

    def test_open_inv02_three_pages(self) -> None:
        # INV-02 is a three-page invoice.
        with open_pdf(INV_02) as doc:
            assert doc.page_count == 3

    def test_document_closed_after_context(self) -> None:
        # After the with-block ends, doc.is_closed must be True.
        with open_pdf(INV_01) as doc:
            pass   # just open and exit immediately
        assert doc.is_closed

    def test_missing_file_raises_file_not_found(self) -> None:
        # A path that does not exist must raise FileNotFoundError (not ValueError).
        with pytest.raises(FileNotFoundError):
            with open_pdf(Path("input/nonexistent_file.pdf")) as doc:
                pass  # pragma: no cover

    def test_corrupt_pdf_raises_value_error_with_cause(self) -> None:
        # A file whose content is not a valid PDF must raise ValueError.
        # The original pymupdf.FileDataError must be chained as the cause.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"THIS IS NOT A PDF")
            corrupt_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                with open_pdf(corrupt_path) as doc:
                    pass  # pragma: no cover
            # The original PyMuPDF exception must be chained as __cause__.
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, pymupdf.FileDataError)
        finally:
            corrupt_path.unlink(missing_ok=True)


# ===========================================================================
# extract_pages_text
# ===========================================================================

class TestExtractPagesText:
    """Verify per-page text extraction with 1-based page numbers."""

    def test_inv01_returns_one_tuple(self) -> None:
        # INV-01 has one page → one (page_no, text) tuple.
        with open_pdf(INV_01) as doc:
            pages = extract_pages_text(doc)
        assert len(pages) == 1
        assert pages[0][0] == 1                         # 1-based page number
        assert pages[0][1].startswith("KESSLER")        # first token on the page

    def test_inv02_returns_three_tuples_with_correct_numbers(self) -> None:
        # INV-02 has three pages; page numbers must be 1, 2, 3.
        with open_pdf(INV_02) as doc:
            pages = extract_pages_text(doc)
        assert len(pages) == 3
        assert [p[0] for p in pages] == [1, 2, 3]

    def test_inv06_image_only_returns_empty_string(self) -> None:
        # INV-06 is a scanned image — no embedded text layer.
        # extract_pages_text must return one tuple with an empty string,
        # not raise an error.
        with open_pdf(INV_06) as doc:
            pages = extract_pages_text(doc)
        assert len(pages) == 1
        assert pages[0][0] == 1
        assert pages[0][1] == ""


# ===========================================================================
# extract_page_words
# ===========================================================================

class TestExtractPageWords:
    """Verify word bounding-box extraction and error handling."""

    def test_inv01_pe_column_header_present(self) -> None:
        # On INV-01 page 1, the "PE" column header appears at x≈459.9.
        # This confirms coordinate-based extraction works correctly.
        with open_pdf(INV_01) as doc:
            words = extract_page_words(doc, 1)

        pe_words = [w for w in words if w[4] == "PE"]
        assert len(pe_words) >= 1, "Expected 'PE' token in INV-01 word list"
        # x0 of the PE header should be close to 459.9 (within 2 pts tolerance).
        assert abs(pe_words[0][0] - 459.9) < 2.0, (
            f"PE token x0 = {pe_words[0][0]}, expected ≈459.9"
        )

    def test_page_number_zero_raises_value_error(self) -> None:
        # Page numbers are 1-based; 0 is invalid.
        with open_pdf(INV_01) as doc:
            with pytest.raises(ValueError):
                extract_page_words(doc, 0)

    def test_page_number_too_large_raises_value_error(self) -> None:
        # INV-01 has 1 page; requesting page 2 must raise ValueError.
        with open_pdf(INV_01) as doc:
            with pytest.raises(ValueError):
                extract_page_words(doc, 99)

    def test_inv06_image_only_returns_empty_list(self) -> None:
        # INV-06 has no text layer; word extraction must return [],
        # not raise an error.
        with open_pdf(INV_06) as doc:
            words = extract_page_words(doc, 1)
        assert words == []
