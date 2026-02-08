"""Tests for the API client scraper of neotaste_scraper."""

import json
from unittest.mock import patch

from neotaste_scraper.api_client import fetch_restaurants_from_api


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


def test_fetch_restaurants_paginates_and_extracts_deals():
    """Test pagination and deal extraction with mocked responses."""
    # page 1: two restaurants, not last
    page1 = {
        "data": [
            {"slug": "a", "name": "A", "citySlug": "berlin", "deals": [{"name": "D1", "status": "available"}]},
            {"slug": "b", "name": "B", "citySlug": "berlin", "deals": [{"name": "D2", "status": "available"}]}
        ],
        "meta": {"page": 1, "isLastPage": False}
    }

    # page 2: one restaurant, last page
    page2 = {
        "data": [
            {"slug": "c", "name": "C", "citySlug": "berlin", "deals": [{"name": "D3", "status": "available"}]}
        ],
        "meta": {"page": 2, "isLastPage": True}
    }

    def fake_get(url, timeout=10, headers=None):  # pylint: disable=unused-argument # (required by requests.get signature)
        if "page=1" in url:
            return DummyResp(page1)
        if "page=2" in url:
            return DummyResp(page2)
        return DummyResp({"data": [], "meta": {"isLastPage": True}})

    with patch("neotaste_scraper.api_client.requests.get", side_effect=fake_get):
        results = fetch_restaurants_from_api("berlin", lang="de")

    # Expect three restaurants extracted
    slugs = {r["link"].split("/")[-1] for r in results}
    assert slugs == {"a", "b", "c"}
    # Check deals presence
    assert any("D1" in [d.text for d in r.get("deals", [])] for r in results)
    assert any("D2" in [d.text for d in r.get("deals", [])] for r in results)
    assert any("D3" in [d.text for d in r.get("deals", [])] for r in results)


def test_fetch_restaurants_classifs_event_deals():
    """Test pagination and deal extraction with mocked responses."""
    # page 1: two restaurants, not last
    event_deal = {"name": "event-deal", "status": "available", "eventDeal": True}
    non_event_deal = {"name": "non-event-deal", "status": "available", "eventDeal": False}
    deal_with_unknown_state = {"name": "deal_with_unknown_state", "status": "available"}
    page1 = {
        "data": [
            {"slug": "a", "name": "A", "citySlug": "berlin", "deals": [event_deal]},
            {"slug": "b", "name": "B", "citySlug": "berlin", "deals": [non_event_deal]},
            {"slug": "c", "name": "C", "citySlug": "berlin", "deals": [deal_with_unknown_state]}
        ],
        "meta": {"page": 1, "isLastPage": True}
    }

    def fake_get(url, timeout=10, headers=None):  # pylint: disable=unused-argument # (required by requests.get signature)
        if "page=1" in url:
            return DummyResp(page1)
        return DummyResp({"data": [], "meta": {"isLastPage": True}})

    with patch("neotaste_scraper.api_client.requests.get", side_effect=fake_get):
        results = fetch_restaurants_from_api("berlin", lang="de")

    # Expect restaurants extracted
    slugs = {r["link"].split("/")[-1] for r in results}
    assert slugs == {"a", "b", "c"}
    # Check deals presence
    assert any(event_deal["name"] in [d.text for d in r.get("deals", [])] for r in results)
    assert any(non_event_deal["name"] in [d.text for d in r.get("deals", [])] for r in results)
    assert any(deal_with_unknown_state["name"] in [d.text for d in r.get("deals", [])] for r in results)
    # event deal is marked as such
    assert any(d.deal_type == "flash+event" for d in [d for r in results for d in r.get("deals", []) if d.text == event_deal["name"]])
    assert all(d.deal_type is None for d in [d for r in results for d in r.get("deals", []) if d.text == non_event_deal["name"]])
    assert all(d.deal_type is None for d in [d for r in results for d in r.get("deals", []) if d.text == deal_with_unknown_state["name"]])

def test_fetch_restaurants_with_api_fixture():
    """Test with real API response fixture (api-response-page.json)."""
    api_page = load_json('tests/json_snippets/api-response-page.json')

    # Mock returns the same fixture for all pages, then empty (simulating end)
    call_count = [0]

    def fake_get(url, timeout=10, headers=None):  # pylint: disable=unused-argument # (required by requests.get signature)
        call_count[0] += 1
        if "page=1" in url:
            return DummyResp(api_page)
        # All other pages return empty (end of pagination)
        return DummyResp({"data": [], "meta": {"isLastPage": True}})

    with patch("neotaste_scraper.api_client.requests.get", side_effect=fake_get):
        results = fetch_restaurants_from_api("berlin", lang="de")

    # Fixture has 14 restaurants (some omitted in display but present)
    assert len(results) >= 14
    # Check that we extracted deals
    assert all("deals" in r for r in results)
    assert all(len(r["deals"]) > 0 for r in results)
    # Verify some known restaurants from fixture
    names = {r["restaurant"] for r in results}
    assert "KONG" in names
    assert "Round & Edgy - Mitte" in names
    assert "PETER PANE Burgergrill & Bar - Friedrichstr." in names
