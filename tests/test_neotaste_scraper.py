"""
Tests for CLI main Python file.
"""

from unittest.mock import patch, MagicMock

from bs4 import BeautifulSoup

from neotaste_scraper.neotaste_scraper import (
    extract_deals_from_card,
    fetch_deals_from_city,
    fetch_all_cities,
    print_deals,
    BASE_URL
)

# Sample HTML response to simulate BeautifulSoup parsing
DEAL_HTML_CONTENT = """
<a href="/gb/restaurants/berlin/peter-pane-burgergrill-bar-friedrichstr">
  <div class="flex flex-col">
    <h4 class="font-semibold text-[18px] whitespace-nowrap overflow-hidden text-ellipsis mt-3 mb-0.5 text-black">PETER PANE Burgergrill &amp; Bar - Friedrichstr.</h4>
    <div class="relative overflow-hidden" data-sentry-component="RestaurantCardDeals">
      <div class="flex flex-1 mt-2 items-center justify-start overflow-x-auto gap-2 whitespace-nowrap relative w-full min-h-4 min-w-full flex-grow-0 flex-shrink-0 scrollbar-hide">
        <div class="bg-neotaste rounded-full w-fit flex items-center justify-center px-3 font-semibold text-[12px] py-2 gap-x-1 whitespace-nowrap min-h-8 max-h-8" data-sentry-component="RestaurantDealPreview">
          <span class="mt-[1px]">🌟 €5 Wild Bert with Betel 🌟</span>
        </div>
        <div class="bg-neotaste rounded-full w-fit flex items-center justify-center px-3 font-semibold text-[12px] py-2 gap-x-1 whitespace-nowrap min-h-8 max-h-8" data-sentry-component="RestaurantDealPreview">
          <span class="mt-[1px]">2for1 Aperitif</span>
        </div>
      </div>
    </div>
  </div>
</a>
"""

def test_extract_deals_from_card():
    """Test extract_deals_from_card function"""
    # Simulate the BeautifulSoup object as it would parse the HTML content
    soup = BeautifulSoup(DEAL_HTML_CONTENT, "html.parser")

    # Find the first <a> tag (simulating the restaurant card)
    card = soup.find("a")

    # Call the function to extract deals
    result = extract_deals_from_card(card, filter_events=False)

    # Assert the result is not None
    assert result is not None
    assert result['restaurant'] == "PETER PANE Burgergrill & Bar - Friedrichstr."
    assert len(result['deals']) == 2  # Two deals: one with 🌟 and one without
    assert "🌟 €5 Wild Bert with Betel 🌟" in result['deals']
    assert "2for1 Aperitif" in result['deals']

@patch('requests.get')
def test_fetch_deals_from_city(mock_get):
    """Test fetch_deals_from_city function with mocking requests"""
    # Mock the response from requests.get
    mock_response = MagicMock()
    mock_response.text = DEAL_HTML_CONTENT
    mock_get.return_value = mock_response

    # Call the function under test
    result = fetch_deals_from_city("sample-city", filter_events=False)

    # Assert that the result contains 1 restaurant
    assert len(result) == 1
    assert result[0]['restaurant'] == "PETER PANE Burgergrill & Bar - Friedrichstr."
    assert "🌟 €5 Wild Bert with Betel 🌟" in result[0]['deals']
    assert "2for1 Aperitif" in result[0]['deals']

@patch('requests.get')
def test_fetch_all_cities(mock_get):
    """Test fetch_all_cities function with mocking requests"""
    # Mock the response from requests.get
    mock_response = MagicMock()
    mock_response.text = "<html><body><div data-sentry-component='CitiesList'><a href='/en/restaurants/sample-city'><span>Sample City</span></a></div></body></html>"
    mock_get.return_value = mock_response

    cities = fetch_all_cities(lang="en")
    assert len(cities) == 1
    assert cities[0]['name'] == "Sample City"
    assert cities[0]['slug'] == "sample-city"

@patch('builtins.print')
def test_print_deals(mock_print):
    """Test print_deals function (print check)"""
    cities_data = {
        "sample-city": [{"restaurant": "Sample Restaurant", "deals": ["🌟 €5 Off"], "link": "http://link.com"}]
    }
    print_deals(cities_data, lang="en")
    mock_print.assert_any_call("\nDeals in Sample-city:")
    mock_print.assert_any_call("  Sample Restaurant")
    mock_print.assert_any_call("   - 🌟 €5 Off")
    mock_print.assert_any_call("   → http://link.com")

