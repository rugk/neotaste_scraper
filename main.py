import argparse
import requests
import json
from bs4 import BeautifulSoup

def fetch_deals_from_city(city_slug: str, filter_events: bool):
    """Scrape deals from a specific city and optionally filter event deals."""
    url = f"https://neotaste.com/de/restaurants/{city_slug}"
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    results = []

    # Each restaurant card is an <a> with a restaurant link
    cards = soup.select("a[href*='/restaurants/']")

    for card in cards:
        link = card.get("href")
        if not link.startswith("http"):
            link = "https://neotaste.com" + link

        # Restaurant name
        name_el = card.select_one("h3, h4, .font-semibold")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)

        # Deal container
        deals_container = card.select_one('[data-sentry-component="RestaurantCardDeals"]')
        if not deals_container:
            continue

        # Deal preview spans
        deal_spans = deals_container.select('[data-sentry-component="RestaurantDealPreview"] span')

        deals = [
            sp.get_text(strip=True)
            for sp in deal_spans
            if sp.get_text(strip=True)
        ]

        if not deals:
            continue

        # Filter only event deals (those with 🌟)
        if filter_events:
            deals = [deal for deal in deals if "🌟" in deal]

        if not deals:
            continue

        results.append({
            "restaurant": name,
            "deals": deals,
            "link": link
        })

    return results

def fetch_all_cities():
    """Scrape the main cities page to get a list of all cities."""
    url = "https://neotaste.com/de/restaurants"
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    city_links = soup.select('[data-sentry-component="CitiesList"] a')
    cities = [link.get("href").split("/")[3] for link in city_links if link.get("href")]

    return cities

def print_deals(deals):
    """Print the formatted deals (text output)."""
    for r in deals:
        print(f"{r['restaurant']}")
        for d in r['deals']:
            print(f" - {d}")
        print(f" → {r['link']}")
        print()

def output_json(deals):
    """Output deals in JSON format."""
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(deals, f, ensure_ascii=False, indent=4)

def output_html(deals):
    """Output deals in simple HTML format."""
    html_content = """
    <html>
    <head><title>NeoTaste Deals</title></head>
    <body>
    <h1>NeoTaste Deals</h1>
    """
    for r in deals:
        html_content += f"<h2>{r['restaurant']}</h2>"
        html_content += "<ul>"
        for d in r['deals']:
            html_content += f"<li>{d}</li>"
        html_content += f"<a href='{r['link']}'>View Restaurant</a><br>"
        html_content += "</ul>"

    html_content += "</body></html>"

    with open("output.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    # Set up CLI argument parsing
    parser = argparse.ArgumentParser(description="NeoTaste CLI Tool")
    parser.add_argument(
        "-c", "--city", type=str, help="City to scrape (e.g., 'nuremberg')"
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

    args = parser.parse_args()

    deals = []

    if args.city:
        # Fetch and print deals for a specific city
        print(f"Fetching deals for city: {args.city}...")
        deals = fetch_deals_from_city(args.city, args.events)
    elif args.all:
        # Fetch and print deals for all cities
        print("Fetching deals for all cities...")
        cities = fetch_all_cities()
        for city in cities:
            print(f"Fetching deals for city: {city}...")
            deals += fetch_deals_from_city(city, args.events)

    if not deals:
        print("No deals found.")
        return

    # Print deals in text format (default)
    print_deals(deals)

    # Output in JSON format if requested
    if args.json:
        print("Outputting deals to output.json...")
        output_json(deals)

    # Output in HTML format if requested
    if args.html:
        print("Outputting deals to output.html...")
        output_html(deals)

if __name__ == "__main__":
    main()
