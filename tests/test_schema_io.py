"""
tests/test_schema_io.py

Unit tests for helpers.schema_io.

Uses the actual output schema and reference JSON files from the project.
Write tests use temporary directories — the reference files are never overwritten.

How to run:
    source .venv/bin/activate
    pytest tests/test_schema_io.py -v
"""

import json
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import jsonschema

from helpers.schema_io import load_json, load_schema, validate_output, write_json

# ---------------------------------------------------------------------------
# Real project file paths
# ---------------------------------------------------------------------------
SCHEMA_PATH   = Path("input/output_schema.json")
REFERENCE_JSON = Path("reference/INV-01_expected_output.json")


# ===========================================================================
# load_schema
# ===========================================================================

class TestLoadSchema:
    """Verify schema loading and structural validation."""

    def test_load_actual_schema_succeeds(self) -> None:
        # The project's output schema must load without errors.
        schema = load_schema(SCHEMA_PATH)
        assert isinstance(schema, dict)
        assert "$schema" in schema

    def test_invalid_schema_raises_schema_error(self) -> None:
        # A JSON file that is structurally not a valid JSON Schema raises
        # jsonschema.SchemaError (not just ValueError).
        with tempfile.TemporaryDirectory() as tmp:
            bad_schema_path = Path(tmp) / "bad_schema.json"
            # "type" must be a string or array, not a plain object —
            # this is a structural schema error.
            bad_schema_path.write_text(
                '{"$schema": "https://json-schema.org/draft/2020-12/schema", '
                '"type": {"invalid": true}}',
                encoding="utf-8",
            )
            with pytest.raises(jsonschema.SchemaError):
                load_schema(bad_schema_path)

    def test_missing_schema_file_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_schema(Path("input/does_not_exist.json"))

    def test_invalid_json_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_json_path = Path(tmp) / "bad.json"
            bad_json_path.write_text("not json at all", encoding="utf-8")
            with pytest.raises(ValueError):
                load_schema(bad_json_path)


# ===========================================================================
# load_json
# ===========================================================================

class TestLoadJson:
    """Verify JSON loading with Decimal precision preservation."""

    def test_load_reference_json_succeeds(self) -> None:
        # The INV-01 reference JSON must load and contain the correct doc number.
        data = load_json(REFERENCE_JSON)
        assert data["document_number"] == "RE-2026-10418"

    def test_decimal_values_loaded_as_decimal_not_float(self) -> None:
        # gross_total is a decimal number in the JSON.
        # With parse_float=Decimal it must be a Decimal, not a float.
        data = load_json(REFERENCE_JSON)
        gross = data["totals"]["gross_total"]
        assert isinstance(gross, Decimal), (
            f"Expected Decimal, got {type(gross).__name__}: {gross!r}"
        )

    def test_integer_values_remain_int(self) -> None:
        # vat_rate is a JSON integer (19).  It must stay an int.
        data = load_json(REFERENCE_JSON)
        vat_rate = data["line_items"][0]["vat_rate"]
        assert isinstance(vat_rate, int), (
            f"Expected int, got {type(vat_rate).__name__}: {vat_rate!r}"
        )

    def test_missing_file_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_json(Path("input/nonexistent.json"))

    def test_invalid_json_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not valid json", encoding="utf-8")
            with pytest.raises(ValueError):
                load_json(bad)


# ===========================================================================
# validate_output
# ===========================================================================

class TestValidateOutput:
    """Verify schema validation against the actual output schema."""

    def test_reference_json_passes_validation(self) -> None:
        # The reference INV-01 output must validate without error.
        schema = load_schema(SCHEMA_PATH)
        data = load_json(REFERENCE_JSON)
        # load_json returns Decimal; validate_output receives Decimal values.
        # We need plain Python numbers for jsonschema — convert via json roundtrip.
        data_plain = json.loads(json.dumps(data, default=float))
        validate_output(data_plain, schema)   # must not raise

    def test_missing_required_field_raises_validation_error(self) -> None:
        # Removing a required field (currency) must cause ValidationError.
        schema = load_schema(SCHEMA_PATH)
        data = load_json(REFERENCE_JSON)
        data_plain = json.loads(json.dumps(data, default=float))
        del data_plain["currency"]
        with pytest.raises(jsonschema.ValidationError):
            validate_output(data_plain, schema)


# ===========================================================================
# write_json
# ===========================================================================

class TestWriteJson:
    """Verify JSON writing with correct Decimal handling."""

    def _sample_data(self) -> dict:
        """A minimal dict containing the three Decimal values under test."""
        return {
            "net_total": Decimal("801.47"),
            "unit_price": Decimal("0.152"),
            "credit_amount": Decimal("-225.80"),
        }

    def test_write_succeeds_with_decimal_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "test_output.json"
            write_json(self._sample_data(), out)
            assert out.exists()

    def test_decimal_801_47_round_trips_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            write_json(self._sample_data(), out)
            reloaded = load_json(out)
            assert reloaded["net_total"] == Decimal("801.47")

    def test_three_decimal_precision_preserved(self) -> None:
        # Decimal("0.152") must not be rounded to 0.15 during the round-trip.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            write_json(self._sample_data(), out)
            reloaded = load_json(out)
            assert reloaded["unit_price"] == Decimal("0.152")

    def test_negative_decimal_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            write_json(self._sample_data(), out)
            reloaded = load_json(out)
            assert reloaded["credit_amount"] == Decimal("-225.80")

    def test_decimal_written_as_number_not_string(self) -> None:
        # Financial values must be JSON numbers (e.g. 801.47),
        # not quoted strings (e.g. "801.47").
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            write_json(self._sample_data(), out)
            raw_text = out.read_text(encoding="utf-8")
            parsed = json.loads(raw_text)
            # A JSON number parses as float (not str) when loaded without
            # parse_float override — confirms it was not written as a string.
            assert isinstance(parsed["net_total"], float), (
                "net_total should be a JSON number, not a string"
            )

    def test_output_directory_created_automatically(self) -> None:
        # write_json must create the output directory tree if absent.
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "a" / "b" / "c" / "out.json"
            assert not nested.parent.exists()
            write_json({"key": Decimal("1.00")}, nested)
            assert nested.exists()
