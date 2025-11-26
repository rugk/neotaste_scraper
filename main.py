"""
This tool allows you to scrape restaurant deal information from
NeoTaste's city-specific restaurant pages.
You can filter and retrieve restaurant deals, including 
”event-deals“ (marked with 🌟), and export the data to
different formats: text, JSON, or HTML.
"""

from neotaste_scraper.neotaste_scraper import main

if __name__ == "__main__":
    main()
