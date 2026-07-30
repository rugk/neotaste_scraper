"""
Tests for CLI main Python file.
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from bs4 import BeautifulSoup

from neotaste_scraper.constants import Verbosity
from neotaste_scraper.neotaste_scraper import (
    extract_deals_from_card,
    fetch_deals_from_city,
    fetch_all_cities
)
from neotaste_scraper.data_output import print_deals, output_json, output_html


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
    assert mock_get.call_count == 1
    assert mock_get.call_args.args == ("https://api.neotaste.com/web/cities",)
    assert mock_get.call_args.kwargs["timeout"] == 10
    assert "User-Agent" in mock_get.call_args.kwargs["headers"]
    assert mock_get.call_args.kwargs["headers"]["Referer"] == "https://neotaste.com/"


def test_fetch_all_cities_logs_verbose_details(capsys):
    """Test fetch_all_cities emits verbose progress details when enabled."""
    api_response = MagicMock(status_code=500)
    api_response.text = ""
    api_response.json.side_effect = ValueError("Invalid JSON")

    html_response = MagicMock(status_code=200)
    html_response.text = "<html><body><a href='/en/restaurants/sample-city'><span>Sample City</span></a></body></html>"
    html_response.json.side_effect = ValueError("Should not be used")

    with patch('requests.get', side_effect=[api_response, html_response]):
        fetch_all_cities(lang="en", verbosity=Verbosity.NORMAL)

    captured = capsys.readouterr()
    assert "Falling back to HTML city discovery" in captured.err
    assert "HTML city discovery found" in captured.err


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


def test_output_json_includes_generated_at(tmp_path):
    """JSON export should preserve the city data and include a human-friendly generation timestamp."""
    output_path = tmp_path / "output.json"
    cities_data = {
        "sample-city": [{"restaurant": "Sample Restaurant", "deals": ["🌟 €5 Off"], "link": "http://link.com"}]
    }

    output_json(cities_data, str(output_path), generated_at="2026-07-30T12:34:56+00:00", lang="en")

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["generated_at"] == "2026-07-30T12:34:56+00:00"
    assert payload["generated_at_display"] == "30 Jul 2026, 12:34:56 UTC"
    assert payload["sample-city"][0]["restaurant"] == "Sample Restaurant"


def test_output_html_includes_generated_at(tmp_path):
    """HTML export should render the generation timestamp inside the page."""
    output_path = tmp_path / "output.html"
    cities_data = {
        "sample-city": [{"restaurant": "Sample Restaurant", "deals": ["🌟 €5 Off"], "link": "http://link.com"}]
    }

    output_html(cities_data, lang="en", filename=str(output_path), generated_at="2026-07-30T12:34:56+00:00")

    html_content = output_path.read_text(encoding="utf-8")
    assert "Scraped at" in html_content
    assert "30 Jul 2026, 12:34:56 UTC" in html_content
