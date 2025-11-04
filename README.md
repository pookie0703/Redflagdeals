# RedFlagDeals Amazon Pipeline

Automate the journey from a RedFlagDeals (RFD) Hot Deals thread to a social-ready Amazon.ca deal post. The project provides a modular scraping, normalization, and content generation pipeline with clean extension points for richer data sources and future automation.

## Features

- **Scraping**: Headless Playwright (preferred) with a graceful fallback to `requests` + `BeautifulSoup`.
- **Filtering**: Targets Amazon-related hot deals (title contains "Amazon" or includes amazon.ca links).
- **Normalization**: Extracts product names, prices, sellers, savings, forum popularity, and Amazon links.
- **Affiliate management**: Enforces the `thatmarcus-20` Amazon Associates tag while rejecting other tags.
- **Flags**: Highlights potential scams, generic listings, or suspicious discounts.
- **Social output**: Generates Instagram/TikTok-ready captions, hashtags, and optional 1080x1080 promo cards.
- **Batch-friendly CLI**: Deterministic command-line interface for automation.

## Quick Start

1. **Clone & set up environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Install Playwright browsers (optional but recommended)**

   ```bash
   playwright install
   ```

3. **Create a `.env` file (optional)**

   ```env
   RFD_BASE_URL=https://forums.redflagdeals.com/
   SCRAPE_MAX_PAGES=5
   RATE_MIN_MS=1000
   RATE_MAX_MS=3000
   AFFILIATE_TAG=thatmarcus-20
   DATA_DIR=data
   ASSETS_DIR=assets
   USE_PLAYWRIGHT=true
   GENERATE_CARD_IMAGES=true
   ```

## CLI Usage

```bash
# Scrape raw posts
python main.py scrape --max-posts 50 --days 2 --out data/raw.json

# Normalize & map to Amazon links with affiliate enforcement
python main.py process data/raw.json data/normalized.json

# Generate social captions and card images
python main.py social data/normalized.json data/social.csv --assets out/
```

Logs include timestamps and structured summaries. Commands exit with non-zero status codes on failure for easy automation.

## Respectful Scraping & Future Integrations

- The scraper identifies as a benign agent with rate limiting, jitter, and retries.
- All CSS selectors and URLs live in a central `ScrapeConfig` to simplify swaps to official feeds or APIs.
- For Instagram/TikTok publishing, this project **only** exports captions and image assets. Future integrations (e.g., Meta Graph API, TikTok Content Posting API) should live under an `integrations/` package with clear TODOs and proper credentials handling.
- Always follow platform terms of service and robots.txt directives.

## Repository Layout

- `config.py` – Loads `.env` configuration into typed settings.
- `main.py` – CLI entry point orchestrating scraping, processing, and social generation.
- `scraper.py` – Playwright + requests scraping for RFD Amazon threads.
- `parser.py` – Heuristics for product, pricing, and seller extraction.
- `amazon.py` – Affiliate tag enforcement and future Amazon mapping hooks.
- `flags.py` – Risk/quality heuristics.
- `social.py` – Caption & 1080x1080 PNG generation.
- `pipeline.py` – High-level stage orchestration.
- `models.py` – Typed dictionaries/dataclasses shared across modules.
- `utils.py` – Helpers for HTML cleaning, price parsing, JSON/CSV IO, retry/backoff, etc.
- `requirements.txt` – Project dependencies.

## Extension Ideas

- Hook into Amazon's Product Advertising API for richer product metadata and review flags.
- Parse additional RFD metadata (e.g., thread vote counts) or incorporate duplicate detection.
- Add persistence/database layers to track historical deals.
- Integrate scheduling or publishing tools once API access is approved.

## Testing & Mock Data

`parser.py` includes a simple `__main__` section demonstrating normalization on mocked posts. Expand with proper unit tests as you integrate with live data sources.

## Disclaimer

This project is provided for educational and automation purposes. Ensure compliance with RedFlagDeals' and Amazon's terms of service, and always respect user privacy and platform rate limits.
