"""Simple API client to fetch restaurants from NeoTaste JSON API with pagination.

This module intentionally keeps dependencies minimal to avoid import cycles
with the main scraper module.
"""
from json import JSONDecodeError
import sys
import time
import random
from typing import Any, Dict, List
import requests

from neotaste_scraper.constants import BASE_URL, Deal

API_BASE = "https://api.neotaste.com"

# Rotating list of real browser User-Agents to avoid 403 blocks
# (App User-Agents were tested but consistently return 403)
USER_AGENTS = [
    # Chrome (latest versions)
    # pylint: disable=line-too-long
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1.2 Safari/605.1.15",
    # Mobile browsers
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Mobile Safari/537.36",
]


# pragma pylint: disable=too-many-nested-blocks, too-many-branches, too-many-locals, too-many-statements
def fetch_restaurants_from_api(city_slug: str, lang: str = "de", verbosity: int = 0) -> List[Dict[str, Any]]:
    """Fetch restaurants for a city using the NeoTaste JSON API with pagination.

    The function will iterate pages until the API signals the last page
    or until a reasonable safety limit is reached. It returns structured
    restaurant dicts only when the restaurant has at least one available deal.
    """
    page = 1
    found: Dict[str, Dict[str, Any]] = {}
    max_pages = 200

    def _get_random_user_agent() -> str:
        """Return a random browser or app User-Agent."""
        return random.choice(USER_AGENTS)

    def _build_api_headers() -> Dict[str, str]:
        """Return browser-like headers for the NeoTaste API request."""
        return {
            "User-Agent": _get_random_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://neotaste.com/",
            "Origin": "https://neotaste.com",
            "Cache-Control": "no-cache"
        }

    retry_limit = 3
    base_backoff = 1.0

    while page <= max_pages:
        normalized_city_slug = city_slug.strip()
        api_city_slug = normalized_city_slug.lower()
        url = f"{API_BASE}/web/restaurants/cities/{api_city_slug}/restaurants"
        params = {
            # "page": page,
            # "citySlug": normalized_city_slug,
            "includeLoyalty": "true"
        }

        if verbosity:
            print(f"[api_client] requesting page {page}: {url} params={params}", file=sys.stderr)

        # Per-page retries for rate-limited responses (403)
        attempts = 0
        resp = None
        while attempts < retry_limit:
            try:
                headers = _build_api_headers()
                resp = requests.get(url, timeout=10, headers=headers, params=params)
            except requests.RequestException as e:
                print(f"[api_client] request error: {e}", file=sys.stderr)
                resp = None

            # If no response object, retry
            if resp is None:
                attempts += 1
                time.sleep(base_backoff * (2 ** attempts))
                continue

            status_attr = getattr(resp, 'status_code', None)
            try:
                status = int(status_attr) if status_attr is not None else 200
            except TypeError:
                status = 200

            if status == 403:
                print("[api_client] page response status:", status,
                      ", failed with user agent: ", headers["User-Agent"], file=sys.stderr)

                # Respect Retry-After header when present
                ra = resp.headers.get(
                    'Retry-After') if hasattr(resp, 'headers') else None
                if ra:
                    try:
                        wait = int(ra)
                    except TypeError:
                        # Non-numeric Retry-After; fallback to exponential backoff
                        wait = int(base_backoff * (2 ** attempts))
                else:
                    # exponential backoff with jitter
                    wait = base_backoff * \
                        (2 ** attempts) + random.random() * 0.5
                if verbosity:
                    print(f"[api_client] 403 received, backing off {wait:.1f}s" +
                          f"(attempt {attempts+1})")
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
        status = int(status_attr) if status_attr is not None else 200

        body_snippet = getattr(resp, 'text', '')[:200].replace("\n", " ")
        
        if status != 200:
            if verbosity:
                print(
                    f"[api_client] non-200 response for page {page}: {status} (url: {resp.url})",
                    file=sys.stderr
                )
                print(
                    f"[api_client] response body snippet: {body_snippet!r}",
                    file=sys.stderr
                )
            break

        if verbosity:
            print("[api_client] page response status:", status,
                  ", worked with user agent: ", headers["User-Agent"], file=sys.stderr)

            print(
                f"[api_client] response body snippet: {body_snippet!r}",
                file=sys.stderr
            )

        try:
            data = resp.json()
        except JSONDecodeError:
            break

        # If the JSON doesn't parse to a dict (e.g. test mocks), stop
        if not isinstance(data, dict):
            break

        items = data.get("data") or []
        meta = data.get("meta") or {}

        if verbosity:
            print(f"[api_client] page {page}: items={len(items)} meta={meta}", file=sys.stderr)

        for obj in items:
            if not isinstance(obj, dict):
                continue
            if obj.get("citySlug", "").lower() != api_city_slug:
                continue
            slug = obj.get("slug")
            name = obj.get("name")
            if not slug or not name:
                continue

            # Extract available deals
            deals = []
            for d in obj.get("deals", []) or []:
                if isinstance(d, dict) and d.get("status") == "available":
                    deal_name = d.get("name") or ""
                    deal_name = deal_name.strip()
                    if deal_name:
                        deals.append(Deal(
                            text=deal_name,
                            component="api",
                            deal_type="flash+event" if d.get("eventDeal", False) else None
                        ))

            if deals:
                found[slug] = {
                    "restaurant": name,
                    "deals": deals,
                    "link": f"{BASE_URL}/{lang}/restaurants/{slug}"
                }

        # Determine if we should continue paging
        if isinstance(meta, dict) and meta.get("isLastPage"):
            break

        if not items:
            break

        page += 1

    return list(found.values())
#pragma pylint: enable=too-many-nested-blocks, too-many-branches, too-many-locals, too-many-statements
