"""
This tool allows you to scrape restaurant deal information from
NeoTaste's city-specific restaurant pages.
You can filter and retrieve restaurant deals, including
”event-deals“ (marked with 🌟), and export the data to
different formats: text, JSON, or HTML.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import importlib
import sys
import json
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


class Verbosity(Enum):
    """Verbosity levels for debug output."""
    SILENT = 0
    NORMAL = 1  # -v: chunk summaries and limited previews
    DEBUG = 2   # -vv: full JSON dumps for all chunks


# Constants
BASE_URL = "https://neotaste.com"


def get_city_url(city_slug: str, lang: str = "de") -> str:
    """Construct full URL for the given city with the specified language."""
    return f"{BASE_URL}/{lang}/restaurants/{city_slug}"


@dataclass
class Deal:
    """A parsed deal from a restaurant card."""
    text: str
    component: str
    deal_type: str  # 'flash', 'event', 'flash+event', 'other'


def extract_deals_from_card(card: Tag,
                            filter_mode: Optional[str] = None
                            ) -> Optional[Dict[str, Any]]:
    """Extract deals from a single restaurant card.

    filter_mode may be one of: None (no filter), 'events' (only 🌟),
    'flash' (only flash deals), 'special' (events OR flash).
    """
    # helper functions to keep this function small and testable
    def _get_link(a_tag: Tag) -> Optional[str]:
        href = a_tag.get("href")
        if not href:
            return None
        return href if href.startswith("http") else BASE_URL + href

    def _get_name(a_tag: Tag) -> Optional[str]:
        name_element = a_tag.select_one("h4")
        return None if not name_element else name_element.get_text(strip=True)

    def _get_deal_elements(a_tag: Tag) -> List[Tag]:
        container = a_tag.select_one('[data-sentry-component="RestaurantCardDeals"]')
        if not container:
            return []
        return container.select('[data-sentry-component$="DealPreview"]')

    def _classify_deal(el: Tag) -> Optional[Deal]:
        txt = el.get_text(strip=True)
        if not txt:
            return None
        comp = el.get('data-sentry-component', '')
        inner = str(el).lower()
        is_flash_local = (
            ('flashdeal' in comp.lower())
            or ('flashdeal' in inner)
            or ('⚡' in txt)
        )
        is_event_local = (
            ('eventdeal' in comp.lower())
            or ('eventdeal' in inner)
            or ('🌟' in txt)
        )
        if is_flash_local and is_event_local:
            dtype = 'flash+event'
        elif is_flash_local:
            dtype = 'flash'
        elif is_event_local:
            dtype = 'event'
        else:
            dtype = 'other'
        return Deal(text=txt, component=comp, deal_type=dtype)

    def _filter_deals(deals_in: List[Deal], mode: Optional[str]) -> List[Deal]:
        if mode == 'events':
            return [
                d for d in deals_in
                if d.deal_type in ('event', 'flash+event')
            ]
        if mode == 'flash':
            return [
                d for d in deals_in
                if d.deal_type in ('flash', 'flash+event')
            ]
        if mode == 'special':
            return [d for d in deals_in if d.deal_type != 'other']
        return deals_in

    # assemble outputs using small helpers
    link = _get_link(card)
    if not link:
        return None
    name = _get_name(card)
    if not name:
        return None

    raw_elements = _get_deal_elements(card)
    parsed_deals: List[Deal] = []
    for elem in raw_elements:
        item = _classify_deal(elem)
        if item is not None:
            parsed_deals.append(item)

    parsed_deals = _filter_deals(parsed_deals, filter_mode)
    results = [d.text for d in parsed_deals]
    if not results:
        return None
    return {"restaurant": name, "deals": results, "link": link}

# Prefer njsparser for parsing Next.js flight data. This scraper relies on it.
try:
    import njsparser  # type: ignore
    NJS_AVAILABLE = True
except ImportError:
    njsparser = None  # type: ignore
    NJS_AVAILABLE = False


def _extract_anchors_from_text(text: str) -> List[Tag]:
    """Given a string (possibly JSON with HTML or plain HTML), try to parse and return
    a list of <a> Tag elements that point to restaurant pages.
    Tries JSON parsing first to avoid spurious BeautifulSoup warnings."""
    # Try JSON parsing first to avoid BeautifulSoup MarkupResemblesLocatorWarning
    try:
        data = json.loads(text)
        text = json.dumps(data, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        # Not JSON, proceed with raw text
        pass
    
    # Now try HTML parsing
    try:
        soup = BeautifulSoup(text, 'html.parser')
        anchors = soup.select("a[href*='/restaurants/']")
        return anchors
    except Exception:
        return []


def _try_njsparser_render(url: str) -> Optional[str]:
    """Optional: use the `njsparser` package (if installed) to render the Next.js page
    and return an HTML string. This is a best-effort fallback; failures are silently ignored.

    The function will try common entry points on the imported module (parse/render/extract/get_html).
    """
    try:
        njs = importlib.import_module('njsparser')
    except ImportError:
        return None

    for fn in ('render', 'parse', 'extract', 'get_html', 'render_html'):
        if hasattr(njs, fn):
            try:
                res = getattr(njs, fn)(url)
                if isinstance(res, str) and res.strip():
                    return res
                if isinstance(res, dict) and 'html' in res and isinstance(res['html'], str):
                    return res['html']
            except (AttributeError, TypeError, ValueError):
                # Skip this candidate on common errors
                continue
    return None


def _extract_anchors_from_flight_data(html: str, verbosity: Verbosity = Verbosity.SILENT) -> List[Tag]:
    """Use njsparser to parse Next.js flight data from the page HTML and extract <a> anchors.

    This method uses the njsparser.BeautifulFD API to iterate over flight data chunks and
    extract HTML fragments from structured data. If `njsparser` is not available, an
    informative debug message will be printed and an empty list returned.
    """
    if not NJS_AVAILABLE:
        # Let caller decide; always provide a helpful debug message
        import sys
        if verbosity.value > Verbosity.SILENT.value:
            print("[neotaste_scraper] njsparser not installed; pip install njsparser", file=sys.stderr)
        return []

    try:
        fd = njsparser.BeautifulFD(html)
    except (AttributeError, TypeError, ValueError) as exc:
        # If njsparser fails to parse, print a debug message
        import sys
        print(
            "[neotaste_scraper] njsparser.BeautifulFD failed to parse the page HTML",
            file=sys.stderr,
        )
        return []

    anchors: List[Tag] = []

    def _walk_and_find_links(obj: Any, depth: int = 0) -> None:
        """Recursively walk nested structures and attempt to extract HTML fragments
        or link-like strings that point to restaurant pages.
        """
        try:
            if obj is None:
                return
            # Strings may contain HTML fragments
            if isinstance(obj, str):
                if '/restaurants/' in obj:
                    anchors_found = _extract_anchors_from_text(obj)
                    anchors.extend(anchors_found)
                return
            # Lists/tuples: iterate
            if isinstance(obj, (list, tuple)):
                for it in obj:
                    _walk_and_find_links(it, depth + 1)
                return
            # Dicts: check values and keys
            if isinstance(obj, dict):
                for k, v in obj.items():
                    # some flight-data stores HTML under 'children' or 'value'
                    if isinstance(k, str) and ('children' in k or 'html' in k or 'link' in k or 'href' in k):
                        _walk_and_find_links(v, depth + 1)
                    else:
                        _walk_and_find_links(v, depth + 1)
                return
            # Fallback: stringify and inspect
            s = str(obj)
            if '/restaurants/' in s:
                anchors_found = _extract_anchors_from_text(s)
                anchors.extend(anchors_found)
        except Exception:
            # Best-effort: don't fail the whole parsing flow for one bad node
            return

    # Iterate and provide verbose debug output so callers can step through njsparser internals
    import sys
    total_chunks = 0
    for data in fd.find_iter([njsparser.T.Data, njsparser.T.Element]):
        total_chunks += 1
        # Data objects may carry a .content or .value attribute with nested structures
        content = getattr(data, 'content', None)
        if content is None:
            content = getattr(data, 'value', None)

        # Print debug summary for this chunk (index, type, presence of content)
        try:
            idx = getattr(data, 'index', '?')
            typ = type(data).__name__
            has_content = 'yes' if content is not None else 'no'
            if verbosity.value > Verbosity.SILENT.value:
                print(f"[neotaste_scraper] njsparser chunk #{total_chunks} type={typ} idx={idx} has_content={has_content}", file=sys.stderr)
        except Exception:
            if verbosity.value > Verbosity.SILENT.value:
                print(f"[neotaste_scraper] njsparser chunk #{total_chunks} (summary failed)", file=sys.stderr)

        # Try to extract links from nested content
        _walk_and_find_links(content)

        # Print preview: full for chunks with restaurants, truncated for noise
        try:
            if verbosity.value > Verbosity.SILENT.value:
                content_preview = json.dumps(content, ensure_ascii=False)
                # Heuristic: check if this chunk likely contains useful data
                is_useful = any(key in content_preview for key in ['state', 'queries', 'restaurants', 'slug', 'citySlug', 'deals'])
                if is_useful and verbosity == Verbosity.DEBUG:
                    # Full dump for useful chunks in debug mode
                    print(f"[neotaste_scraper] chunk #{total_chunks} full preview:\n{content_preview}\n---", file=sys.stderr)
                elif is_useful:
                    # Truncated for useful chunks in normal mode
                    if len(content_preview) > 300:
                        content_preview = content_preview[:300] + '…'
                    print(f"[neotaste_scraper] chunk #{total_chunks} preview: {content_preview}", file=sys.stderr)
                else:
                    # Always truncate unrelated chunks
                    if len(content_preview) > 150:
                        content_preview = content_preview[:150] + '…'
                    print(f"[neotaste_scraper] chunk #{total_chunks} (unrelated): {content_preview}", file=sys.stderr)
        except Exception:
            pass

    if verbosity.value > Verbosity.SILENT.value:
        print(f"[neotaste_scraper] njsparser found {total_chunks} flight-data chunks, extracted {len(anchors)} anchors", file=sys.stderr)
    return anchors


def _extract_structured_restaurants_from_flight_data(html: str, city_slug: str, lang: str = 'de', verbosity: Verbosity = Verbosity.SILENT) -> List[Dict[str, Any]]:
    """Parse flight-data with njsparser and extract structured restaurant records + deals.

    Returns a list of dicts: {"restaurant": name, "deals": [deal_names], "link": url}
    Looks for chunks containing state.queries with restaurants (the restaurant list from the API).
    Filters to only real restaurants in the specified city (by requiring citySlug and/or location fields).
    """
    if not NJS_AVAILABLE:
        if verbosity.value > Verbosity.SILENT.value:
            print("[neotaste_scraper] njsparser not installed; structured extractor skipped", file=sys.stderr)
        return []

    try:
        fd = njsparser.BeautifulFD(html)
    except Exception:
        if verbosity.value > Verbosity.SILENT.value:
            print("[neotaste_scraper] njsparser.BeautifulFD failed for structured extractor", file=sys.stderr)
        return []

    found: Dict[str, Dict[str, Any]] = {}  # key is slug to avoid duplicates

    def _extract_deals_from_obj(obj: Any) -> List[str]:
        """Extract deal names from a nested deal object or deals list."""
        deals_out = []
        if isinstance(obj, dict):
            # Check if this is a deal object with 'name' field
            if 'name' in obj and isinstance(obj.get('name'), str):
                name = obj['name'].strip()
                if name and obj.get('status') == 'available':
                    deals_out.append(name)
            # Recurse into nested structures
            for v in obj.values():
                deals_out.extend(_extract_deals_from_obj(v))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                deals_out.extend(_extract_deals_from_obj(item))
        return deals_out

    def _is_real_restaurant(obj: Any) -> bool:
        """Check if obj is likely a real restaurant (not a tag/category/country).
        Real restaurants have citySlug matching and/or location fields (latitude/longitude).
        """
        if not isinstance(obj, dict):
            return False
        # Must match the target city
        obj_city = obj.get('citySlug')
        if obj_city != city_slug:
            return False
        # Should have some restaurant-specific fields
        has_location = (obj.get('latitude') is not None or obj.get('longitude') is not None)
        has_images = isinstance(obj.get('images'), (list, tuple)) and len(obj.get('images', [])) > 0
        return has_location or has_images

    def _recurse(obj: Any, depth: int = 0) -> None:
        """Recursively search for restaurant objects and extract their data and deals."""
        try:
            if obj is None or depth > 50:
                return
            if isinstance(obj, dict):
                # Check if this is a real restaurant object
                slug = obj.get('slug')
                name = obj.get('name')
                if isinstance(slug, str) and isinstance(name, str) and slug and name:
                    if '/' not in slug and len(slug) <= 100 and len(name) <= 200:
                        if _is_real_restaurant(obj):
                            if slug not in found:
                                link = f"{BASE_URL}/{lang}/restaurants/{slug}"
                                deals = _extract_deals_from_obj(obj.get('deals', []))
                                found[slug] = {"restaurant": name, "deals": deals, "link": link}
                                if verbose:
                                    print(f"[neotaste_scraper] found restaurant: {name} with {len(deals)} deals (citySlug={obj.get('citySlug')})", file=sys.stderr)
                # Recurse into dict values
                for v in obj.values():
                    _recurse(v, depth + 1)
                return
            if isinstance(obj, (list, tuple)):
                for it in obj:
                    _recurse(it, depth + 1)
                return
        except Exception:
            return

    total_chunks = 0
    for data in fd.find_iter([njsparser.T.Data, njsparser.T.Element]):
        total_chunks += 1
        content = getattr(data, 'content', None)
        if content is None:
            content = getattr(data, 'value', None)
        _recurse(content, depth=0)

    if verbosity.value > Verbosity.SILENT.value:
        print(f"[neotaste_scraper] structured extractor found {len(found)} restaurants with deals from {total_chunks} chunks", file=sys.stderr)

    return list(found.values())


def fetch_deals_from_city(city_slug: str,
                          filter_mode: Optional[str] = None,
                          lang: str = "de",
                          verbosity: Verbosity = Verbosity.SILENT) -> List[Dict[str, Any]]:
    """Scrape deals from a specific city and optionally filter deals.

    Attempts a best-effort to retrieve the fully rendered restaurant list by:
    1) Parsing the initial page HTML (server-side rendered elements)
    2) Using `njsparser` to extract structured restaurant objects with deals from flight-data
    3) Using njsparser to extract HTML anchors from flight-data
    4) Optionally using `njsparser` rendering helpers as a last-resort fallback

    Deduplicates by link and applies filter_mode at the end.
    filter_mode may be None or one of 'events','flash','special'.
    """

    url = get_city_url(city_slug, lang)
    try:
        html = requests.get(url, timeout=10).text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

    if verbosity.value > Verbosity.SILENT.value:
        print(f"[neotaste_scraper] Fetching {url}", file=sys.stderr)

    soup = BeautifulSoup(html, "html.parser")
    results_by_slug: Dict[str, Dict[str, Any]] = {}

    # Helper: extract slug from a URL (last path component)
    def get_slug_from_link(link: str) -> Optional[str]:
        """Extract restaurant slug from URL."""
        if not link:
            return None
        # Remove protocol and domain, get the last path component
        path = link.split('/')[-1]
        return path if path else None

    # 1) Parse server-side HTML cards
    cards = soup.select("a[href*='/restaurants/']")
    for card in cards:
        result = extract_deals_from_card(card, filter_mode)
        if result:
            slug = get_slug_from_link(result['link'])
            if slug:
                results_by_slug[slug] = result

    # 2) Extract structured restaurant objects from flight-data (has deals)
    structured = _extract_structured_restaurants_from_flight_data(html, city_slug=city_slug, lang=lang, verbosity=verbosity)
    if structured:
        if verbosity.value > Verbosity.SILENT.value:
            print(f"[neotaste_scraper] structured flight-data extractor found {len(structured)} restaurants", file=sys.stderr)
        for obj in structured:
            slug = get_slug_from_link(obj['link'])
            if slug and slug not in results_by_slug:
                results_by_slug[slug] = obj

    # 3) Try HTML anchor extraction from flight-data
    anchors_fd = _extract_anchors_from_flight_data(html, verbosity=verbosity)
    if anchors_fd:
        if verbosity.value > Verbosity.SILENT.value:
            print(f"[neotaste_scraper] njsparser flight-data anchor extractor found {len(anchors_fd)} anchors", file=sys.stderr)
        for a in anchors_fd:
            link = a.get('href')
            if not link:
                continue
            full_link = link if link.startswith('http') else BASE_URL + link
            slug = get_slug_from_link(full_link)
            if slug and slug not in results_by_slug:
                parsed = extract_deals_from_card(a, filter_mode)
                if parsed:
                    results_by_slug[slug] = parsed

    # 4) If flight data didn't produce everything, try njsparser renderer helpers (last resort)
    if len(results_by_slug) < 20:
        njs_html = _try_njsparser_render(url)
        if njs_html:
            if verbosity.value > Verbosity.SILENT.value:
                print(f"[neotaste_scraper] Using njsparser renderer fallback for {city_slug}", file=sys.stderr)
            anchors = _extract_anchors_from_text(njs_html)
            for a in anchors:
                link = a.get('href')
                if not link:
                    continue
                full_link = link if link.startswith('http') else BASE_URL + link
                slug = get_slug_from_link(full_link)
                if slug and slug not in results_by_slug:
                    parsed = extract_deals_from_card(a, filter_mode)
                    if parsed:
                        results_by_slug[slug] = parsed

    # Return deduplicated results (dict.values maintains insertion order in Python 3.7+)
    results = list(results_by_slug.values())
    if verbosity.value > Verbosity.SILENT.value:
        print(f"[neotaste_scraper] final result: {len(results)} unique restaurants after deduplication", file=sys.stderr)
    return results


def fetch_all_cities(lang: str = "de") -> List[Dict[str, str]]:
    """Scrape the main cities page to get a list of all cities."""
    url = f"{BASE_URL}/{lang}/restaurants"
    try:
        html = requests.get(url, timeout=10).text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    city_links = soup.select('[data-sentry-component="CitiesList"] a')

    cities = []
    for link in city_links:
        # This class should contain the city name
        city_name = link.select_one(".font-semibold")

        # Ensure the city name is extracted correctly and strip out any extra spaces
        if city_name:
            cities.append({
                "slug": link.get("href").split("/")[3],
                "name": city_name.get_text(strip=True)
            })

    return cities
