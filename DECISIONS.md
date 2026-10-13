# Decisions

One or two lines per real choice: what we picked, what we didn't, and why.

## Setup
- **Database: SQLite now, Postgres at deploy.** SQLite is a single file with no server to run, which suits local development. Postgres handles many users writing at once, which we'll need once the app is hosted.

## Scraper
- **Data source: nutrition.umd.edu HTML, not an API.** The site has no public API. Pages are server-rendered (ASP.NET), so the menu is already in the raw HTML. That means `requests` + BeautifulSoup is enough and we don't need a headless browser like Selenium.
- **Scraping rules:** There's no robots.txt (404), so no crawl rules are declared. We still follow our own: scrape at most 1–2 times a day, wait between requests, and cache everything in our database.
- **Python 3.12 (Homebrew) in a `.venv`, replacing the Mac's built-in 3.9** before starting the backend. We get newer syntax like `str | None`, and the urllib3/LibreSSL warning goes away. Always run things with `.venv/bin/python`.
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

## Daily scrape
- **One script (`scraper/daily_scrape.py`) wires fetcher → parsers → database.** Run by hand with `python -m scraper.daily_scrape [--date YYYY-MM-DD]`; scheduling it (cron) waits until deploy.
- **A failed menu page stops that hall *before* `save_menu`.** `save_menu` replaces the whole day, so saving nothing would wipe a good menu from an earlier run. Exit code 1 so a scheduler can notice.
- **A failed label is logged and skipped, not fatal.** The dish still appears with `nutrition=None`, and the next run retries it because `has_nutrition` is still False.
- **Each recipe ID's label is fetched once per run** (same dish at lunch and dinner). The first run is about 300 labels × 2s ≈ 10 min; later runs only fetch new dishes.
- **Summary counts saved rows, not parsed ones.** UMD lists some dishes at several stations in one meal (645 parsed → 533 saved for South Campus), and the DB keeps one per meal.
- **`HALLS` dict, South Campus = 16** (ID taken from the site's hall dropdown). Adding a hall later means adding one line.
- **"No nutrition published" is its own outcome (`NutritionNotAvailableError`), not a failure.** Same idea as "no menu" vs "broken page": UMD shows a "Nutritional Information is not available" box for some dishes (e.g. Maryland Crab Soup), and that's normal. A missing macro *without* that box still counts as a broken page. Detected by the `labelnotavailable` CSS class, not the text, because normal labels say "not available" in a footnote. It's a subclass of `LabelPageFormatError` so older `except` blocks still catch it.
- **No-data dishes aren't saved, so every run checks them again.** UMD may add the data later, and it costs one request per dish per day.

## Backend API
- **FastAPI, not Flask.** Type hints become request validation (a bad `?date=` is an automatic 422) and interactive docs at `/docs` for free.
- **Pydantic response models (`api/schemas.py`) separate from the DB dataclasses.** The database can change shape without breaking the frontend's JSON.
- **One SQLite connection per request via `Depends(get_db)`, with `check_same_thread=False`.** FastAPI may run the dependency and the endpoint on different threads; that's safe because no two requests share a connection.
- **"Today" = Eastern time (`get_today`), not the server clock.** A UTC server would show tomorrow's menu after 8pm on campus. It's also a dependency, so tests pin the date.
- **Tests swap dependencies (`app.dependency_overrides`) and use a temp DB *file*, not `:memory:`.** Every `:memory:` connection is a separate empty database, so the test's seeded data wouldn't be visible to the API's connection.
- **Hall IDs are slugs (`south_campus`) built from the scraper's `HALLS`.** No spaces in URLs, and adding a hall to the scraper adds it to the API.
- **`/menu` returns a flat item list (each with its `meal`), not grouped by meal.** Grouping is display logic for the frontend. Unknown hall → 404; a day with nothing stored → 200 with `items: []`.
