#!/usr/bin/env python3
"""Minimal JSON verifier for CI.

Usage: python scripts/verify_json.py path/to/index.json

Exits with 0 if any city array in the JSON has length > 0, otherwise exits 1.
When empty, the script emits a GitHub Actions warning line so the workflow log
shows a clear message (useful if you handle the script's exit in the shell).
"""

import json
import sys
from pathlib import Path


def main() -> int:
    """
    Reads JSON and verifies it is not empty.
    """
    if len(sys.argv) != 2:
        print("Usage: python scripts/verify_json.py path/to/index.json", file=sys.stderr)
        return 2

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"::error::JSON file not found: {file_path}")
        return 404

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e: # pylint: disable=broad-exception-caught
        print(f"::error::Failed to parse JSON {file_path}: {e}")
        return 500

    if not isinstance(data, dict):
        print(f"::warning::Top-level JSON is not an object in {file_path}")
        return 400

    for city, entries in data.items():
        if isinstance(entries, list) and len(entries) > 0:
            print(f"OK: found non-empty city '{city}' in {file_path}")
            return 0

    # no non-empty lists
    # Emit a warning recognizable by GitHub Actions; callers can choose to ignore
    # the non-zero exit via shell (e.g. `python scripts/verify_json.py file || true`).
    print(f"::warning::All city lists are empty in {file_path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
