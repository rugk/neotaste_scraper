"""
Tests for CLI main Python file.
"""

from unittest.mock import patch, MagicMock
from neotaste_scraper import (
    extract_deals_from_card,
    fetch_deals_from_city,
    fetch_all_cities,
    print_deals,
    BASE_URL
)

def test_extract_deals_from_card():
    """Test extract_deals_from_card function"""
    # Sample HTML structure for a restaurant card (simulating BeautifulSoup object)
    sample_card = MagicMock()
    sample_card.get.return_value = "/restaurants/sample-restaurant"
    sample_card.select_one.return_value.get_text.return_value = "Sample Restaurant"

    # Sample deals
    sample_deals = MagicMock()
    sample_deals.select.return_value = [MagicMock(get_text=MagicMock(return_value="🌟 €5 Off"))]

    # Assuming no event filter
    result = extract_deals_from_card(sample_card, filter_events=False)
    assert result is not None
    assert result['restaurant'] == "Sample Restaurant"
    assert len(result['deals']) == 1
    assert "🌟 €5 Off" in result['deals']

@patch('requests.get')
def test_fetch_deals_from_city(mock_get):
    """Test fetch_deals_from_city function with mocking requests"""
    # Mock the response from requests.get
    mock_response = MagicMock()
    mock_response.text = "<html><body><a href='/restaurants/sample-restaurant'><h4>Sample Restaurant</h4></a></body></html>"
    mock_get.return_value = mock_response

    result = fetch_deals_from_city("sample-city", filter_events=False)
    assert len(result) == 1
    assert result[0]['restaurant'] == "Sample Restaurant"
    assert result[0]['link'] == f"{BASE_URL}/de/restaurants/sample-restaurant"

@patch('requests.get')
def test_fetch_all_cities(mock_get):
    """Test fetch_all_cities function with mocking requests"""
    # Mock the response from requests.get
    mock_response = MagicMock()
    mock_response.text = "<html><body><a href='/de/restaurants/sample-city'>Sample City</a></body></html>"
    mock_get.return_value = mock_response

    cities = fetch_all_cities(lang="de")
    assert len(cities) == 1
    assert cities[0]['name'] == "Sample City"
    assert cities[0]['slug'] == "sample-city"

@patch('builtins.print')
def test_print_deals(mock_print):
    """Test print_deals function (print check)"""
    cities_data = {
        "sample-city": [{"restaurant": "Sample Restaurant", "deals": ["🌟 €5 Off"], "link": "http://link.com"}]
    }
    print_deals(cities_data, lang="de")
    mock_print.assert_any_call("Deals in sample-city:")
    mock_print.assert_any_call("  Sample Restaurant")
    mock_print.assert_any_call("   - 🌟 €5 Off")
    mock_print.assert_any_call("   → http://link.com")
