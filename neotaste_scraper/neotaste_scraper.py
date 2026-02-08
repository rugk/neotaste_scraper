"""
This tool allows you to scrape restaurant deal information from
NeoTaste's city-specific restaurant pages.
You can filter and retrieve restaurant deals, including
”event-deals“ (marked with 🌟), and export the data to
different formats: text, JSON, or HTML.
"""

from typing import Any, Dict, List, Optional
import sys
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from neotaste_scraper.constants import BASE_URL, Deal, Verbosity
from neotaste_scraper.helper import filter_deals, get_city_url, get_slug_from_link
from . import api_client

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

    parsed_deals = filter_deals(parsed_deals, filter_mode)
    results = [d.text for d in parsed_deals]
    if not results:
        return None
    return {"restaurant": name, "deals": results, "link": link}


def fetch_deals_from_city(city_slug: str,
                          filter_mode: Optional[str] = None,
                          lang: str = "de",
                          verbosity: Verbosity = Verbosity.SILENT) -> List[Dict[str, Any]]:
    """Scrape deals from a specific city and optionally filter deals.

    Attempts a best-effort to retrieve the fully rendered restaurant list by:
    1) Fetching the HTML and parsing server-side rendered cards
    2) Fetching the JSON API (which provides more results and pagination)

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
    results_by_slug, sources_summary = fetch_api(city_slug, lang, verbosity, filter_mode)

    soup = BeautifulSoup(html, "html.parser")

    # 1) Parse server-side HTML cards
    parse_html(filter_mode, verbosity, results_by_slug, sources_summary, soup)

    # Return deduplicated results
    results = list(results_by_slug.values())

    print(f"[neotaste_scraper] Final: {len(results)} restaurants from "
          f"{''.join(sources_summary) if sources_summary else 'no sources'} "
          f"for {city_slug}", file=sys.stderr)
    return results

def parse_html(filter_mode, verbosity, results_by_slug, sources_summary, soup):
    """Parse the HTML for restaurant cards and extract deals, applying filters."""
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


def fetch_api(city_slug,
              lang,
              verbosity, 
              filter_mode: Optional[str] = None):
    """Fetch restaurant data from the NeoTaste JSON API with pagination."""
    try:
        api_results = api_client.fetch_restaurants_from_api(
            city_slug,
            lang=lang,
            verbosity=verbosity.value)
    except Exception:  # pylint: disable=broad-except
        api_results = []

    results_by_slug: Dict[str, Dict[str, Any]] = {}
    sources_summary = []

    if api_results:
        added_api = 0
        for restaurant in api_results:
            # obj already contains link and restaurant/deals
            link = restaurant.get('link')
            if not link:
                continue
            slug = link.split('/')[-1]
            if slug and slug not in results_by_slug:
                # If filter_mode is set, only include restaurants with matching deals
                filtered_deals = filter_deals(restaurant.get('deals', []), filter_mode)
                restaurant['deals'] = filtered_deals
                results_by_slug[slug] = restaurant
                added_api += 1

            # remove empty entries if filter_mode filters out all deals
            if slug in results_by_slug and not results_by_slug[slug]['deals']:
                del results_by_slug[slug]

        sources_summary.append(f"API: {added_api}")
        if verbosity.value > Verbosity.SILENT.value:
            print(f"[neotaste_scraper] API client added {added_api} restaurants", file=sys.stderr)

    if verbosity.value > Verbosity.SILENT.value:
        print(f"[neotaste_scraper] Fetching {city_slug}", file=sys.stderr)
    return results_by_slug, sources_summary


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
