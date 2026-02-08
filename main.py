#!/usr/bin/env python3
"""
This tool allows you to scrape restaurant deal information from
NeoTaste's city-specific restaurant pages.
You can filter and retrieve restaurant deals, including
”event-deals“ (marked with 🌟), and export the data to
different formats: text, JSON, or HTML.
"""
import argparse

from neotaste_scraper.constants import Verbosity
from neotaste_scraper.data_output import (
    print_deals,
    output_json,
    output_html,
    get_localized_strings
)
from neotaste_scraper.neotaste_scraper import (
    fetch_deals_from_city,
    fetch_all_cities,
)


def main() -> None:
    """Main entry point"""
    # Set up CLI argument parsing
    parser = argparse.ArgumentParser(description="NeoTaste CLI Tool")
    parser.add_argument(
        "-c", "--city", type=str, help="City to scrape (e.g., 'berlin')"
    )
    parser.add_argument(
        "-a", "--all", action="store_true", help="Scrape all available cities"
    )
    # Filtering options: mutually exclusive
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-e", "--events", action="store_true",
                       help="Filter only event deals (🌟)")
    group.add_argument("-f", "--flash", action="store_true",
                       help="Filter only flash deals (⚡)")
    group.add_argument("-s", "--special", action="store_true",
                       help="Filter only special deals (events + flash)")
    parser.add_argument(
        "-j", "--json", type=str, nargs="?", const="output.json",
        help="Output in JSON format (default: output.json)"
    )
    parser.add_argument(
        "-H", "--html", type=str, nargs="?", const="output.html",
        help="Output in HTML format (default: output.html)"
    )
    parser.add_argument(
        "--html-include-footer-navigation", action="store_true",
        help="Include footer navigation in HTML output. " +
        "Only relevant if --html is used." +
        "Note this is mostly only useful if deployed using the " +
        "default GitHub Actions workflow, which expects the HTML " +
        "file to be in certain places."
    )
    parser.add_argument(
        "-l", "--lang", type=str, choices=["de", "en"], default="de",
        help="Language (default: de)"
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="Verbosity level: -v for normal, -vv for debug"
    )

    # Parse the arguments
    args = parser.parse_args()

    # Ensure that --city and --all are mutually exclusive
    if args.city and args.all:
        print("Error: --city and --all cannot be used together.")
        return

    cities_data = {}

    # Decide filter mode to pass to scraper
    if args.events:
        filter_mode = 'events'
    elif args.flash:
        filter_mode = 'flash'
    elif args.special:
        filter_mode = 'special'
    else:
        filter_mode = None

    if args.city:
        # Fetch and print deals for a specific city
        print(f"Fetching deals for city: {args.city}...")
        verbosity = [Verbosity.SILENT, Verbosity.NORMAL, Verbosity.DEBUG][min(args.verbose, 2)]
        deals = fetch_deals_from_city(args.city, filter_mode, args.lang, verbosity=verbosity)
        cities_data[args.city] = deals
    elif args.all:
        # Fetch and print deals for all cities
        print("Fetching deals for all cities...")
        verbosity = [Verbosity.SILENT, Verbosity.NORMAL, Verbosity.DEBUG][min(args.verbose, 2)]
        cities = fetch_all_cities(args.lang)
        for city in cities:
            print(f"Fetching deals for city: {city['slug']}...")
            city_deals = fetch_deals_from_city(
                city['slug'], filter_mode, args.lang, verbosity=verbosity)
            cities_data[city['slug']] = city_deals

    if not cities_data:
        print(get_localized_strings(args.lang)['no_deals_found'])
        return

    # Print deals in text format (default)
    print_deals(cities_data, args.lang)

    # Output in JSON format if requested
    if args.json:
        print(f"Outputting deals to {args.json}...")
        output_json(cities_data, args.json)

    # Output in HTML format if requested
    if args.html:
        print(f"Outputting deals to {args.html}...")
        output_html(cities_data, args.lang, args.html, {
            "filter_mode": filter_mode,
            "include_footer_navigation": args.html_include_footer_navigation
        })

if __name__ == "__main__":
    main()
