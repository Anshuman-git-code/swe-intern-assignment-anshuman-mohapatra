"""
tests/test_regression.py

Phase 8 regression tests.

Runs parsers, schema validation and V1–V7 checks against all five supplied
PDFs to confirm no regressions were introduced by Phase 7 or 8 changes.

Uses actual output JSON files loaded via load_json() (Decimal values).
Uses actual source PDFs; does not overwrite them.

How to run:
    source .venv/bin/activate
    pytest tests/test_regression.py -v
"""

from decimal import Decimal
from pathlib import Path

import pytest

from helpers.schema_io import load_json, load_schema, validate_output
from parsers.layout_legacy import parse_legacy_invoice
from parsers.layout_modern import parse_modern_invoice
from validation.checks import (
    check_v1, check_v2, check_v3, check_v4,
    check_v5, check_v6, check_v7,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PDF_INV01 = Path("input/INV-01_RE-2026-10418.pdf")
PDF_INV02 = Path("input/INV-02_RE-2026-10431.pdf")
PDF_INV03 = Path("input/INV-03_GS-2026-00872.pdf")
PDF_INV04 = Path("input/INV-04_RE-2026-10457.pdf")
PDF_INV05 = Path("input/INV-05_2026-R-00117.pdf")

SCHEMA_PATH = Path("input/output_schema.json")
REF_INV01   = Path("reference/INV-01_expected_output.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def schema() -> dict:
    return load_schema(SCHEMA_PATH)

@pytest.fixture(scope="module")
def parsed_inv01() -> dict:
    return parse_legacy_invoice(PDF_INV01)

@pytest.fixture(scope="module")
def parsed_inv02() -> dict:
    return parse_legacy_invoice(PDF_INV02)

@pytest.fixture(scope="module")
def parsed_inv03() -> dict:
    return parse_legacy_invoice(PDF_INV03)

@pytest.fixture(scope="module")
def parsed_inv04() -> dict:
    return parse_legacy_invoice(PDF_INV04)

@pytest.fixture(scope="module")
def parsed_inv05() -> dict:
    return parse_modern_invoice(PDF_INV05)

@pytest.fixture(scope="module")
def json_inv01() -> dict:
    return load_json(Path("outputs/INV-01.json"))

@pytest.fixture(scope="module")
def json_inv02() -> dict:
    return load_json(Path("outputs/INV-02.json"))

@pytest.fixture(scope="module")
def json_inv03() -> dict:
    return load_json(Path("outputs/INV-03.json"))

@pytest.fixture(scope="module")
def json_inv04() -> dict:
    return load_json(Path("outputs/INV-04.json"))

@pytest.fixture(scope="module")
def json_inv05() -> dict:
    return load_json(Path("outputs/INV-05.json"))

@pytest.fixture(scope="module")
def reference_inv01() -> dict:
    return load_json(REF_INV01)


# ===========================================================================
# Parser regression — item counts
# ===========================================================================

class TestParserItemCounts:

    def test_inv01_has_6_items(self, parsed_inv01: dict) -> None:
        assert len(parsed_inv01["line_items"]) == 6

    def test_inv02_has_26_items(self, parsed_inv02: dict) -> None:
        assert len(parsed_inv02["line_items"]) == 26

    def test_inv03_has_3_items(self, parsed_inv03: dict) -> None:
        assert len(parsed_inv03["line_items"]) == 3

    def test_inv04_has_15_items(self, parsed_inv04: dict) -> None:
        assert len(parsed_inv04["line_items"]) == 15

    def test_inv05_has_5_items(self, parsed_inv05: dict) -> None:
        assert len(parsed_inv05["line_items"]) == 5


# ===========================================================================
# Parser regression — INV-01 exact reference match
# ===========================================================================

class TestINV01ReferenceMatch:

    def test_inv01_exact_match(
        self, parsed_inv01: dict, reference_inv01: dict
    ) -> None:
        assert parsed_inv01 == reference_inv01, (
            "INV-01 parsed output no longer matches reference JSON"
        )


# ===========================================================================
# Schema regression — all five outputs
# ===========================================================================

class TestSchemaRegression:

    def test_inv01_schema_valid(self, json_inv01: dict, schema: dict) -> None:
        validate_output(json_inv01, schema)

    def test_inv02_schema_valid(self, json_inv02: dict, schema: dict) -> None:
        validate_output(json_inv02, schema)

    def test_inv03_schema_valid(self, json_inv03: dict, schema: dict) -> None:
        validate_output(json_inv03, schema)

    def test_inv04_schema_valid(self, json_inv04: dict, schema: dict) -> None:
        validate_output(json_inv04, schema)

    def test_inv05_schema_valid(self, json_inv05: dict, schema: dict) -> None:
        validate_output(json_inv05, schema)


# ===========================================================================
# Validation regression — INV-01: all checks pass
# ===========================================================================

class TestValidationINV01:

    def test_v1_all_pass(self, json_inv01: dict) -> None:
        assert all(r.passed for r in check_v1(json_inv01))

    def test_v2_all_pass(self, json_inv01: dict) -> None:
        assert all(r.passed for r in check_v2(json_inv01))

    def test_v3_all_pass(self, json_inv01: dict) -> None:
        assert all(r.passed for r in check_v3(json_inv01))

    def test_v4_pass(self, json_inv01: dict) -> None:
        assert check_v4(json_inv01).passed

    def test_v5_pass(self, json_inv01: dict) -> None:
        assert check_v5(json_inv01).passed

    def test_v6_all_pass(self, json_inv01: dict) -> None:
        assert all(r.passed for r in check_v6(json_inv01))

    def test_v7_all_pass(self, json_inv01: dict) -> None:
        assert all(r.passed for r in check_v7(json_inv01))


# ===========================================================================
# Validation regression — INV-02: all checks pass
# ===========================================================================

class TestValidationINV02:

    def test_v1_all_pass(self, json_inv02: dict) -> None:
        assert all(r.passed for r in check_v1(json_inv02))

    def test_v2_all_pass(self, json_inv02: dict) -> None:
        assert all(r.passed for r in check_v2(json_inv02))

    def test_v3_all_pass(self, json_inv02: dict) -> None:
        assert all(r.passed for r in check_v3(json_inv02))

    def test_v4_pass(self, json_inv02: dict) -> None:
        assert check_v4(json_inv02).passed

    def test_v5_pass(self, json_inv02: dict) -> None:
        assert check_v5(json_inv02).passed

    def test_v6_all_pass(self, json_inv02: dict) -> None:
        assert all(r.passed for r in check_v6(json_inv02))

    def test_v7_all_pass(self, json_inv02: dict) -> None:
        assert all(r.passed for r in check_v7(json_inv02))


# ===========================================================================
# Validation regression — INV-03: all checks pass
# ===========================================================================

class TestValidationINV03:

    def test_v1_all_pass(self, json_inv03: dict) -> None:
        assert all(r.passed for r in check_v1(json_inv03))

    def test_v2_all_pass(self, json_inv03: dict) -> None:
        assert all(r.passed for r in check_v2(json_inv03))

    def test_v3_all_pass(self, json_inv03: dict) -> None:
        assert all(r.passed for r in check_v3(json_inv03))

    def test_v4_pass(self, json_inv03: dict) -> None:
        assert check_v4(json_inv03).passed

    def test_v5_pass(self, json_inv03: dict) -> None:
        assert check_v5(json_inv03).passed

    def test_v6_all_pass(self, json_inv03: dict) -> None:
        # INV-03 has no service_date, due_date, or cash_discount — only document_date
        assert all(r.passed for r in check_v6(json_inv03))

    def test_v7_all_pass(self, json_inv03: dict) -> None:
        assert all(r.passed for r in check_v7(json_inv03))


# ===========================================================================
# Validation regression — INV-04: V1 and V2 FAIL; V3–V7 PASS
# ===========================================================================

class TestValidationINV04:

    def test_v1_pos7_fails(self, json_inv04: dict) -> None:
        results = check_v1(json_inv04)
        pos7 = next(r for r in results if r.position == 7)
        assert not pos7.passed

    def test_v1_pos7_diff_is_36(self, json_inv04: dict) -> None:
        results = check_v1(json_inv04)
        pos7 = next(r for r in results if r.position == 7)
        assert pos7.difference == Decimal("36.00")

    def test_v1_pos7_expected_1248_52(self, json_inv04: dict) -> None:
        results = check_v1(json_inv04)
        pos7 = next(r for r in results if r.position == 7)
        assert pos7.expected == Decimal("1248.52")

    def test_v1_pos7_actual_1284_52_preserved(self, json_inv04: dict) -> None:
        results = check_v1(json_inv04)
        pos7 = next(r for r in results if r.position == 7)
        assert pos7.actual == Decimal("1284.52")

    def test_v1_all_other_pass(self, json_inv04: dict) -> None:
        results = check_v1(json_inv04)
        others = [r for r in results if r.position != 7]
        assert all(r.passed for r in others)

    def test_v2_19pct_fails_with_36_diff(self, json_inv04: dict) -> None:
        results = check_v2(json_inv04)
        r19 = next(r for r in results if r.rate == "19")
        assert not r19.passed
        assert r19.difference == Decimal("36.00")

    def test_v2_19pct_expected_is_line_sum(self, json_inv04: dict) -> None:
        results = check_v2(json_inv04)
        r19 = next(r for r in results if r.rate == "19")
        assert r19.expected == Decimal("5249.22")

    def test_v2_19pct_actual_is_printed_net(self, json_inv04: dict) -> None:
        results = check_v2(json_inv04)
        r19 = next(r for r in results if r.rate == "19")
        assert r19.actual == Decimal("5213.22")

    def test_v2_7pct_passes(self, json_inv04: dict) -> None:
        results = check_v2(json_inv04)
        r7 = next(r for r in results if r.rate == "7")
        assert r7.passed

    def test_v3_pass(self, json_inv04: dict) -> None:
        assert all(r.passed for r in check_v3(json_inv04))

    def test_v4_pass(self, json_inv04: dict) -> None:
        assert check_v4(json_inv04).passed

    def test_v5_pass(self, json_inv04: dict) -> None:
        assert check_v5(json_inv04).passed

    def test_v6_pass(self, json_inv04: dict) -> None:
        assert all(r.passed for r in check_v6(json_inv04))

    def test_v7_pass(self, json_inv04: dict) -> None:
        assert all(r.passed for r in check_v7(json_inv04))


# ===========================================================================
# Validation regression — INV-05: all pass; V2 by construction
# ===========================================================================

class TestValidationINV05:

    def test_v1_all_pass(self, json_inv05: dict) -> None:
        assert all(r.passed for r in check_v1(json_inv05))

    def test_v2_pass_by_construction(self, json_inv05: dict) -> None:
        results = check_v2(json_inv05, inv05_derived=True)
        assert all(r.passed for r in results)
        assert any("construction" in r.detail.lower() for r in results)

    def test_v3_pass(self, json_inv05: dict) -> None:
        assert all(r.passed for r in check_v3(json_inv05))

    def test_v4_pass(self, json_inv05: dict) -> None:
        assert check_v4(json_inv05).passed

    def test_v5_pass(self, json_inv05: dict) -> None:
        assert check_v5(json_inv05).passed

    def test_v6_pass(self, json_inv05: dict) -> None:
        assert all(r.passed for r in check_v6(json_inv05))

    def test_v7_pass(self, json_inv05: dict) -> None:
        assert all(r.passed for r in check_v7(json_inv05))
