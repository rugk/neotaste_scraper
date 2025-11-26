"""
This tool allows you to scrape restaurant deal information from
NeoTaste's city-specific restaurant pages.
You can filter and retrieve restaurant deals, including 
”event-deals“ (marked with 🌟), and export the data to
different formats: text, JSON, or HTML.
"""
import json
import argparse
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

# Constants
BASE_URL = "https://neotaste.com"

# Localized Strings
localized_strings = {
    'de': {
        'deals_title': "NeoTaste Deals",
        'restaurant_link_text': "Mehr Informationen/Details zum Angebot",
        'view_restaurant': "Restaurant ansehen",
        'deals_in': "Deals in",
        'no_deals_found': "Keine Deals gefunden.",
        'city_page': "Seite der Stadt",
        'restaurant_details': "Mehr Details zum Restaurant",
    },
    'en': {
        'deals_title': "NeoTaste Deals",
        'restaurant_link_text': "More Info/Details about the Offer",
        'view_restaurant': "View Restaurant",
        'deals_in': "Deals in",
        'no_deals_found': "No deals found.",
        'city_page': "City Page",
        'restaurant_details': "Restaurant Details",
    }
}

def get_localized_strings(lang):
    """Return the localized strings for the given language."""
    return localized_strings.get(lang, localized_strings['de'])  # Default to German if not found

def get_city_url(city_slug, lang="de"):
    """Construct full URL for the given city with the specified language."""
    return f"{BASE_URL}/{lang}/restaurants/{city_slug}"

def extract_deals_from_card(card, filter_events):
    """Extract deals from a single restaurant card."""
    link = card.get("href")
    if not link.startswith("http"):
        link = BASE_URL + link

    # Restaurant name
    name_el = card.select_one("h4")
    if not name_el:
        return None  # Return None if no name is found
    name = name_el.get_text(strip=True)

    # Deal container
    deals_container = card.select_one('[data-sentry-component="RestaurantCardDeals"]')
    if not deals_container:
        return None  # Return None if no deals container is found

    # Extract deal text
    deal_spans = deals_container.select('[data-sentry-component="RestaurantDealPreview"] span')
    deals = [sp.get_text(strip=True) for sp in deal_spans if sp.get_text(strip=True)]

    if filter_events:
        # Filter only event deals (those with 🌟)
        deals = [deal for deal in deals if "🌟" in deal]

    if not deals:
        return None  # Return None if no deals match the filter

    return {"restaurant": name, "deals": deals, "link": link}

def fetch_deals_from_city(city_slug: str, filter_events: bool, lang="de"):
    """Scrape deals from a specific city and optionally filter event deals."""
    url = get_city_url(city_slug, lang)
    try:
        html = requests.get(url, timeout=10).text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Each restaurant card is an <a> with a restaurant link
    cards = soup.select("a[href*='/restaurants/']")

    for card in cards:
        result = extract_deals_from_card(card, filter_events)
        if result:
            results.append(result)

    return results


def fetch_all_cities(lang="de"):
    """Scrape the main cities page to get a list of all cities."""
    url = f"{BASE_URL}/{lang}/restaurants"
    try:
        html = requests.get(url, timeout=10).text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    city_links = soup.select('[data-sentry-component="CitiesList"] a')
    cities = [
        {"slug": link.get("href").split("/")[3], "name": link.get_text(strip=True)}
        for link in city_links if link.get("href")
    ]

    return cities

def print_deals(cities_data, lang="de"):
    """Print the formatted deals (text output)."""
    strings = get_localized_strings(lang)
    for city, city_deals in cities_data.items():
        print(f"\n{strings['deals_in']} {city.capitalize()}:")
        for r in city_deals:
            print(f"  {r['restaurant']}")
            for d in r['deals']:
                print(f"   - {d}")
            print(f"   → {r['link']}")

def output_json(cities_data):
    """Output deals in JSON format, including city information."""
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(cities_data, f, ensure_ascii=False, indent=4)

def output_html(cities_data, lang="de"):
    """Output deals in simple HTML format, grouped by city, using Jinja2 for templating."""
    strings = get_localized_strings(lang)

    # Set up Jinja2 environment and load the template
    env = Environment(loader=FileSystemLoader(searchpath="templates"))
    template = env.get_template("deals_template.html")

    # Prepare the context for the template
    context = {
        'base_url': BASE_URL,
        'lang': lang,
        'title': strings['deals_title'],
        'cities_data': cities_data,
        'strings': strings
    }

    # Render the template with data
    html_content = template.render(context)

    # Output HTML content to a file
    with open("output.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    """Main entry point"""
    # Set up CLI argument parsing
    parser = argparse.ArgumentParser(description="NeoTaste CLI Tool")
    parser.add_argument(
        "-c", "--city", type=str, help="City to scrape (e.g., 'berlin')"
    )
    parser.add_argument(
        "-a", "--all", action="store_true", help="Scrape all available cities"
    )
    parser.add_argument(
        "-e", "--events", action="store_true", help="Filter only event deals (🌟)"
    )
    parser.add_argument(
        "-j", "--json", action="store_true", help="Output in JSON format"
    )
    parser.add_argument(
        "-H", "--html", action="store_true", help="Output in HTML format"
    )
    parser.add_argument(
        "-l", "--lang", type=str, choices=["de", "en"], default="de", help="Language (default: de)"
    )

    args = parser.parse_args()

    cities_data = {}

    if args.city:
        # Fetch and print deals for a specific city
        print(f"Fetching deals for city: {args.city}...")
        deals = fetch_deals_from_city(args.city, args.events, args.lang)
        cities_data[args.city] = deals
    elif args.all:
        # Fetch and print deals for all cities
        print("Fetching deals for all cities...")
        cities = fetch_all_cities(args.lang)
        for city in cities:
            print(f"Fetching deals for city: {city['slug']}...")
            city_deals = fetch_deals_from_city(city['slug'], args.events, args.lang)
            cities_data[city['slug']] = city_deals

    if not cities_data:
        print(get_localized_strings(args.lang)['no_deals_found'])
        return

    # Print deals in text format (default)
    print_deals(cities_data, args.lang)

    # Output in JSON format if requested
    if args.json:
        print("Outputting deals to output.json...")
        output_json(cities_data)

    # Output in HTML format if requested
    if args.html:
        print("Outputting deals to output.html...")
        output_html(cities_data, args.lang)

if __name__ == "__main__":
    main()
