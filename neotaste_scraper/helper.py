"""Helper functions for neotaste_scraper."""

# Helper: extract slug from a URL (last path component)
from typing import List, Optional
from neotaste_scraper.constants import BASE_URL, Deal


def get_slug_from_link(link: str) -> Optional[str]:
    """Extract restaurant slug from URL."""
    if not link:
        return None
    # Remove protocol and domain, get the last path component
    path = link.split('/')[-1]
    return path if path else None


def get_city_url(city_slug: str, lang: str = "de") -> str:
    """Construct full URL for the given city with the specified language."""
    return f"{BASE_URL}/{lang}/restaurants/{city_slug}"

def filter_deals(deals_in: List[Deal], mode: Optional[str]) -> List[Deal]:
    """Filter deals based on the specified mode/criteria."""
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
        return [d for d in deals_in if d.deal_type in ('flash', 'event', 'flash+event')]
    return deals_in
