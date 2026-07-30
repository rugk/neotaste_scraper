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

from neotaste_scraper.constants import BASE_URL, Deal, Verbosity

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


def _coerce_status_code(status_attr: Any) -> int:
    """Normalize a response status code, defaulting to 200 for mocked objects."""
    if status_attr is None:
        return 200
    if isinstance(status_attr, bool):
        return 200
    if isinstance(status_attr, int):
        return status_attr
    if isinstance(status_attr, str):
        try:
            return int(status_attr)
        except ValueError:
            return 200
    return 200


def _request_with_retries(url: str,
                          *,
                          params: Dict[str, Any] | None = None,
                          timeout: int = 10,
                          verbosity: int = 0,
                          headers: Dict[str, str] | None = None,
                          retry_limit: int = 3,
                          base_backoff: float = 1.0) -> requests.Response | None:
    """Perform an HTTP GET with retries and browser-like headers."""
    request_headers = headers or _build_api_headers()
    attempts = 0
    while attempts < retry_limit:
        try:
            request_kwargs = {"timeout": timeout}
            if headers is not None:
                request_kwargs["headers"] = request_headers
            elif params is not None:
                request_kwargs["headers"] = request_headers
            if params is not None:
                request_kwargs["params"] = params
            response = requests.get(url, **request_kwargs)
        except requests.RequestException as exc:
            print(f"[api_client] request error: {exc}", file=sys.stderr)
            if attempts >= retry_limit - 1:
                return None
            wait = base_backoff * (2 ** attempts) + random.random() * 0.5
            if verbosity:
                print(f"[api_client] retrying request in {wait:.1f}s", file=sys.stderr)
            time.sleep(wait)
            attempts += 1
            continue

        status_attr = getattr(response, 'status_code', None)
        status = _coerce_status_code(status_attr)

        if status == 403:
            print("[api_client] page response status:", status,
                  ", failed with user agent: ", request_headers["User-Agent"], file=sys.stderr)

            retry_after = response.headers.get('Retry-After') if hasattr(response, 'headers') else None
            if retry_after:
                try:
                    wait = int(retry_after)
                except TypeError:
                    wait = int(base_backoff * (2 ** attempts))
            else:
                wait = base_backoff * (2 ** attempts) + random.random() * 0.5
            if verbosity:
                print(f"[api_client] 403 received, backing off {wait:.1f}s"
                      f"(attempt {attempts+1})")
            time.sleep(wait)
            attempts += 1
            continue

        return response

    return None


def request_json(url: str,
                 *,
                 params: Dict[str, Any] | None = None,
                 timeout: int = 10,
                 verbosity: int = 0,
                 headers: Dict[str, str] | None = None,
                 retry_limit: int = 3,
                 base_backoff: float = 1.0) -> Any | None:
    """Fetch and parse JSON from a URL with shared request handling."""
    response = _request_with_retries(
        url,
        params=params,
        timeout=timeout,
        verbosity=verbosity,
        headers=headers,
        retry_limit=retry_limit,
        base_backoff=base_backoff
    )
    if response is None:
        return None

    status_attr = getattr(response, 'status_code', None)
    status = _coerce_status_code(status_attr)

    if status != 200:
        if verbosity:
            body_snippet = getattr(response, 'text', '')[:200].replace("\n", " ")
            print(
                f"[api_client] non-200 response for {url}: {status}",
                file=sys.stderr
            )
            print(
                f"[api_client] response body snippet: {body_snippet!r}",
                file=sys.stderr
            )
        return None

    try:
        return response.json()
    except (JSONDecodeError, ValueError) as exc:
        if verbosity:
            print(f"[api_client] invalid JSON response from {url}: {exc}", file=sys.stderr)
        return None


def request_text(url: str,
                 *,
                 params: Dict[str, Any] | None = None,
                 timeout: int = 10,
                 verbosity: int = 0,
                 headers: Dict[str, str] | None = None,
                 retry_limit: int = 3,
                 base_backoff: float = 1.0) -> str | None:
    """Fetch text content from a URL with shared request handling."""
    response = _request_with_retries(
        url,
        params=params,
        timeout=timeout,
        verbosity=verbosity,
        headers=headers,
        retry_limit=retry_limit,
        base_backoff=base_backoff
    )
    if response is None:
        return None

    status_attr = getattr(response, 'status_code', None)
    status = _coerce_status_code(status_attr)

    if status != 200:
        if verbosity:
            print(f"[api_client] non-200 response for {url}: {status}", file=sys.stderr)
        return None

    return getattr(response, 'text', '')


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
#pragma pylint: enable=too-many-nested-blocks, too-many-branches, too-many-locals, too-many-statements
