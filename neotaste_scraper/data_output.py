"""
Modle for outputting the scraping/parsing result.
"""

import json
from datetime import datetime, timezone
from typing import Optional, TypedDict

from jinja2 import Environment, FileSystemLoader

from neotaste_scraper.constants import BASE_URL
from neotaste_scraper.l10s import localized_strings

def get_localized_strings(lang):
    """Return the localized strings for the given language."""
    return localized_strings.get(lang, localized_strings['de'])  # Default to German if not found

def print_deals(cities_data, lang="de"):
    """Print the formatted deals (text output)."""
    strings = get_localized_strings(lang)
    for city, city_deals in cities_data.items():
        print(f"\n{strings['deals_in']} {city.capitalize()}: ({len(city_deals)} {strings['restaurants']})")
        for r in city_deals:
            print(f"  {r['restaurant']}")
            for d in r['deals']:
                print(f"   - {d}")
            print(f"   → {r['link']}")


def _resolve_generated_at(generated_at: Optional[str] = None) -> str:
    """Return a generation timestamp, creating one if none was provided."""
    if generated_at is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return generated_at


def _format_generated_at(value: str) -> str:
    """Format a UTC ISO timestamp as a human-friendly display string."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M:%S UTC")


def output_json(cities_data, filename: str = "output.json", generated_at: Optional[str] = None, lang: str = "de"):
    """Output deals in JSON format, including city information and a timestamp."""
    raw_generated_at = _resolve_generated_at(generated_at)
    payload = {
        "generated_at": raw_generated_at,
        "generated_at_display": _format_generated_at(raw_generated_at),
    }
    payload.update(cities_data)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


class HtmlOptions(TypedDict, total=False):
    """Options for HTML output. This is used to pass additional options."""
    filter_mode: Optional[str]
    include_footer_navigation: Optional[bool]

def output_html(cities_data,
                lang="de",
                filename: str = "output.html",
                options: HtmlOptions = None,
                generated_at: Optional[str] = None):
    """Output deals in simple HTML format, grouped by city, using Jinja2 for templating."""
    strings = get_localized_strings(lang)
    options = options or {}
    generated_at_value = _resolve_generated_at(generated_at)
    generated_at_display = _format_generated_at(generated_at_value)

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
        'generated_at': generated_at_value,
        'generated_at_display': generated_at_display,
        'strings': strings
    }

    # Render the template with data
    html_content = template.render(context)

    # Output HTML content to a file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
