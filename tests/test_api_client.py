"""Tests for the API client scraper of neotaste_scraper."""

from unittest.mock import patch

from neotaste_scraper.api_client import request_json
from tests.test_tools import DummyResp


def test_request_json_uses_browser_headers_and_params():
    """A shared request helper should add browser-like headers and return parsed JSON."""
    calls = []

    def fake_get(url, timeout=10, headers=None, params=None):
        calls.append((url, timeout, headers, params))
        return DummyResp({"data": [{"slug": "sample-city"}]})

    with patch("neotaste_scraper.api_client.requests.get", side_effect=fake_get):
        payload = request_json("https://api.neotaste.com/web/cities", params={"page": 1}, verbosity=1)

    assert payload == {"data": [{"slug": "sample-city"}]}
    assert len(calls) == 1
    assert calls[0][0] == "https://api.neotaste.com/web/cities"
    assert calls[0][1] == 10
    assert calls[0][3] == {"page": 1}
    assert "User-Agent" in calls[0][2]
