"""Simple API client to fetch restaurants from NeoTaste JSON API with pagination.

This module intentionally keeps dependencies minimal to avoid import cycles
with the main scraper module.
"""
from typing import Any, Dict, List
import requests
import time
import random

SITE_BASE_URL = "https://neotaste.com"
API_BASE = "https://api.neotaste.com"


def fetch_restaurants_from_api(city_slug: str, lang: str = "de", verbosity: int = 0) -> List[Dict[str, Any]]:
    """Fetch restaurants for a city using the NeoTaste JSON API with pagination.

    The function will iterate pages until the API signals the last page
    or until a reasonable safety limit is reached. It returns structured
    restaurant dicts only when the restaurant has at least one available deal.
    """
    page = 1
    found: Dict[str, Dict[str, Any]] = {}
    max_pages = 200

    headers = {
        "User-Agent": "neotaste_scraper/1.0 (+https://github.com/rugk/neotaste_scraper)"
    }
    retry_limit = 3
    base_backoff = 1.0

    while page <= max_pages:
        url = f"{API_BASE}/cities/{city_slug}/restaurants?citySlug={city_slug}&includeLoyalty=true&page={page}"
        if verbosity:
            print(f"[api_client] requesting page {page}: {url}")

        # Per-page retries for rate-limited responses (403)
        attempts = 0
        resp = None
        while attempts < retry_limit:
            try:
                resp = requests.get(url, timeout=10, headers=headers)
            except Exception:
                resp = None
            # If no response object, break retries
            if resp is None:
                attempts += 1
                time.sleep(base_backoff * (2 ** attempts))
                continue

            status_attr = getattr(resp, 'status_code', None)
            try:
                status = int(status_attr) if status_attr is not None else 200
            except Exception:
                status = 200

            if status == 403:
                # Respect Retry-After header when present
                ra = resp.headers.get('Retry-After') if hasattr(resp, 'headers') else None
                if ra:
                    try:
                        wait = int(ra)
                    except Exception:
                        # Non-numeric Retry-After; fallback to exponential backoff
                        wait = int(base_backoff * (2 ** attempts))
                else:
                    # exponential backoff with jitter
                    wait = base_backoff * (2 ** attempts) + random.random() * 0.5
                if verbosity:
                    print(f"[api_client] 403 received, backing off {wait:.1f}s (attempt {attempts+1})")
                time.sleep(wait)
                attempts += 1
                continue

            # For other status codes, break and handle below
            break

        # If we exhausted retries without a valid response, stop paging
        if resp is None:
            break

        # Recompute status
        status_attr = getattr(resp, 'status_code', None)
        try:
            status = int(status_attr) if status_attr is not None else 200
        except Exception:
            status = 200

        if status != 200:
            break

        try:
            data = resp.json()
        except Exception:
            break

        # If the JSON doesn't parse to a dict (e.g. test mocks), stop
        if not isinstance(data, dict):
            break

        items = data.get("data") or []
        meta = data.get("meta") or {}

        for obj in items:
            if not isinstance(obj, dict):
                continue
            if obj.get("citySlug") != city_slug:
                continue
            slug = obj.get("slug")
            name = obj.get("name")
            if not slug or not name:
                continue

            # Extract available deals
            deals = []
            for d in obj.get("deals", []) or []:
                if isinstance(d, dict) and d.get("status") == "available":
                    dn = d.get("name") or ""
                    dn = dn.strip()
                    if dn:
                        deals.append(dn)

            if deals:
                found[slug] = {
                    "restaurant": name,
                    "deals": deals,
                    "link": f"{SITE_BASE_URL}/{lang}/restaurants/{slug}"
                }

        # Determine if we should continue paging
        is_last = None

        if is_last:
            break

        if not items:
            break

        page += 1

    return list(found.values())
