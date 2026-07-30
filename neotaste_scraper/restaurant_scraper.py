"""Simple API client to fetch restaurants from NeoTaste JSON API with pagination."""

# pragma pylint: disable=too-many-nested-blocks, too-many-branches, too-many-locals, too-many-statements
import sys
from typing import Any, Dict, List

from neotaste_scraper.api_client import request_json
from neotaste_scraper.constants import API_BASE, BASE_URL, Deal


def fetch_restaurants_from_api(city_slug: str, lang: str = "de", verbosity: int = 0) -> List[Dict[str, Any]]:
    """Fetch restaurants for a city using the NeoTaste JSON API with pagination.

    The function will iterate pages until the API signals the last page
    or until a reasonable safety limit is reached. It returns structured
    restaurant dicts only when the restaurant has at least one available deal.
    """
    page = 1
    found: Dict[str, Dict[str, Any]] = {}
    max_pages = 200

    while page <= max_pages:
        normalized_city_slug = city_slug.strip()
        api_city_slug = normalized_city_slug.lower()
        url = f"{API_BASE}/web/restaurants/cities/{api_city_slug}/restaurants"
        params = {
            "page": page,
            "citySlug": normalized_city_slug,
            "includeLoyalty": "true"
        }

        if verbosity:
            print(f"[api_client] requesting page {page}: {url} params={params}", file=sys.stderr)

        payload = request_json(url, params=params, timeout=10, verbosity=verbosity)
        if payload is None:
            break

        if not isinstance(payload, dict):
            break

        items = payload.get("data") or []
        meta = payload.get("meta") or {}

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
                    "link": f"{BASE_URL}/{lang}/restaurants/{api_city_slug}/{slug}"
                }

        # Determine if we should continue paging
        if isinstance(meta, dict) and meta.get("isLastPage"):
            break

        if not items:
            break

        page += 1

    return list(found.values())

# pragma pylint: enable=too-many-nested-blocks, too-many-branches, too-many-locals, too-many-statements
