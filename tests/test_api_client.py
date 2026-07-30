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

    def fake_get(url, timeout=10, headers=None, params=None):  # pylint: disable=unused-argument # (required by requests.get signature)
        if params and params.get("page") == 1:
            return DummyResp(page1)
        if params and params.get("page") == 2:
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

    def fake_get(url, timeout=10, headers=None, params=None):  # pylint: disable=unused-argument # (required by requests.get signature)
        if params and params.get("page") == 1:
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
    assert any(d.deal_type == "flash+event" for d in
               [d for r in results for d in r.get("deals", [])
                if d.text == event_deal["name"]])
    assert all(d.deal_type is None for d in
               [d for r in results for d in r.get("deals", [])
                if d.text == non_event_deal["name"]])
    assert all(d.deal_type is None for d in
               [d for r in results for d in r.get("deals", [])
                if d.text == deal_with_unknown_state["name"]])

def test_fetch_restaurants_with_api_fixture():
    """Test with real API response fixture (api-response-page.json)."""
    api_page = load_json('tests/json_snippets/api-response-page.json')

    # Mock returns the same fixture for all pages, then empty (simulating end)
    call_count = [0]

    def fake_get(url, timeout=10, headers=None, params=None):  # pylint: disable=unused-argument # (required by requests.get signature)
        call_count[0] += 1
        if params and params.get("page") == 1:
            return DummyResp(api_page)
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


def test_fetch_restaurants_uses_web_api_endpoint():
    """Ensure the API client uses the updated web endpoint and query params."""
    called = []

    def fake_get(url, timeout=10, headers=None, params=None):  # pylint: disable=unused-argument
        called.append((url, params))
        return DummyResp({"data": [], "meta": {"isLastPage": True}})

    with patch("neotaste_scraper.api_client.requests.get", side_effect=fake_get):
        fetch_restaurants_from_api("berlin", lang="de")

    assert called, "requests.get should be called"
    assert called[0][0] == "https://api.neotaste.com/web/restaurants/cities/berlin/restaurants"
    assert called[0][1] == {"page": 1, "citySlug": "berlin", "includeLoyalty": "true"}


def test_fetch_restaurants_matches_lowercase_city_response():
    """Uppercase city slug input should still match lowercase API response citySlug."""
    page1 = {
        "data": [
            {"slug": "members-friends", "name": "members & friends", "citySlug": "aachen", "deals": [{"name": "2for1 Main Item", "status": "available", "eventDeal": False}]}
        ],
        "meta": {"page": 1, "isLastPage": True}
    }

    def fake_get(url, timeout=10, headers=None, params=None):  # pylint: disable=unused-argument
        return DummyResp(page1)

    with patch("neotaste_scraper.api_client.requests.get", side_effect=fake_get):
        results = fetch_restaurants_from_api("Aachen", lang="de")

    assert len(results) == 1
    assert results[0]["restaurant"] == "members & friends"
    assert results[0]["link"].endswith("/aachen/members-friends")


def test_fetch_restaurants_uses_lowercase_api_slug():
    """The API client should normalize the city slug in the URL path."""
    called = []

    def fake_get(url, timeout=10, headers=None, params=None):  # pylint: disable=unused-argument
        called.append((url, params))
        return DummyResp({"data": [], "meta": {"isLastPage": True}})

    with patch("neotaste_scraper.api_client.requests.get", side_effect=fake_get):
        fetch_restaurants_from_api("Aachen", lang="de")

    assert called, "requests.get should be called"
    assert called[0][0] == "https://api.neotaste.com/web/restaurants/cities/aachen/restaurants"
    assert called[0][1] == {"page": 1, "citySlug": "Aachen", "includeLoyalty": "true"}
