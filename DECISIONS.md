# Decisions

One or two lines per real choice: what we picked, what we didn't, and why.

## Setup
- **Database: SQLite now, Postgres at deploy.** SQLite is a single file with no server to run, which suits local development. Postgres handles many users writing at once, which we'll need once the app is hosted.

## Scraper
- **Data source: nutrition.umd.edu HTML, not an API.** The site has no public API. Pages are server-rendered (ASP.NET), so the menu is already in the raw HTML. That means `requests` + BeautifulSoup is enough and we don't need a headless browser like Selenium.
- **Scraping rules:** There's no robots.txt (404), so no crawl rules are declared. We still follow our own: scrape at most 1–2 times a day, wait between requests, and cache everything in our database.
- **Python 3.9 (the Mac's built-in) for now.** It's the only version installed. Upgrade before the backend so we get newer syntax like `str | None`.
- **"No menu" vs "broken page" are different outcomes.** The parser returns `[]` only when the page literally says "NO DATA AVAILABLE". Any other empty page raises `MenuPageFormatError`, so a UMD redesign can't be silently mistaken for "no menu posted".
- **Item IDs: UMD's `RecNumAndPort`** (e.g. `080603*4`) rather than item names. Names can repeat or change, but the ID is what the nutrition label URL needs.
- **Tests run on saved real pages** (`tests/fixtures/`): a full menu, a menu with dinner missing, and an empty day. They're fast, work offline, and don't load UMD's servers.

## Nutrition label parser
- **Fixed fields for nutrients, not a dict.** `NutritionLabel` has named fields (`protein_g`, `carbs_g`...) so the database and API know exactly which columns exist. The four macros are required; a label missing one raises `LabelPageFormatError`.
- **Match nutrients by label text, not table position.** If UMD reorders rows, "Protein 15g" is still found.
- **Precise calories (240.8 from the detail table), not the rounded big number (241).** Rounding errors would grow when we multiply by portions like 1.5x.
- **Blank values become `None`, not 0.** UMD leaves some cells empty (`Trans Fat - - - g`); "unknown" is different from "zero". The banana fixture covers this.
