"""
helpers/schema_io.py

JSON loading, schema validation, and JSON writing for the invoice extractor.

Four functions are provided:
  load_schema       — load and verify the JSON Schema file.
  validate_output   — validate an extracted invoice dict against the schema.
  write_json        — write a dict (possibly containing Decimal values) to JSON.
  load_json         — load a JSON file, returning Decimal for decimal numbers.

Design principle — the Decimal/float boundary:
  Financial values are Decimal throughout the application.
  The ONLY place Decimal is converted to float is inside DecimalEncoder.default(),
  immediately before json.dump() writes the value to disk.
  load_json() uses parse_float=Decimal so reloaded values are also Decimal,
  allowing Phase 7 validation checks to use Decimal arithmetic on loaded files.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator, FormatChecker


# ---------------------------------------------------------------------------
# Custom JSON encoder.
# json.dump() calls encoder.default(obj) when it encounters a type it cannot
# serialise natively.  We intercept Decimal and convert to float at this
# boundary only.  All other types fall through to the built-in encoder.
# ---------------------------------------------------------------------------
class _DecimalEncoder(json.JSONEncoder):
    """Encode Decimal values as JSON numbers (float) at serialisation time."""

    def default(self, obj: object) -> object:
        if isinstance(obj, Decimal):
            # float() here is intentional and deliberate — this is the single
            # authorised conversion point in the entire project.
            return float(obj)
        return super().default(obj)  # raise TypeError for unknown types


def load_schema(path: Path) -> dict:
    """Load the JSON Schema from disk and verify its internal structure.

    Calls Draft202012Validator.check_schema() to catch any accidental edits
    to the schema file before it is used for validation.

    Args:
        path: Path to the JSON Schema file (e.g. input/output_schema.json).

    Returns:
        A Python dict representing the JSON Schema.

    Raises:
        FileNotFoundError:        The schema file does not exist.
        ValueError:               The file exists but is not valid JSON.
        jsonschema.SchemaError:   The file is valid JSON but is not a valid
                                  JSON Schema.
    """
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Schema file is not valid JSON: {path}. Error: {exc}"
        ) from exc

    # Validates that the schema itself is well-formed.
    # Raises jsonschema.SchemaError if the schema has structural problems.
    Draft202012Validator.check_schema(schema)
    return schema


def validate_output(data: dict, schema: dict) -> None:
    """Validate an extracted invoice dict against the output schema.

    Uses Draft202012Validator with a FormatChecker so that date-format
    constraints in the schema (format: "date") are actually enforced.

    Args:
        data:   The extracted invoice as a Python dict.
        schema: The JSON Schema dict, typically from load_schema().

    Returns:
        None on success.

    Raises:
        jsonschema.ValidationError: The data does not conform to the schema.
                                    The exception message names the failing
                                    field and the reason.
    """
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    # validate() raises ValidationError on failure; returns None on success.
    validator.validate(data)


def write_json(data: dict, output_path: Path) -> None:
    """Write a Python dict to a JSON file, converting Decimal values to float.

    Creates the output directory (and any parent directories) if it does not
    already exist.  Writes with indentation=2 for human-readable output.

    Decimal → float conversion happens ONLY inside _DecimalEncoder.default().
    No other part of the project should call float() on financial values.

    Args:
        data:        The dict to serialise.  May contain Decimal values.
        output_path: Destination file path.

    Returns:
        None.  Side effect: writes or overwrites the file at output_path.

    Raises:
        OSError: Permission error or disk full.
    """
    # Create the parent directory tree if it does not exist.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, cls=_DecimalEncoder),
        encoding="utf-8",
    )


def load_json(path: Path) -> dict:
    """Load a JSON file and return its contents as a Python dict.

    Uses parse_float=Decimal so that JSON decimal numbers (e.g. 801.47)
    are returned as Decimal objects rather than float.  This allows Phase 7
    validation checks to use Decimal arithmetic on loaded output files without
    re-introducing floating-point imprecision.

    JSON integers are returned as Python int (unaffected by parse_float).

    Args:
        path: Path to the JSON file.

    Returns:
        A Python dict.  Decimal-valued numbers are Decimal instances.

    Raises:
        FileNotFoundError: The file does not exist.
        ValueError:        The file exists but is not valid JSON.
    """
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"File is not valid JSON: {path}. Error: {exc}"
        ) from exc
