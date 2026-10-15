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
- **Added Yahentamitsi = 19** (same dropdown). Hall name kept short ("Yahentamitsi", not "Yahentamitsi Dining Hall") so its API slug is `yahentamitsi`.
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
- **Kept `httpx` for `TestClient`, didn't switch to `httpx2` yet.** Starlette shows a deprecation warning, but the tests work fine; we'll switch when it actually breaks or during a dependency upgrade.
- **`GET /items/{recipe_id}` returns 404 when we have no label,** whether the ID is wrong or the dish's label just hasn't been scraped. The frontend treats both the same ("no nutrition info").
- **Shared API test fixtures live in `tests/conftest.py`,** which pytest loads automatically, so each API test file gets the same `client` (temp DB + fixed date) without copying it.
- **Meal logs copy the dish's macros at log time (`meal_logs` table), per serving, plus `servings`.** A log is history: re-scraping a dish must not change yesterday's totals. Storing per-serving + servings (not pre-multiplied totals) keeps the raw facts, so "edit servings" can be added later. Only the 4 macros are copied; the full label stays in `items`.
- **Can't log a dish with no stored nutrition (404).** We can't count macros we don't know.
- **Daily totals are summed in SQL (`SUM(calories * servings)`, `COALESCE` → 0 for empty days),** not in Python. The database does the adding, and it's one query however many meals there are.
- **Servings: any number in (0, 5], validated by Pydantic `Field(gt=0, le=5)`.** The 0.5/1/1.5/2 buttons are a frontend choice; ML v2 will estimate portions like 1.3.
- **Round to 1 decimal only in the API's output (`round_macro`).** The DB keeps exact values so rounding errors don't add up; the JSON shows `164.7` instead of `164.70000000000002`.
- **`POST` returns 201 Created, `DELETE` returns 204 No Content,** the standard HTTP codes for "made something" and "done, nothing to send back".
- **`POST /meals` takes an optional `date`** so last night's dinner can be logged after midnight. Left out for now: `user_id` (single user until deploy), a breakfast/lunch/dinner field, and editing a log (delete + re-log).

## Frontend
- **React + Vite in `frontend/`, plain JavaScript (not TypeScript), plain CSS (not Tailwind).** Fewer new things to learn at once; both can be added later.
- **Vite dev proxy (`/api/*` → FastAPI on :8000), not CORS.** The browser sees one origin, so the backend needed no changes. At deploy we'll serve both from one domain or add CORS then.
- **Every backend call lives in `src/api.js`.** Components never build URLs; tests fake one module. All failures become one `ApiError` (message + status), same idea as the scraper's `FetchError`. FastAPI's `detail` string becomes the message; "can't reach the server" has `status: null`.
- **Tests: Vitest + Testing Library + jsdom,** plus `jest-dom` (matchers like `toBeInTheDocument`) and `user-event` (realistic clicks/typing). API tests stub the global `fetch` with `vi.stubGlobal`, so no backend runs.
- **Menu screen split into `MenuView` (fetches, holds state) and `MenuList` (display only), with grouping in a pure `groupByMeal()` (`menu.js`).** The pure function is tested without React; the display component can't get loading logic tangled into it.
- **Meals sorted Breakfast → Brunch → Lunch → Dinner, unknown meal names last.** The API's order isn't guaranteed to be the day's order.
- **Hall switch ignores late answers (a `stale` flag in the effect cleanup).** Otherwise a slow South Campus response arriving after you picked Yahentamitsi would show the wrong menu.
- **State is reset in the dropdown's change handler, not inside the effect** (the linter's `set-state-in-effect` rule): React suggests updating state from the event that caused the change, which avoids an extra render.
- **Component tests mock the whole `api.js` with `vi.mock`,** keeping the real `ApiError`. `vi.resetAllMocks()` before each test so fake answers can't leak between tests.
- **One click logs a dish: tapping a portion button (0.5x/1x/1.5x/2x) logs right away,** no separate "Log" button. Fewer taps in a dining hall line; a mistake is fixed by deleting it (step 4 dashboard).
- **Logging lives in `MenuView` (`handleLog`); `MenuList`/`PortionButtons` just call `onLog`.** One component talks to the API; the rest only display. This is "lifting state up" in React.
- **Buttons are disabled while that dish's request is in flight (`loggingId`),** so a double-click can't log twice. Dishes with no nutrition get no buttons (the API would 404 anyway).
- **The confirmation uses the calories the server sent back,** not ones computed in the browser, so it shows exactly what was saved.
- **Dashboard split like the menu: `DashboardView` (fetches, deletes) + display-only `MacroTotals` and `LoggedMealsList`.** Summary and logs load together with `Promise.all`, one wait instead of two.
- **Screens stay in sync through a counter in `App` (`logCount` → `refreshKey`), not by moving all meal data into `App`.** The menu only needs to say "something changed"; the dashboard reloads itself. `MenuView` calls `onLogged` only after a *successful* log.
- **After a delete, totals are reloaded from the server, not subtracted in the browser.** Same rule as the log banner: show what the server has, no rounding drift.
- **Totals shown as whole numbers** (the API keeps 1 decimal). A tenth of a gram is noise on a daily total.
- **No daily goals/progress bars and no chart library yet.** There's nowhere to store goals in the backend; four number tiles need no install.

## ML v1 (Phase 4, planned)
- **Zero-shot CLIP (`openai/clip-vit-base-patch32` via Hugging Face `transformers`), not training our own model first.** We only rank ~30 of today's dishes by image–text similarity, so a pretrained model needs no labeled training data to start.
- **Evaluation photos from Yahentamitsi, not South Campus.** 15–20 labeled plates (`ml/eval_photos/` + `labels.csv`, photos gitignored) measure top-1/top-3 accuracy before we build on it.
- **The model is passed into the recognizer (dependency injection, like `Fetcher`),** so tests use a fake model and never download 600 MB.
- **Saving confirmed photo + dish (step 6) is part of Phase 4, not Phase 5,** so training data for fine-tuning starts piling up from the first real use.
- **Known v1 limit:** CLIP sees the whole plate as one image, so multi-dish plates are handled by the user picking several of the top 5 guesses.
- **Eval labels in `ml/eval_photos/labels.csv`: one row per photo (`photo,date,hall,meal,dishes,notes`), dishes as exact menu names joined by `;`.** You can't see recipe IDs in a dining hall, but you can see names in our app. The eval script will match names to that day's stored menu. `;` because some dish names contain commas. Photos stay gitignored (big, personal); only the labels file is committed.
- **The candidate list is ~250 dishes per meal at Yahentamitsi, not ~30** (it includes salad bar toppings and condiments like Butter). The eval will tell us whether we need to filter that list down.
- **Steps in plan order: evaluate (Step 3) before the API/UI (Steps 4–6).** Considered moving it last, but measuring CLIP first tells us whether the rest is worth building on.
- **Label rules:** a dish that isn't on that day's menu stays out of `dishes` and goes in `notes` as `not on menu: ...` (we can't score a guess that was never a candidate). A photo whose menu we don't have or can't match gets notes starting `menu unavailable`, and the eval skips it.
- **Lettuce etc. labeled by what's on the plate** ("Shredded Lettuce", not "Chopped"), even when several stations serve a similar item. Near-duplicate names are a known source of "wrong" top-1 guesses.
- **Menus scraped ahead (14 days), but they're UMD's plan, not what was served.** Re-scrape on the day (the daily run replaces the day) so eval photos match the final menu.
- **Step 1: torch, transformers, Pillow, python-multipart pinned in `requirements.txt`.** `ml/spike.py` is a throwaway try-out. First result: on the taco-bar plate, CLIP's #1 guess was right and 5 of its top 10 were on the plate (209 candidates). On the pita plate only the red onion (#1) was right, since the pita/tzatziki details are hard to see.
- **Step 2: `ml/recognizer.py` injects our own `ImageTextScorer` (a `Protocol` with one `score()` method), not the Hugging Face model.** Faking HF's model would mean copying its tensor outputs; a fake `score()` is 3 lines. `ClipScorer` is the real one and loads CLIP once.
- **The recognizer takes plain dish names, not DB rows.** It stays independent of SQLite; the eval script and API fetch the menu and map names back to recipe IDs. Duplicate names are scored once.
- **Softmax in `rank_menu_items`, not in the scorer,** so the fake can return simple numbers and the probability math is still tested. Scores sum to 1 over *all* candidates, not just the top 5.
- **The prompt template is a parameter (`{name}` slot)** so Step 3 can compare wordings without code changes.
- **`load_photo` raises `BadPhotoError` for empty, non-image, or truncated bytes** (it decodes the pixels right away), so Step 4 can return a 400 instead of crashing inside the model.
- **No automated test loads real CLIP** (600 MB). Step 3's eval on real photos is the real check for `ClipScorer`.
- **Step 3 metrics: top-1 hit (is the #1 guess on the plate), top-3 hit (any of the top 3 on the plate), recall@5 (share of the plate's dishes found in the top 5).** A plate has several dishes, so plain "accuracy" doesn't fit; recall@5 matches the UI, where you pick from 5 guesses.
- **Label names not on the stored menu are warned about (with a "did you mean" from `difflib`) and left out of scoring,** not counted as misses. Otherwise a typo in labels.csv would look like a model failure. Photos with no menu, a missing file, or no matching dishes are skipped with a printed reason.
- **Each run appends one row per wording to `ml/eval_history.csv` (committed),** so re-runs with more photos show a trend.
- **First run (n=3, 2026-10-15):** `"a photo of {name}, a dining hall dish"` was best: top-1 67%, top-3 67%, recall@5 33%. `"{name}"`: 33/67/21. `"a photo of {name}"`: 0/67/22. Too few photos to trust; one photo moves a score 33 points. Plate 02 (fried chicken thighs, fries, shrimp pasta) only got 1 hit in the top 5. Long sandwich and pasta names in the top 5 suggest the ~200-dish candidate list needs filtering.
- **Step 4: `POST /recognize` is a multipart upload (`photo` file + `hall` + optional `meal` form fields), not JSON with base64.** That's how browsers send files natively, and base64 makes the upload ~33% bigger. Always uses today's menu (`get_today`).
- **CLIP loads on the first photo (`get_scorer`, cached with `lru_cache`), not at server start.** The server starts instantly and the menu/meal endpoints never pay for a 600 MB model. It's a dependency, so tests swap in a fake scorer like they swap the DB.
- **Only dishes with nutrition are candidates,** since a guess you can't log (`POST /meals` → 404) wastes a top-5 slot. Each guess includes `recipe_id` + nutrition so the UI can log it with no extra request.
- **Errors: 400 not an image, 413 over 10 MB, 404 unknown hall; no menu (or no dishes for that meal) → 200 with `guesses: []`,** same rule as `/menu`. `meal` matches case-insensitively.
- **Plain `def` endpoint, not `async def`.** CLIP is slow CPU work; FastAPI runs plain `def` on a worker thread, so one photo doesn't block other requests.
- **Not yet: filtering the ~200 candidates.** That's an ML decision for when there are more eval photos. Real-CLIP check on plate 03: 4 of the top 5 were on the plate.
- **Step 5a: `recognizePhoto()` in `api.js` sends `FormData` and doesn't set `Content-Type`.** The browser has to write the multipart header itself, because it includes a random "boundary" string. An empty `meal` is left out, so the backend uses the whole day's menu.
