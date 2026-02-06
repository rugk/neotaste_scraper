"""
This tool allows you to scrape restaurant deal information from
NeoTaste's city-specific restaurant pages.
You can filter and retrieve restaurant deals, including
”event-deals“ (marked with 🌟), and export the data to
different formats: text, JSON, or HTML.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import importlib
import sys
import json
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

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
    """Given a string (possibly JSON containing HTML fragments), try to parse and return
    a list of <a> Tag elements that point to restaurant pages."""
    soup = BeautifulSoup(text, 'html.parser')
    anchors = soup.select("a[href*='/restaurants/']")
    return anchors


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


def _extract_anchors_from_flight_data(html: str) -> List[Tag]:
    """Use njsparser to parse Next.js flight data from the page HTML and extract <a> anchors.

    This method uses the njsparser.BeautifulFD API to iterate over flight data chunks and
    extract HTML fragments from structured data. If `njsparser` is not available, an
    informative debug message will be printed and an empty list returned.
    """
    if not NJS_AVAILABLE:
        # Let caller decide; always provide a helpful debug message
        import sys
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
    for data in fd.find_iter([njsparser.T.Data, njsparser.T.Element]):
        # Data objects may carry a .content or .value attribute with nested structures
        content = getattr(data, 'content', None)
        if content is None:
            content = getattr(data, 'value', None)

        # If the data is structured, try to dump to JSON string and parse any embedded HTML
        try:
            content_str = json.dumps(content, ensure_ascii=False)
        except (TypeError, ValueError):
            content_str = str(content)

        anchors.extend(_extract_anchors_from_text(content_str))

    return anchors


def fetch_deals_from_city(city_slug: str,
                          filter_mode: Optional[str] = None,
                          lang: str = "de") -> List[Dict[str, Any]]:
    """Scrape deals from a specific city and optionally filter deals.

    Attempts a best-effort to retrieve the fully rendered restaurant list by:
    1) Parsing the initial page HTML (server-side rendered elements)
    2) Using `njsparser` to extract Next.js flight data that may contain additional restaurant
       HTML fragments (preferred)
    3) Optionally using `njsparser` rendering helpers as a last-resort fallback

    Note: This scraper now prefers `njsparser` (BeautifulFD) to extract Next.js flight data.
    filter_mode may be None or one of 'events','flash','special'.
    """

    url = get_city_url(city_slug, lang)
    try:
        html = requests.get(url, timeout=10).text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

    print(f"[neotaste_scraper] Fetching {url}", file=sys.stderr)

    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, Any]] = []

    # First, parse what we have from the page HTML
    cards = soup.select("a[href*='/restaurants/']")

    for card in cards:
        result = extract_deals_from_card(card, filter_mode)
        if result:
            results.append(result)

    # Always attempt to use njsparser flight-data extractor
    anchors_fd = _extract_anchors_from_flight_data(html)
    if anchors_fd:
        print(
            f"[neotaste_scraper] Using njsparser flight-data extractor for {city_slug}",
            file=sys.stderr,
        )
        seen_links = {r['link'] for r in results}
        for a in anchors_fd:
            link = a.get('href')
            if not link:
                continue
            full_link = link if link.startswith('http') else BASE_URL + link
            if full_link in seen_links:
                continue
            parsed = extract_deals_from_card(a, filter_mode)
            if parsed:
                results.append(parsed)
                seen_links.add(full_link)
    else:
        print(
            f"[neotaste_scraper] njsparser flight-data extractor returned no anchors for {city_slug}",
            file=sys.stderr,
        )

    # If flight data didn't produce everything, try njsparser renderer helpers (last resort)
    if len(results) < 20:
        njs_html = _try_njsparser_render(url)
        if njs_html:
            print(
                f"[neotaste_scraper] Using njsparser renderer fallback for {city_slug}",
                file=sys.stderr,
            )
            anchors = _extract_anchors_from_text(njs_html)
            seen_links = {r['link'] for r in results}
            for a in anchors:
                link = a.get('href')
                if not link:
                    continue
                full_link = link if link.startswith('http') else BASE_URL + link
                if full_link in seen_links:
                    continue
                parsed = extract_deals_from_card(a, filter_mode)
                if parsed:
                    results.append(parsed)
                    seen_links.add(full_link)
        else:
            print(f"[neotaste_scraper] njsparser renderer fallback produced no anchors for {city_slug}", file=sys.stderr)

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
