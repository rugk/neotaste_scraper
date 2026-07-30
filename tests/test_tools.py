"""Small test and mock utilities for neotaste_scraper."""

import json

class DummyResp:  # pylint: disable=too-few-public-methods
    """A simple dummy response object to simulate requests.Response."""
    def __init__(self, data):
        self._data = data

    def json(self):
        """Return the JSON data."""
        return self._data

def load_json(file_name):
    """Helper to load JSON fixture."""
    with open(file_name, 'r', encoding='utf-8') as f:
        return json.load(f)
