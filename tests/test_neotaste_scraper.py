"""
Tests for CLI main Python file.
"""

from unittest.mock import patch, MagicMock

import pytest
from bs4 import BeautifulSoup

from neotaste_scraper.neotaste_scraper import (
    extract_deals_from_card,
    fetch_deals_from_city,
    fetch_all_cities
)
from neotaste_scraper.data_output import print_deals


def load_html(file_name):
    """Helper function to load HTML from a file"""
    with open(file_name, 'r', encoding='utf-8') as file:
        return file.read()


@pytest.mark.parametrize("html_file", [
    'tests/html_snippets/deal-per-city.html',
    'tests/html_snippets/deal-per-city-simplified.html',
    'tests/html_snippets/deal-per-city-new-badge.html',
    'tests/html_snippets/deal-per-city-flash.html'
])
def test_extract_deals_from_card(html_file):
    """Test extract_deals_from_card function with different HTML contents"""

    html_content = load_html(html_file)
    # Simulate the BeautifulSoup object as it would parse the HTML content
    soup = BeautifulSoup(html_content, "html.parser")

    # Find the first <a> tag (simulating the restaurant card)
    card = soup.find("a")

    # Call the function to extract deals (no filter)
    result = extract_deals_from_card(card, filter_mode=None)

    # Assert the result is not None
    assert result is not None
    assert result['restaurant'] == "PETER PANE Burgergrill & Bar - Friedrichstr."
    assert result['link'] == "https://neotaste.com/gb/restaurants/berlin/peter-pane-burgergrill-bar-friedrichstr"

    # Expectations per HTML fixture
    expected = {
        'tests/html_snippets/deal-per-city.html': ["🌟 €5 Wild Bert with Betel 🌟", "2for1 Aperitif"],
        'tests/html_snippets/deal-per-city-simplified.html': ["🌟 €5 Wild Bert with Betel 🌟", "2for1 Aperitif"],
        'tests/html_snippets/deal-per-city-new-badge.html': ["🌟 €5 Wild Bert with Betel 🌟", "2for1 Aperitif"],
        'tests/html_snippets/deal-per-city-flash.html': ["5€ Bowl", "10€ Rabatt", "GRATIS Getränk"]
    }

    exp = expected.get(html_file)
    assert exp is not None
    assert len(result['deals']) == len(exp)
    for deal in exp:
        assert deal in result['deals']


@pytest.mark.parametrize("html_file", [
    'tests/html_snippets/deal-per-city.html'
])
@patch('requests.get')
def test_fetch_deals_from_city(mock_get, html_file):
    """Test fetch_deals_from_city function with mocking requests"""
    # Mock the response from requests.get
    mock_response = MagicMock()
    html_content = load_html(html_file)
    mock_response.text = html_content
    mock_get.return_value = mock_response

    # Call the function under test (no filter)
    result = fetch_deals_from_city("sample-city", filter_mode=None)

    # Assert that the result contains 1 restaurant
    assert len(result) == 1
    assert result[0]['restaurant'] == "PETER PANE Burgergrill & Bar - Friedrichstr."
    assert "🌟 €5 Wild Bert with Betel 🌟" in result[0]['deals']
    assert "2for1 Aperitif" in result[0]['deals']


@pytest.mark.parametrize("html_file", [
    'tests/html_snippets/restaurant-overview-all-cities-simplified.html',
    'tests/html_snippets/restaurant-overview-all-cities.html'
])
@patch('requests.get')
def test_fetch_all_cities_falls_back_to_html(mock_get, html_file):
    """Test fetch_all_cities uses HTML fallback when the API is unavailable."""
    # Simulate API failure then HTML success
    html_content = load_html(html_file)
    api_response = MagicMock(status_code=500)
    api_response.text = ""
    api_response.json.side_effect = ValueError("Invalid JSON")

    html_response = MagicMock(status_code=200)
    html_response.text = html_content
    html_response.json.side_effect = ValueError("Should not be used")

    mock_get.side_effect = [api_response, html_response]

    cities = fetch_all_cities(lang="en")
    assert len(cities) >= 1
    assert cities[0]['name'] == "Sample City"
    assert cities[0]['slug'] == "sample-city"


def test_fetch_all_cities_falls_back_to_new_html_structure():
    """Test fetch_all_cities fallback parsing for the newer HTML city list structure."""
    html_content = load_html('tests/html_snippets/restaurant-overview-all-cities-new-fallback.html')
    api_response = MagicMock(status_code=500)
    api_response.text = ""
    api_response.json.side_effect = ValueError("Invalid JSON")

    html_response = MagicMock(status_code=200)
    html_response.text = html_content
    html_response.json.side_effect = ValueError("Should not be used")

    with patch('requests.get', side_effect=[api_response, html_response]):
        cities = fetch_all_cities(lang="de")

    assert cities == [
        {"slug": "aachen", "name": "Aachen"},
        {"slug": "wuerzburg", "name": "Würzburg"}
    ]


def test_fetch_all_cities_uses_api_endpoint():
    """Test fetch_all_cities discovers cities from the /web/cities API."""
    api_response = MagicMock(status_code=200)
    api_response.json.return_value = {
        "data": [
            {"slug": "sample-city", "name": "Sample City", "status": "ACTIVE"}
        ]
    }

    with patch('requests.get', return_value=api_response) as mock_get:
        cities = fetch_all_cities(lang="en")

    assert cities == [{"slug": "sample-city", "name": "Sample City"}]
    mock_get.assert_called_once_with("https://api.neotaste.com/web/cities", timeout=10)


@patch('builtins.print')
def test_print_deals(mock_print):
    """Test print_deals function (print check)"""
    cities_data = {
        "sample-city": [{"restaurant": "Sample Restaurant",
                         "deals": ["🌟 €5 Off"],
                         "link": "http://link.com"}]
    }
    print_deals(cities_data, lang="en")
    mock_print.assert_any_call("\nDeals in Sample-city: (1 restaurants)")
    mock_print.assert_any_call("  Sample Restaurant")
    mock_print.assert_any_call("   - 🌟 €5 Off")
    mock_print.assert_any_call("   → http://link.com")
