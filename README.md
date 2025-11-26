# NeoTaste Scraper CLI Tool

This tool allows you to scrape restaurant deal information from NeoTaste's city-specific restaurant pages. You can filter and retrieve restaurant deals, including ”event-deals“ (marked with 🌟), and export the data to different formats: text, JSON, or HTML.

## Installation

To use the NeoTaste Scraper CLI tool, you'll need to have Python 3.7+ installed. Follow these steps to set up the environment:

### 1. Clone the repository (or download the files):

```bash
git clone https://github.com/rugk/neotaste_scraper.git
cd neotaste-fetcher
```

### 2. Set up a virtual environment:

Create a virtual environment for the project:

```bash
python3 -m venv venv
```

### 3. Install the required dependencies:

```bash
source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
pip install -r requirements.txt
```

---

## Usage

Once the tool is installed, you can run the script using the command line to fetch deals for a specific city or all cities. You can filter the deals based on events, and output the results in various formats (text, JSON, HTML).

### Command-line Arguments

* `-c`, `--city <city_slug>`
  Fetch deals for a specific city (e.g., `nuremberg`).

* `-a`, `--all`
  Fetch deals for all available cities on NeoTaste.

* `-e`, `--events`
  Filter only event deals, which are marked with `🌟` in their name.

* `-j`, `--json`
  Output the results in JSON format. This will generate an `output.json` file.

* `-H`, `--html`
  Output the results in HTML format. This will generate an `output.html` file.

* `-l`, `--lang <language>`
  Specify the language for output. Options are `de` (German) or `en` (English). Defaults to `de` (German).

For all CLI arguments, run it with `--help`.

### Examples

1. **Fetch deals for a specific city** (`nuremberg`), filter only event deals, and output in JSON format:

   ```bash
   python neotaste_scraper.py --city nuremberg --events --json
   ```

2. **Fetch deals for all cities**, filter only event deals, and output in HTML format:

   ```bash
   python neotaste_scraper.py --all --events --html
   ```

3. **Fetch deals for a specific city** (`hamburg`) and print them in text format (default):

   ```bash
   python neotaste_scraper.py --city hamburg
   ```

4. **Fetch deals for a specific city** (`munich`) in English and output in both JSON and HTML formats:

   ```bash
   python neotaste_scraper.py --city munich --lang en --json --html
   ```

---

## Example Output

### Text Output:

```
Deals in Nuremberg:
  Jojo‘s Indonesisches Resto & Bar
   - 🌟 €5 Main Course 🌟
   - 2für1 Aperitif
   → https://neotaste.com/de/restaurants/nuremberg/jojos-indonesisches-resto-bar

  PETER PANE Burgergrill & Bar - Königstraße
   - 🌟 5€ wilder Bert mit Betel 🌟
   - 2für1 Aperitif
   → https://neotaste.com/de/restaurants/nuremberg/peter-pane-burgergrill-bar-koenigstrasse
```

### JSON Output:

```json
{
    "nuremberg": [
        {
            "restaurant": "Jojo‘s Indonesisches Resto & Bar",
            "deals": [
                "🌟 €5 Main Course 🌟",
                "2für1 Aperitif"
            ],
            "link": "https://neotaste.com/de/restaurants/nuremberg/jojos-indonesisches-resto-bar"
        },
        {
            "restaurant": "PETER PANE Burgergrill & Bar - Königstraße",
            "deals": [
                "🌟 5€ wilder Bert mit Betel 🌟",
                "2für1 Aperitif"
            ],
            "link": "https://neotaste.com/de/restaurants/nuremberg/peter-pane-burgergrill-bar-koenigstrasse"
        }
    ]
}
```

### HTML Output:

```html
<html>
<head><title>NeoTaste Deals</title></head>
<body>
<h1>NeoTaste Deals</h1>

<h2><a id='nuremberg' href='https://neotaste.com/de/restaurants/nuremberg'>Deals in Nuremberg</a></h2>
<h3>Jojo‘s Indonesisches Resto & Bar</h3>
<ul>
  <li>🌟 €5 Main Course 🌟</li>
  <li>2für1 Aperitif</li>
</ul>
<a href='https://neotaste.com/de/restaurants/nuremberg/jojos-indonesisches-resto-bar'>Mehr Informationen/Details zum Angebot</a><br>

<h3>PETER PANE Burgergrill & Bar - Königstraße</h3>
<ul>
  <li>🌟 5€ wilder Bert mit Betel 🌟</li>
  <li>2für1 Aperitif</li>
</ul>
<a href='https://neotaste.com/de/restaurants/nuremberg/peter-pane-burgergrill-bar-koenigstrasse'>Mehr Informationen/Details zum Angebot</a><br>

</body>
</html>
```

---

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Disclosure

Especially for early-prototyping this has heavily [used ChatGPT](https://chatgpt.com/share/69277054-6f88-8009-90e4-c95d2346d031) for adding code.
