
# Helper: extract slug from a URL (last path component)
from typing import Optional
from neotaste_scraper.constants import BASE_URL


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