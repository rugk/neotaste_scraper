#!/usr/bin/env python3
"""Minimal JSON verifier for CI with item count verification.

Usage: python scripts/verify_json.py path/to/index.json [min_count]

Exits with 0 if any city has at least one entry and count >= min_count.
min_count defaults to 15 if not provided.

Outputs item count to help track scraper health across CI runs.
"""

import json
import sys
from pathlib import Path


def main() -> int:
    """
    Reads JSON, verifies it is not empty, and validates item counts.
    """
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_json.py path/to/index.json [min_count]", file=sys.stderr)
        return 2

    file_path = Path(sys.argv[1])
    min_count = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    if not file_path.exists():
        print(f"::error::JSON file not found: {file_path}")
        return 404

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"::error::Failed to parse JSON {file_path}: {e}")
        return 500

    if not isinstance(data, dict):
        print(f"::warning::Top-level JSON is not an object in {file_path}")
        return 400

    total_items = 0
    max_city_count = 0
    max_city_name = None

    for city, entries in data.items():
        if isinstance(entries, list):
            city_count = len(entries)
            total_items += city_count

            if city_count > max_city_count:
                max_city_count = city_count
                max_city_name = city

            if city_count > 0:
                print(f"✓ City '{city}': {city_count} restaurants")

    print(f"\n📊 Total: {total_items} restaurants across {len(data)} cities")
    if max_city_name:
        print(f"📈 Max: City '{max_city_name}' with {max_city_count} restaurants")

    # Check if we have at least one non-empty city and if max city meets min_count
    if total_items == 0:
        print(f"::warning::All city lists are empty in {file_path}")
        return 1

    if max_city_count < min_count:
        print(f"::warning::Max city count ({max_city_count}) is below minimum ({min_count}) in {file_path}")
        return 1

    print(f"✅ Verification passed: {total_items} total items, max city has {max_city_count} (min: {min_count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

