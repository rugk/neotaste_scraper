# Copilot instructions for neotaste_scraper

## Project summary
- Small CLI tool for scraping NeoTaste restaurant pages, extracting deal badges, and exporting results as text, JSON, or HTML.
- It is especially focused on special deals such as event-deals (🌟) and flash-deals (⚡).

## Key files
- [main.py](../main.py): CLI entry point and argument parsing for city selection, filters, and output formats.
- [neotaste_scraper/neotaste_scraper.py](../neotaste_scraper/neotaste_scraper.py): core scraping and parsing logic.
- [neotaste_scraper/api_client.py](../neotaste_scraper/api_client.py): shared HTTP client for JSON/text requests with browser-like headers, retries, and graceful error handling.
- [neotaste_scraper/data_output.py](../neotaste_scraper/data_output.py): text/JSON/HTML export helpers.
- [templates/deals_template.html](../templates/deals_template.html): Jinja2 template used for HTML export; keep its expected context keys stable.
- [tests/](../tests): unit tests and HTML fixtures; update them whenever parsing or export behavior changes.
- [.github/workflows/](../.github/workflows): CI and GitHub Pages export workflow.

## Architecture and data flow
- The CLI in [main.py](../main.py) collects city data, applies the selected deal filter, and then hands the results to the output layer.
- Scraping still relies on requests + BeautifulSoup for page parsing, but newer JSON/text fetches should go through [neotaste_scraper/api_client.py](../neotaste_scraper/api_client.py) instead of ad-hoc requests.
- The exported data shape is still a mapping of city slug to restaurant entries with the fields `restaurant`, `deals`, and `link`.

## Parsing and classification conventions
- Deal badges are discovered from the NeoTaste HTML structure, especially elements inside the restaurant card deals container.
- Prefer small helper functions and explicit typing when adding parsing logic.
- When introducing a new deal classification, keep the existing semantics and prefer the structured `Deal`/`deal_type` approach where available.

## Jinja/HTML template guidance
- HTML export is rendered through [templates/deals_template.html](../templates/deals_template.html) by [neotaste_scraper/data_output.py](../neotaste_scraper/data_output.py).
- The template expects a context with at least `base_url`, `lang`, `title`, `cities_data`, `filter_mode`, `include_footer_navigation`, and `strings`.
- If you change the template context or the HTML structure, update the template and the relevant tests together.
- Keep the footer navigation and hash-preserving behavior intact unless the workflow explicitly requires a change.

## API client guidance
- The refactored API client in [neotaste_scraper/api_client.py](../neotaste_scraper/api_client.py) centralizes retries, browser-like headers, and response normalization.
- Prefer `request_json()` and `request_text()` for new JSON/text fetches rather than creating new requests calls inline.
- If you change status handling, retries, or headers, update [tests/test_api_client.py](../tests/test_api_client.py) accordingly.

## Development workflow
- Run tests with `pytest`.
- For local export checks, use the commands from [README.md](../README.md) and the GitHub workflow files.
- Keep changes backward-compatible where practical, especially for CLI flags and the JSON/HTML output contract.
- Update [README.md](../README.md) and the workflow files when CLI behavior or export paths change.

## Do / Don’t
- Do: add or update HTML fixtures in [tests/html_snippets/](../tests/html_snippets) when parsing rules change.
- Do: add focused tests for parser or export changes.
- Don’t: change the output data structure without updating the output layer and tests.
- Don’t: introduce new network logic that bypasses the shared API client when JSON/text requests are involved.
