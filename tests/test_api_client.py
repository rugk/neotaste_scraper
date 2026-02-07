import types
from unittest.mock import patch

from neotaste_scraper.api_client import fetch_restaurants_from_api


class DummyResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_fetch_restaurants_paginates_and_extracts_deals():
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

    def fake_get(url, timeout=10):
        if "page=1" in url:
            return DummyResp(page1)
        if "page=2" in url:
            return DummyResp(page2)
        return DummyResp({"data": [], "meta": {"isLastPage": True}})

    with patch("requests.get", side_effect=fake_get):
        results = fetch_restaurants_from_api("berlin", lang="de")

    # Expect three restaurants extracted
    slugs = {r["link"].split("/")[-1] for r in results}
    assert slugs == {"a", "b", "c"}
    # Check deals presence
    assert any("D1" in r.get("deals", []) for r in results)
    assert any("D2" in r.get("deals", []) for r in results)
    assert any("D3" in r.get("deals", []) for r in results)
