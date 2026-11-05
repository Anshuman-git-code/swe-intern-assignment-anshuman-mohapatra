#!/usr/bin/env python3
"""
validate.py — Kessler invoice validation report generator.

Usage:
    python validate.py <output-directory>

Example:
    python validate.py outputs/

Reads every *.json file in the directory (excluding validation_report.md),
runs checks V1–V7 on each document, and writes validation_report.md.

Exit codes:
    0  report written (document-originated FAILs are expected, not CLI errors)
    1  usage error
    2  directory/file I/O error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from helpers.schema_io import load_json, load_schema, validate_output
    from validation.checks import (
        check_v1, check_v2, check_v3, check_v4,
        check_v5, check_v6, check_v7,
    )
    from validation.report import format_document_section, write_validation_report
except ImportError as exc:
    print(f"Import error: {exc}", file=sys.stderr)
    print("Make sure you have activated the virtual environment:", file=sys.stderr)
    print("  source .venv/bin/activate", file=sys.stderr)
    sys.exit(1)

_SCHEMA_PATH   = Path("input/output_schema.json")

# ---------------------------------------------------------------------------
# The modern-layout document (INV-05) uses derived per-rate net values.
# Detect it by document number prefix.
# ---------------------------------------------------------------------------
_MODERN_DOC_NUMBER_PREFIX = "2026-R-"


def _is_inv05_derived(doc: dict) -> bool:
    """True when net_by_vat_rate was derived from line items (no printed per-rate net)."""
    doc_no = doc.get("document_number", "")
    return _MODERN_DOC_NUMBER_PREFIX in doc_no


def run_all_checks(doc: dict) -> dict:
    """Run V1–V7 and return a dict of check_id → list[CheckResult]."""
    derived = _is_inv05_derived(doc)
    return {
        "V1": check_v1(doc),
        "V2": check_v2(doc, inv05_derived=derived),
        "V3": check_v3(doc),
        "V4": [check_v4(doc)],
        "V5": [check_v5(doc)],
        "V6": check_v6(doc),
        "V7": check_v7(doc),
    }


def validate_directory(output_dir: Path) -> int:
    """Process all invoice JSON files in output_dir and write validation_report.md.

    Returns:
        0 on success (document FAILs are not exit errors).
        2 on I/O or structural error.
    """
    if not output_dir.exists():
        print(f"Error: directory not found: {output_dir}", file=sys.stderr)
        return 2

    # Collect JSON files in stable alphabetical order; skip the report itself
    # and skip legacy short-name outputs (INV-01.json etc.) — only process
    # the full-filename outputs produced by extract.py.
    json_files = sorted(
        p for p in output_dir.glob("*.json")
        if p.name != "validation_report.json"
        and p.name not in (
            "INV-01.json", "INV-02.json", "INV-03.json",
            "INV-04.json", "INV-05.json",
        )
    )

    if not json_files:
        print(f"No JSON files found in {output_dir}", file=sys.stderr)
        return 2

    try:
        schema = load_schema(_SCHEMA_PATH)
    except Exception as exc:
        print(f"Could not load schema: {exc}", file=sys.stderr)
        return 2

    sections: list[str] = []
    doc_summary: list[str] = []

    for json_path in json_files:
        doc_name = json_path.stem
        print(f"Processing {json_path.name} ...", end=" ", flush=True)

        try:
            doc = load_json(json_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"SKIP (cannot load: {exc})")
            continue

        # Schema validation
        try:
            validate_output(doc, schema)
            schema_ok = True
        except Exception as exc:
            schema_ok = False
            print(f"schema FAIL ({exc})")

        # Run all seven checks
        all_results = run_all_checks(doc)
        sections.append(format_document_section(doc_name, all_results))

        # Terminal summary
        check_statuses = []
        for cid in ("V1", "V2", "V3", "V4", "V5", "V6", "V7"):
            results = all_results.get(cid, [])
            overall = all(r.passed for r in results) if results else False
            check_statuses.append(f"{cid}:{'✅' if overall else '❌'}")

        schema_marker = "✅" if schema_ok else "❌"
        line = f"schema{schema_marker} | " + " ".join(check_statuses)
        print(line)
        doc_summary.append(f"  {doc_name}: {line}")

    if not sections:
        print("No documents could be processed.", file=sys.stderr)
        return 2

    write_validation_report(sections, output_dir)
    report_path = output_dir / "validation_report.md"

    print()
    print(f"Documents processed : {len(sections)}")
    print(f"Report written      : {report_path}")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python validate.py <output-directory>\n"
            "Example: python validate.py outputs/",
            file=sys.stderr,
        )
        return 1

    output_dir = Path(sys.argv[1])
    return validate_directory(output_dir)


if __name__ == "__main__":
    sys.exit(main())
