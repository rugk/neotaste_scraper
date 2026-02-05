"""
Modle for outputting the scraping/parsing result.
"""

import json
from typing import Optional, TypedDict

from jinja2 import Environment, FileSystemLoader

from neotaste_scraper.neotaste_scraper import BASE_URL

# Localized Strings
localized_strings = {
    'de': {
        'deals': "Angebote",
        'deals_title': "NeoTaste Deals",
        'table_of_contents': "Inhaltsverzeichnis",
        'restaurant_link_text': "Mehr Informationen/Details zum Angebot",
        'view_restaurant': "Restaurant ansehen",
        'deals_in': "Deals in",
        'show_deals_in': "Zeige Deals in",
        'no_deals_found': "Keine Deals gefunden.",
        'city_page': "Seite der Stadt",
        'restaurant_details': "Mehr Details zum Restaurant",
        'link_source_code': "Quellcode auf GitHub",
        'back_to_toc': "Zurück zum Inhaltsverzeichnis",
        'no_filter': "Nicht filtern",
        'use_filter': "Nur spezielle anzeigen",
        'in_english': "In English"
    },
    'en': {
        'deals': "deals",
        'deals_title': "NeoTaste Deals",
        'table_of_contents': "Table of contents",
        'restaurant_link_text': "More Info/Details about the Offer",
        'view_restaurant': "View Restaurant",
        'deals_in': "Deals in",
        'show_deals_in': "Show deals in",
        'no_deals_found': "No deals found.",
        'city_page': "City Page",
        'restaurant_details': "Restaurant Details",
        'link_source_code': "Source code on GitHub",
        'back_to_toc': "Back to Table of Contents",
        'no_filter': "Do not filter",
        'use_filter': "Show only special deals",
        'in_german': "Auf Deutsch"
    }
}

def get_localized_strings(lang):
    """Return the localized strings for the given language."""
    return localized_strings.get(lang, localized_strings['de'])  # Default to German if not found

def print_deals(cities_data, lang="de"):
    """Print the formatted deals (text output)."""
    strings = get_localized_strings(lang)
    for city, city_deals in cities_data.items():
        print(f"\n{strings['deals_in']} {city.capitalize()}: ({len(city_deals)} {strings['deals']})")
        for r in city_deals:
            print(f"  {r['restaurant']}")
            for d in r['deals']:
                print(f"   - {d}")
            print(f"   → {r['link']}")


def output_json(cities_data, filename: str = "output.json"):
    """Output deals in JSON format, including city information."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(cities_data, f, ensure_ascii=False, indent=4)

class HtmlOptions(TypedDict, total=False):
    """Options for HTML output. This is used to pass additional options."""
    filter_mode: Optional[str]
    include_footer_navigation: Optional[bool]

def output_html(cities_data,
                lang="de",
                filename: str = "output.html",
                options: HtmlOptions = None):
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
        'filter_mode': options.get('filter_mode'),
        'include_footer_navigation': options.get('include_footer_navigation'),
        'strings': strings
    }

    # Render the template with data
    html_content = template.render(context)

    # Output HTML content to a file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
