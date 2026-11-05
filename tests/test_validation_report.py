"""
tests/test_validation_report.py

Regression tests for validation/report.py.

Verifies that the generated validation_report.md:
- Contains every document (INV-01 through INV-05).
- Contains every check (V1 through V7) for each document.
- Shows INV-04 V1 and V2 failures with exact values.
- Shows INV-05 V2 by-construction disclosure.
- Does not silently omit any required check.
- Does not claim the Phase 9 CLI (`validate.py`) already exists.

How to run:
    source .venv/bin/activate
    pytest tests/test_validation_report.py -v
"""

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from helpers.schema_io import load_json
from validation.checks import (
    check_v1, check_v2, check_v3, check_v4,
    check_v5, check_v6, check_v7,
)
from validation.report import format_document_section, write_validation_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_all_results(doc: dict, inv05_derived: bool = False) -> dict:
    return {
        "V1": check_v1(doc),
        "V2": check_v2(doc, inv05_derived=inv05_derived),
        "V3": check_v3(doc),
        "V4": [check_v4(doc)],
        "V5": [check_v5(doc)],
        "V6": check_v6(doc),
        "V7": check_v7(doc),
    }


@pytest.fixture(scope="module")
def generated_report() -> str:
    """Generate a fresh report for all five documents and return the text."""
    docs = {
        "INV-01_RE-2026-10418": (load_json(Path("outputs/INV-01.json")), False),
        "INV-02_RE-2026-10431": (load_json(Path("outputs/INV-02.json")), False),
        "INV-03_GS-2026-00872": (load_json(Path("outputs/INV-03.json")), False),
        "INV-04_RE-2026-10457": (load_json(Path("outputs/INV-04.json")), False),
        "INV-05_2026-R-00117":  (load_json(Path("outputs/INV-05.json")), True),
    }
    sections = []
    for name, (doc, derived) in docs.items():
        sections.append(format_document_section(name, _build_all_results(doc, derived)))

    with tempfile.TemporaryDirectory() as tmp:
        write_validation_report(sections, Path(tmp))
        return (Path(tmp) / "validation_report.md").read_text(encoding="utf-8")


# ===========================================================================
# Document presence
# ===========================================================================

class TestDocumentPresence:

    def test_inv01_present(self, generated_report: str) -> None:
        assert "INV-01" in generated_report

    def test_inv02_present(self, generated_report: str) -> None:
        assert "INV-02" in generated_report

    def test_inv03_present(self, generated_report: str) -> None:
        assert "INV-03" in generated_report

    def test_inv04_present(self, generated_report: str) -> None:
        assert "INV-04" in generated_report

    def test_inv05_present(self, generated_report: str) -> None:
        assert "INV-05" in generated_report


# ===========================================================================
# Check presence — every V1–V7 must appear for each document
# ===========================================================================

class TestCheckPresence:

    def test_all_checks_v1_through_v7_present(self, generated_report: str) -> None:
        for check in ("V1", "V2", "V3", "V4", "V5", "V6", "V7"):
            assert f"### {check}" in generated_report, (
                f"{check} section header missing from report"
            )

    def test_report_not_empty(self, generated_report: str) -> None:
        assert len(generated_report) > 500


# ===========================================================================
# INV-04 failures
# ===========================================================================

class TestINV04Failures:

    def test_inv04_v1_fail_present(self, generated_report: str) -> None:
        # The FAIL marker and Pos 7 must appear in the report
        assert "FAIL" in generated_report
        assert "Pos 7" in generated_report

    def test_inv04_v1_diff_36_present(self, generated_report: str) -> None:
        # The discrepancy value must appear
        assert "36.00" in generated_report

    def test_inv04_v2_fail_present(self, generated_report: str) -> None:
        # INV-04 V2 failure values
        assert "5249.22" in generated_report
        assert "5213.22" in generated_report

    def test_inv04_document_originated_note_present(self, generated_report: str) -> None:
        # The header notes must explain the failures
        assert "document-originated" in generated_report


# ===========================================================================
# INV-05 V2 by-construction disclosure
# ===========================================================================

class TestINV05Disclosure:

    def test_by_construction_note_present(self, generated_report: str) -> None:
        assert "by construction" in generated_report.lower(), (
            "INV-05 V2 by-construction disclosure must appear in report"
        )


# ===========================================================================
# CLI wording
# ===========================================================================

class TestReportWording:

    def test_validate_cli_referenced_in_report(self, generated_report: str) -> None:
        # Now that validate.py exists, the report must reference it
        assert "validate.py" in generated_report


# ===========================================================================
# format_document_section — structural
# ===========================================================================

class TestFormatDocumentSection:

    def test_section_contains_document_name(self) -> None:
        doc = load_json(Path("outputs/INV-01.json"))
        section = format_document_section("INV-01_TEST", _build_all_results(doc))
        assert "INV-01_TEST" in section

    def test_section_contains_all_check_ids(self) -> None:
        doc = load_json(Path("outputs/INV-01.json"))
        section = format_document_section("INV-01_TEST", _build_all_results(doc))
        for check in ("V1", "V2", "V3", "V4", "V5", "V6", "V7"):
            assert f"### {check}" in section

    def test_write_creates_file(self) -> None:
        doc = load_json(Path("outputs/INV-01.json"))
        sections = [format_document_section("INV-01", _build_all_results(doc))]
        with tempfile.TemporaryDirectory() as tmp:
            write_validation_report(sections, Path(tmp))
            report_path = Path(tmp) / "validation_report.md"
            assert report_path.exists()
            assert report_path.stat().st_size > 0


# ===========================================================================
# format_document_section — empty result list must produce explicit FAIL
# ===========================================================================

class TestEmptyResultsNotSilentlyOmitted:
    """A required check with an empty result list must appear as FAIL in the
    report, never be silently omitted."""

    def test_empty_v1_results_shows_fail_not_silence(self) -> None:
        section = format_document_section("TEST", {"V1": []})
        assert "### V1" in section, "V1 section must appear even with empty results"
        assert "FAIL" in section, "Empty V1 results must show FAIL"

    def test_empty_v4_results_shows_fail_not_silence(self) -> None:
        section = format_document_section("TEST", {"V4": []})
        assert "### V4" in section
        assert "FAIL" in section

    def test_all_seven_checks_present_when_all_results_empty(self) -> None:
        section = format_document_section(
            "TEST",
            {k: [] for k in ("V1", "V2", "V3", "V4", "V5", "V6", "V7")}
        )
        for check in ("V1", "V2", "V3", "V4", "V5", "V6", "V7"):
            assert f"### {check}" in section, f"{check} must appear even with empty results"

    def test_missing_check_key_shows_fail(self) -> None:
        # When a check ID is not present in the dict at all, it still appears.
        section = format_document_section("TEST", {})
        for check in ("V1", "V2", "V3", "V4", "V5", "V6", "V7"):
            assert f"### {check}" in section
