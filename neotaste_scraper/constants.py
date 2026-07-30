"""Constants and data structures for neotaste_scraper."""

# Constants
from dataclasses import dataclass
from enum import Enum


API_BASE = "https://api.neotaste.com"
BASE_URL = "https://neotaste.com"


@dataclass
class Deal:
    """A parsed deal from a restaurant card."""
    text: str
    component: str
    deal_type: str  # 'flash', 'event', 'flash+event', 'other'


class Verbosity(Enum):
    """Verbosity levels for debug output."""
    SILENT = 0
    NORMAL = 1  # -v: chunk summaries and limited previews
    DEBUG = 2   # -vv: full JSON dumps for all chunks
