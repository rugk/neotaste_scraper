#!/usr/bin/env python3
"""Quick import and enum test."""

try:
    from neotaste_scraper.neotaste_scraper import Verbosity, fetch_deals_from_city
    print(f"✓ Imports successful")
    print(f"✓ Verbosity enum: {Verbosity.SILENT}, {Verbosity.NORMAL}, {Verbosity.DEBUG}")
    print(f"✓ Verbosity.NORMAL.value = {Verbosity.NORMAL.value}")
    
    # Test the mapping logic
    test_counts = [0, 1, 2, 3]
    for count in test_counts:
        v = [Verbosity.SILENT, Verbosity.NORMAL, Verbosity.DEBUG][min(count, 2)]
        print(f"  args.verbose={count} → {v}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
