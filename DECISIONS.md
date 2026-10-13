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

## Fetcher
- **Fetching is kept separate from parsing.** `fetcher.py` only downloads HTML and the parsers only read it. Parsers get tested on saved pages, the fetcher on a fake network, and neither test needs the real site.
- **Fake session + fake clock instead of the `responses` library.** We pass fakes into `Fetcher` (dependency injection), so tests need no extra package and don't really sleep.
- **A class, not functions,** because it has to remember the HTTP session and the time of the last request, which the 2s polite delay needs.
- **Errors are wrapped in one `FetchError`.** Timeout, connection failure and 4xx/5xx all become one exception with a readable message, so callers catch one thing.
- **No file cache or retries yet.** The database will act as the cache, and at 1–2 scrapes a day failing loudly beats retrying.

## Database
- **Built-in `sqlite3` with plain SQL, not SQLAlchemy.** No install, and we see the real SQL. Revisit SQLAlchemy when we switch to Postgres at deploy.
- **Two tables: `items` (nutrition per dish) and `menu_entries` (what's served when/where).** A dish served daily stores its nutrition once, and `has_nutrition` lets the scraper skip re-fetching it. The database acts as the cache.
- **No foreign key from `menu_entries` to `items`; the menu keeps the dish name.** If one label download fails, the rest of the menu still saves, and `get_menu` shows that dish with `nutrition=None` (LEFT JOIN).
- **Re-scraping a day replaces it (delete + insert in one transaction), not merges.** Dishes UMD removes disappear, and a failed save leaves the old menu intact.
- **Upsert for nutrition (`ON CONFLICT ... DO UPDATE`).** Re-saving a dish updates it instead of erroring or duplicating.
- **Allergens stored as JSON text; dates as ISO text (`2026-10-12`).** SQLite has no list or date type, and ISO dates sort correctly as text.
- **Tests use `:memory:` databases.** Each test gets a fresh, empty DB with no files to clean up.
