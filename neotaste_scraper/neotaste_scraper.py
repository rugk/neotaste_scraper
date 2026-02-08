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
import sys
import json
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
import njsparser
from . import api_client


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


def _extract_anchors_from_flight_data(html: str, verbosity: Verbosity = Verbosity.SILENT) -> List[Tag]:
    """Use njsparser to parse Next.js flight data and extract restaurant anchors.
    
    Navigates the known flight-data structure: state.queries[].state.data.pages[].data[]
    which contains restaurant objects with link information.
    """
    if not NJS_AVAILABLE:
        if verbosity.value > Verbosity.SILENT.value:
            print("[neotaste_scraper] njsparser not installed; pip install njsparser", file=sys.stderr)
        return []

    try:
        fd = njsparser.BeautifulFD(html)
    except (AttributeError, TypeError, ValueError):
        if verbosity.value > Verbosity.SILENT.value:
            print("[neotaste_scraper] njsparser.BeautifulFD failed to parse page HTML", file=sys.stderr)
        return []

    anchors: List[Tag] = []

    def _search_for_restaurants(obj: Any, depth: int = 0) -> None:
        """Search for restaurant objects and HTML fragments in nested structures."""
        if depth > 30 or obj is None:
            return
        
        try:
            if isinstance(obj, dict):
                # Check for restaurant objects with slug/name
                if 'slug' in obj and 'name' in obj:
                    slug = obj.get('slug')
                    if isinstance(slug, str) and slug and '/' not in slug and len(slug) < 100:
                        link_text = f'<a href="/restaurants/{slug}">{obj.get("name", "")}</a>'
                        found = _extract_anchors_from_text(link_text)
                        anchors.extend(found)
                
                # Recurse into dict values
                for v in obj.values():
                    _search_for_restaurants(v, depth + 1)
            
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _search_for_restaurants(item, depth + 1)
            
            elif isinstance(obj, str):
                # Also try to extract HTML from strings containing restaurant links
                if '/restaurants/' in obj:
                    found = _extract_anchors_from_text(obj)
                    anchors.extend(found)
        except Exception:
            pass

    # Parse through all chunks
    total_chunks = 0
    for data in fd.find_iter([njsparser.T.Data, njsparser.T.Element]):
        total_chunks += 1
        content = getattr(data, 'content', None) or getattr(data, 'value', None)
        
        if verbosity.value > Verbosity.SILENT.value:
            try:
                idx = getattr(data, 'index', '?')
                typ = type(data).__name__
                print(f"[neotaste_scraper] chunk #{total_chunks} type={typ} idx={idx}", file=sys.stderr)
            except Exception:
                pass
        
        _search_for_restaurants(content)

    if verbosity.value > Verbosity.SILENT.value:
        print(f"[neotaste_scraper] njsparser found {total_chunks} chunks, extracted {len(anchors)} anchors", file=sys.stderr)
    
    return anchors


def _extract_structured_restaurants_from_flight_data(
    html: str,
    city_slug: str,
    lang: str = 'de',
    verbosity: Verbosity = Verbosity.SILENT
) -> List[Dict[str, Any]]:
    """Parse flight-data with njsparser and extract structured restaurant
    records + deals.
    
    Navigates the known structure: state.queries[].state.data.pages[].data[]
    Returns a list of dicts: {"restaurant": name, "deals": [deal_names],
    "link": url}
    """
    fd = njsparser.BeautifulFD(html)

    found: Dict[str, Dict[str, Any]] = {}  # key is slug to avoid duplicates

    def _extract_deals_from_list(deals_obj: Any) -> List[str]:
        """Extract deal names from a deals list, filtering by status='available'."""
        if not isinstance(deals_obj, (list, tuple)):
            return []
        
        deals_out = []
        for deal in deals_obj:
            if isinstance(deal, dict):
                name = deal.get('name', '').strip() if deal.get('name') else ''
                # Only include available deals
                if name and deal.get('status') == 'available':
                    deals_out.append(name)
        return deals_out

    def _is_valid_restaurant(obj: Any, target_city: str) -> bool:
        """Check if obj is a valid restaurant record."""
        if not isinstance(obj, dict):
            return False
        # Must be in the target city
        if obj.get('citySlug') != target_city:
            return False
        # Must have slug, name, and location or images
        slug = obj.get('slug')
        name = obj.get('name')
        if not (isinstance(slug, str) and isinstance(name, str) and slug and name):
            return False
        if '/' in slug or len(slug) > 100:
            return False
        # Must have location or images to be a real restaurant
        has_location = obj.get('latitude') is not None or obj.get('longitude') is not None
        has_images = isinstance(obj.get('images'), (list, tuple)) and len(obj.get('images', [])) > 0
        return has_location or has_images

    def _search_restaurants(obj: Any, depth: int = 0) -> None:
        """Search through nested structures for restaurant objects.
        Also navigates the known structure state.queries[].state.data.pages[].data[]
        """
        if depth > 30 or obj is None:
            return
        
        try:
            if isinstance(obj, dict):
                # Check if this looks like a restaurant object
                if _is_valid_restaurant(obj, city_slug):
                    slug = obj['slug']
                    if slug not in found:
                        link = f"{BASE_URL}/{lang}/restaurants/{slug}"
                        deals = _extract_deals_from_list(obj.get('deals', []))
                        found[slug] = {
                            "restaurant": obj['name'],
                            "deals": deals,
                            "link": link
                        }
                        if verbosity.value > Verbosity.NORMAL.value:
                            print(
                                f"[neotaste_scraper] found restaurant: "
                                f"{obj['name']} ({len(deals)} deals)",
                                file=sys.stderr
                            )
                
                # Recurse into nested structures
                for v in obj.values():
                    _search_restaurants(v, depth + 1)
            
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _search_restaurants(item, depth + 1)
        except Exception:
            pass

    # Parse through all flight data chunks
    total_chunks = 0
    for data in fd.find_iter([njsparser.T.Data, njsparser.T.Element]):
        total_chunks += 1
        content = getattr(data, 'content', None) or getattr(data, 'value', None)
        # if verbosity.value > Verbosity.SILENT.value:
        content_as_string = json.dumps(content, indent=2)
        _search_restaurants(content)

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

    # Try JSON API first — it provides full pagination and more results
    try:
        api_results = api_client.fetch_restaurants_from_api(city_slug, lang=lang, verbosity=verbosity.value)
    except Exception:
        api_results = []

    results_by_slug: Dict[str, Dict[str, Any]] = {}
    sources_summary = []
    
    if api_results:
        added_api = 0
        for obj in api_results:
            # obj already contains link and restaurant/deals
            link = obj.get('link')
            if not link:
                continue
            slug = link.split('/')[-1]
            if slug and slug not in results_by_slug:
                results_by_slug[slug] = obj
                added_api += 1
        sources_summary.append(f"API: {added_api}")
        if verbosity.value > Verbosity.SILENT.value:
            print(f"[neotaste_scraper] API client added {added_api} restaurants", file=sys.stderr)

    if verbosity.value > Verbosity.SILENT.value:
        print(f"[neotaste_scraper] Fetching {url}", file=sys.stderr)

    soup = BeautifulSoup(html, "html.parser")

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
    html_count = 0
    for card in cards:
        result = extract_deals_from_card(card, filter_mode)
        if result:
            slug = get_slug_from_link(result['link'])
            if slug:
                results_by_slug[slug] = result
                html_count += 1
    if html_count > 0:
        sources_summary.append(f"HTML: {html_count}")
    if verbosity.value > Verbosity.SILENT.value:
        print(
            f"[neotaste_scraper] HTML parsing found {html_count} restaurants",
            file=sys.stderr
        )

    # 2) Extract structured restaurant objects from flight-data (has deals)
    structured = _extract_structured_restaurants_from_flight_data(
        html, city_slug=city_slug, lang=lang, verbosity=verbosity
    )
    added_structured = 0
    if structured:
        for obj in structured:
            slug = get_slug_from_link(obj['link'])
            if slug and slug not in results_by_slug:
                results_by_slug[slug] = obj
                added_structured += 1
        if added_structured > 0:
            sources_summary.append(f"Flight-data: {added_structured}")
        if verbosity.value > Verbosity.SILENT.value:
            print(
                f"[neotaste_scraper] Flight-data extractor added {added_structured}/"
                f"{len(structured)} new restaurants",
                file=sys.stderr
            )

    # 3) Try HTML anchor extraction from flight-data
    anchors_fd = _extract_anchors_from_flight_data(html, verbosity=verbosity)
    added_anchors = 0
    if anchors_fd:
        for a in anchors_fd:
            link = a.get('href')
            if not link:
                continue
            full_link = (
                link if link.startswith('http') else BASE_URL + link
            )
            slug = get_slug_from_link(full_link)
            if slug and slug not in results_by_slug:
                parsed = extract_deals_from_card(a, filter_mode)
                if parsed:
                    results_by_slug[slug] = parsed
                    added_anchors += 1
        if added_anchors > 0:
            sources_summary.append(f"Anchors: {added_anchors}")
        if verbosity.value > Verbosity.SILENT.value:
            print(
                f"[neotaste_scraper] Anchor extractor added {added_anchors}/"
                f"{len(anchors_fd)} new restaurants",
                file=sys.stderr
            )

    # Return deduplicated results
    results = list(results_by_slug.values())

    print(f"[neotaste_scraper] Final: {len(results)} restaurants from {', '.join(sources_summary) if sources_summary else 'no sources'} for {city_slug}", file=sys.stderr)
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
