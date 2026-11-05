"""
tests/test_cli.py

Tests for extract.py and validate.py CLI entry points.

Uses temporary directories for all write operations.  Does not overwrite
the canonical outputs/ directory during testing.

How to run:
    source .venv/bin/activate
    pytest tests/test_cli.py -v
"""

import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from helpers.schema_io import load_json, load_schema, validate_output

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PDF_INV01 = Path("input/INV-01_RE-2026-10418.pdf")
PDF_INV02 = Path("input/INV-02_RE-2026-10431.pdf")
PDF_INV03 = Path("input/INV-03_GS-2026-00872.pdf")
PDF_INV04 = Path("input/INV-04_RE-2026-10457.pdf")
PDF_INV05 = Path("input/INV-05_2026-R-00117.pdf")
REF_INV01 = Path("reference/INV-01_expected_output.json")
SCHEMA    = Path("input/output_schema.json")
PYTHON    = sys.executable  # the venv Python running this test process


def _run_extract(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, "extract.py"] + args,
        capture_output=True, text=True,
    )


def _run_validate(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, "validate.py"] + args,
        capture_output=True, text=True,
    )


# ===========================================================================
# extract.py — argument handling
# ===========================================================================

class TestExtractArguments:

    def test_no_args_exits_1(self) -> None:
        r = _run_extract([])
        assert r.returncode == 1
        assert "Usage" in r.stderr

    def test_nonexistent_pdf_exits_1(self) -> None:
        r = _run_extract(["nonexistent_file.pdf"])
        assert r.returncode == 1

    def test_unsupported_extension_exits_nonzero(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not a pdf")
            tmp = f.name
        r = _run_extract([tmp])
        assert r.returncode != 0


# ===========================================================================
# extract.py — layout detection and extraction
# ===========================================================================

class TestExtractLegacyLayout:

    def test_inv01_detected_as_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [PYTHON, "-c",
                 f"from extract import detect_layout; from pathlib import Path; "
                 f"print(detect_layout(Path('{PDF_INV01}')))"],
                capture_output=True, text=True,
            )
            assert "legacy" in r.stdout

    def test_inv01_extraction_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [PYTHON, "-c",
                 f"import sys; sys.argv=['x','{PDF_INV01}']; "
                 f"from extract import extract_invoice; from pathlib import Path; "
                 f"out,layout = extract_invoice(Path('{PDF_INV01}'),Path('{tmp}')); "
                 f"print(out.name, layout)"],
                capture_output=True, text=True,
            )
            assert "INV-01_RE-2026-10418.json" in r.stdout
            assert "legacy" in r.stdout

    def test_inv01_output_filename_convention(self) -> None:
        # Output stem must equal the PDF stem
        with tempfile.TemporaryDirectory() as tmp:
            from extract import extract_invoice
            out, _ = extract_invoice(PDF_INV01, Path(tmp))
            assert out.stem == PDF_INV01.stem
            assert out.suffix == ".json"

    def test_inv01_output_passes_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from extract import extract_invoice
            out, _ = extract_invoice(PDF_INV01, Path(tmp))
            schema = load_schema(SCHEMA)
            d = load_json(out)
            validate_output(d, schema)  # must not raise

    def test_inv01_matches_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from extract import extract_invoice
            out, _ = extract_invoice(PDF_INV01, Path(tmp))
            extracted = load_json(out)
            reference = load_json(REF_INV01)
            assert extracted == reference

    def test_inv04_pos7_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from extract import extract_invoice
            out, _ = extract_invoice(PDF_INV04, Path(tmp))
            d = load_json(out)
            pos7 = next(i for i in d["line_items"] if i["position"] == 7)
            assert pos7["line_total"] == Decimal("1284.52")


class TestExtractModernLayout:

    def test_inv05_detected_as_modern(self) -> None:
        r = subprocess.run(
            [PYTHON, "-c",
             f"from extract import detect_layout; from pathlib import Path; "
             f"print(detect_layout(Path('{PDF_INV05}')))"],
            capture_output=True, text=True,
        )
        assert "modern" in r.stdout

    def test_inv05_extraction_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from extract import extract_invoice
            out, layout = extract_invoice(PDF_INV05, Path(tmp))
            assert out.stem == PDF_INV05.stem
            assert layout == "modern"
            schema = load_schema(SCHEMA)
            d = load_json(out)
            validate_output(d, schema)


# ===========================================================================
# validate.py — argument handling
# ===========================================================================

class TestValidateArguments:

    def test_no_args_exits_1(self) -> None:
        r = _run_validate([])
        assert r.returncode == 1
        assert "Usage" in r.stderr

    def test_nonexistent_dir_exits_2(self) -> None:
        r = _run_validate(["nonexistent_directory_xyz/"])
        assert r.returncode == 2

    def test_empty_dir_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = _run_validate([tmp])
            assert r.returncode == 2


# ===========================================================================
# validate.py — successful processing
# ===========================================================================

class TestValidateProcessing:

    @pytest.fixture(scope="class")
    @classmethod
    def tmp_outputs(cls, tmp_path_factory):
        """Create a temp outputs dir containing full-name JSON for all five invoices."""
        tmp = tmp_path_factory.mktemp("outputs")
        from extract import extract_invoice
        for pdf in (PDF_INV01, PDF_INV02, PDF_INV03, PDF_INV04, PDF_INV05):
            extract_invoice(pdf, tmp)
        return tmp

    def test_processes_five_documents(self, tmp_outputs: Path) -> None:
        r = _run_validate([str(tmp_outputs)])
        assert r.returncode == 0
        assert "Documents processed : 5" in r.stdout

    def test_report_written(self, tmp_outputs: Path) -> None:
        _run_validate([str(tmp_outputs)])
        assert (tmp_outputs / "validation_report.md").exists()

    def test_inv04_v1_v2_fail_appear_in_report(self, tmp_outputs: Path) -> None:
        _run_validate([str(tmp_outputs)])
        text = (tmp_outputs / "validation_report.md").read_text()
        assert "36.00" in text, "INV-04 +36.00 discrepancy must appear"
        assert "1284.52" in text
        assert "1248.52" in text

    def test_inv05_v2_by_construction_disclosed(self, tmp_outputs: Path) -> None:
        _run_validate([str(tmp_outputs)])
        text = (tmp_outputs / "validation_report.md").read_text()
        assert "construction" in text.lower()

    def test_all_checks_v1_to_v7_present_for_each_doc(self, tmp_outputs: Path) -> None:
        _run_validate([str(tmp_outputs)])
        text = (tmp_outputs / "validation_report.md").read_text()
        for check in ("V1", "V2", "V3", "V4", "V5", "V6", "V7"):
            count = text.count(f"### {check}")
            assert count >= 5, f"{check} appears only {count} times (need ≥5)"

    def test_validate_cli_wording_in_report(self, tmp_outputs: Path) -> None:
        _run_validate([str(tmp_outputs)])
        text = (tmp_outputs / "validation_report.md").read_text()
        assert "validate.py" in text

    def test_malformed_json_skipped_gracefully(self, tmp_outputs: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "BAD_INVOICE_MALFORMED.json"
            bad.write_text("not json {{{", encoding="utf-8")
            r = _run_validate([tmp])
            # Should not crash with returncode 0 (no valid files) or 2;
            # malformed files are skipped — empty dir returns 2
            assert r.returncode in (0, 2)
