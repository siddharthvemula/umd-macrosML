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
- **Step 5b: one hall picker for the whole app (`HallPicker`, state in `App`), not one per screen.** You pick the hall once and both the photo and menu screens follow it. `MenuView` now takes `hallId` as a prop instead of loading halls itself.
- **Switching halls resets screens with `key={hallId}`, not by clearing each state by hand.** A new key makes React start the component fresh, so no old menu, photo or guesses are left over. The old "reset in the change handler" code isn't needed anymore.
- **Logging logic moved into a custom hook (`useMealLogger`) plus a `LogBanner` component,** shared by the menu and photo screens instead of copying ~20 lines.
- **The photo is analyzed as soon as it's picked (no "Analyze" button), and changing the meal re-analyzes it.** Inputs are disabled while a request is in flight, so two answers can't race, which is simpler than a `stale` flag.
- **`<input type="file" accept="image/*" capture="environment">`, no camera library.** Phones open the back camera directly; desktops get a file picker. The preview uses a `blob:` URL that is revoked when replaced, so photos don't pile up in memory.
- **Scores shown as "% match", with "<1%" for tiny ones.** Softmax over ~200 dishes makes even right guesses small, and "0%" would look broken.
- **Not done: resizing photos in the browser before upload** (phone photos fit under the 10 MB limit; 413 covers the rest), and **"none of these are right"** (log from the menu for now; corrections are Step 6).
- **Step 6a: the training label is the log itself.** `/recognize` saves the photo and returns a `photo_id`. A dish logged with that `photo_id` (`meal_logs.photo_id`) means "this dish was on this plate". We didn't add a separate "confirm" request, because the browser would have to upload the photo twice. Deleting a wrong log removes its label too.
- **Image files on disk (`ml/training_photos/`, gitignored), with info in a `photos` table.** Databases are bad at big files. The original bytes are saved unchanged under a random UUID name, and the extension comes from the image's real format, not the uploaded filename. The file is written before the DB row, so a row never points to a missing file.
- **Only photos with guesses are saved.** With no menu there's nothing to label. Bad images are rejected before saving. Photos nobody logs from are kept for now (cleanup later).
- **`photo_id` is checked in the API (404 if unknown), not with a SQLite foreign key.** SQLite ignores foreign keys unless you turn them on per connection, and a clear 404 message is friendlier anyway.
- **Tiny migration (`ADDED_COLUMNS` + `ALTER TABLE`) instead of a migration tool like Alembic.** `CREATE TABLE IF NOT EXISTS` never changes an existing table, so the existing `macros.db` needed the new column added. One list entry per new column is enough until Postgres.
- **The photo folder is a dependency (`get_photo_dir`).** Tests write photos to a temp folder, never into the real training data.
- **Step 6b: `useMealLogger(onLogged, photoId)` passes the photo's id to `logMeal`.** The photo screen keeps `photo_id` from the newest recognize result and clears it when a new analysis starts, so a log can't be linked to an old photo. `logMeal` only adds `photo_id` to the JSON when it's set, so menu logs send the same body as before.
- **Step 6c: `python -m ml.export_training_data` rebuilds `ml/training_photos/labels.csv` from the DB each run** (same columns as the hand-made `labels.csv`). The DB is the source of truth, so a deleted log also disappears from the export. Photos nobody logged from are left out. A dish logged twice from one photo is one label. `notes` holds `photo_id N` so a row can be traced back to the DB.
- **`evaluate.py --training` scores CLIP on photos from real use,** reading the export and the training photo folder. These runs aren't added to `eval_history.csv`, so the history keeps comparing the same hand-labeled set. Meal "Any" photos export with an empty meal, and `load_candidates("")` then uses the whole day, which is what `/recognize` did.
- ~~Known gap: the evaluator's candidates included dishes without nutrition.~~ Fixed below.
- **Step 6d: "Not listed? Search today's menu" on the photo screen.** If CLIP misses a dish, you find it by name and log it. It goes through the same `handleLog`, so it's linked to the photo like any guess. A missed dish is the most useful training example, because it shows exactly where the model went wrong.
- **Search is a pure `searchMenu()` in `menu.js`, shown by a display-only `MenuSearch`;** `PhotoLogView` still makes all the API calls. It matches anywhere in the name, ignoring case. It only lists dishes with nutrition, from the chosen meal, not already in the guesses, each once, at most 8. The search runs in the browser on the menu from `getMenu`, with no new search endpoint, because one hall's day is only a few hundred dishes.
- **The menu loads on the first "Not listed?" click, not with every photo,** and stays loaded for later photos at the same hall (switching halls remounts the screen). There's no button when no photo was saved (no guesses), since a correction needs a photo to attach to.
- **Not done: marking a guess as wrong.** Right now only what you *log* is a label. A guess you skip isn't recorded as "not on the plate". That kind of negative label could come in Phase 5.
- **Fixed: `evaluate.py` now leaves out dishes without nutrition, the same as `/recognize`.** Before, it scored CLIP against a bigger list than the app ever shows. Test written first. Earlier `eval_history.csv` rows used the old, bigger lists, so the next run isn't an exact comparison with them.

## Deploy (Phase 6)
- **Hosting not chosen yet.** Compared Fly.io (~$13/mo for 2 GB, recommended), Render (~$25, and its cron can't reach the web server's disk), Railway (~$12–15, same disk problem), HF Spaces (free but files wiped on restart), Oracle/Hetzner VPS (cheap, but you run the server yourself). Checking GitHub Student Pack credits first.
- **Keep SQLite on the server's disk, not Postgres (yet).** One server and a few students is fine for SQLite. Postgres would mean a second paid service and rewriting all the SQL. Switch when we need several servers or many users.
- **Step 1: paths come from env vars (`config.py`: `MACROS_DB_PATH`, `MACROS_PHOTO_DIR`, `MACROS_FRONTEND_DIR`), defaulting to the project folders.** The old `DEFAULT_*` names now read from `config.py`, so the scraper, export and evaluate scripts all follow the same setting with no changes. Empty value = unset.
- **Production entry point `api/server.py` mounts the API at `/api` and the built React app at `/`,** instead of adding `/api` to every route. The frontend already calls `/api/...` (Vite proxy), so the same code works in both places, one origin, no CORS. Tests and local dev still use `api.main:app` directly.
- **`create_server()` is a factory (`uvicorn --factory`)** so importing it never crashes before `npm run build`; a missing build gives a clear `RuntimeError` instead of a cryptic StaticFiles error.
- **`GET /health` runs `SELECT 1`, never touches CLIP,** so a host can poll it every few seconds cheaply.
- **Step 2: one user per device, no accounts.** The browser makes a random UUID once (`device.js`, saved in localStorage) and `api.js` sends it as `X-Device-Id` on every request. `meal_logs` and `photos` got a `device_id` column. Not chosen: logins/passwords (too much for v1). Known limit: anyone who copies your ID sees your log, and clearing site data starts a fresh log.
- **`get_device_id` dependency checks the header is a real UUID (400 otherwise) and normalizes it to lowercase.** Junk never reaches the DB, and one ID can't be split by spelling. Menus/halls/items need no ID; they're the same for everyone.
- **`device_id` is a required keyword-only argument (`*, device_id`) on every meal/photo DB function.** Python then refuses a call that forgets it, so no query can accidentally return everyone's meals.
- **Another device's log or photo is a 404, not a 403.** Same answer as "doesn't exist", so you can't probe which ids other students have.
- **Logs from before devices existed (`device_id` NULL) are hidden from everyone,** but stay in the DB and in the training-data export.
- **Daily cap: 20 saved photos per device per campus day → 429,** checked before CLIP runs. Stops one device or a script from filling the server's disk. Only *saved* photos count (ones with guesses).
- **`crypto.getRandomValues` fallback for making the UUID,** because `crypto.randomUUID` only exists on https/localhost and a phone testing over home Wi-Fi uses plain http. If localStorage is blocked, the ID lasts until reload instead of failing every request.
- **Step 3: privacy notice gates the camera.** The photo screen shows `PhotoNotice` (what's saved, why, who sees it, how to delete) and the file input appears only after "I understand", remembered in localStorage (`privacy.js`). The full text is also in a footer `<details>` box, which needs no state. Blocked storage = notice shows again next visit (safer side).
- ~~The notice said photos are saved exactly as uploaded, location included.~~ Replaced by EXIF stripping below.
- **Deletion by email with an 8-character device code,** not a "delete my data" button yet. The code finds the rows without showing the full ID, which is what keeps a log private. `CONTACT_EMAIL` in `privacy.js` is a UMD Terpmail address, so it's clearly tied to the student project.
- **"Not affiliated with UMD Dining" + "nutrition may not be exact" disclaimer** in the notice, since other students will rely on it.
- **Photos are re-encoded without metadata before saving (`clean_photo`),** replacing Step 6a's "save the original bytes unchanged". Phone EXIF can hold GPS location and the phone model, which we shouldn't keep for other students. Pillow writes no EXIF/XMP unless asked; the color profile (ICC) is kept. Cost: JPEG/WebP are re-compressed at quality 95 (visually the same), PNG stays lossless, other formats become PNG.
- **The pixels are rotated by the EXIF Orientation tag (`ImageOps.exif_transpose`) before the tag is dropped.** Phones store pixels sideways plus a "turn 90 degrees" tag, so removing the tag alone would save the plate on its side, which would also hurt training. Photos saved before this change still have their EXIF (they're all Sid's own).
- **One-time `python -m db.claim_old_data <device code>` gives pre-device logs/photos (NULL `device_id`) to one device.** It takes the 8-character code from the Privacy footer and looks up the full ID in the DB, so the full ID never has to be shown in the app. The catch: that device must have logged something first. Only NULL rows are updated, in one transaction, so a second run does nothing and other students' rows are never touched. (At the time of writing, the local DB had 0 old logs/photos.)
- **Step 4: one host-agnostic `Dockerfile`, no Fly config yet,** so the same image runs on whichever host the Student Pack check picks. Docker runtime locally: OrbStack (lighter than Docker Desktop on Apple Silicon, same `docker` commands).
- **Two-stage build:** a `node:24-slim` stage runs `npm run build`, and only `frontend/dist` is copied into the `python:3.12-slim` stage. Node and `node_modules` never ship, and FastAPI (`api/server.py`) serves the React files, so the image has one process and one port (8080).
- **CPU-only torch from PyTorch's own index (`download.pytorch.org/whl/cpu`).** The default x86 torch from PyPI includes ~3 GB of NVIDIA libraries a CPU server can't use. Installed before `requirements.txt` so pip doesn't fetch torch twice.
- **CLIP is downloaded during `docker build`, then `HF_HUB_OFFLINE=1`.** The server starts without a ~600 MB download and can't break because Hugging Face is down. Cost: a bigger image (3.6 GB: CLIP 1.2 GB, torch 0.8 GB). transformers saves CLIP twice (`pytorch_model.bin` + a `model.safetensors` copy), which is a possible 600 MB trim later.
- **DB and photos live in a mounted `/data` folder (`MACROS_DB_PATH=/data/macros.db`, `MACROS_PHOTO_DIR=/data/photos`), never in the image.** They survive rebuilds, and anyone holding the image can't read students' meals or photos. `.dockerignore` keeps `.env`, `*.db` and photo folders out, and `tests/test_dockerignore.py` guards those lines.
- **Runs as root for now.** Most hosts' volumes (Fly's included) are root-owned, so a non-root user needs extra permission setup. Revisit once the host is picked.
- **`HEALTHCHECK` calls `/api/health` with Python's urllib,** because the slim image has no curl.
- **Lesson: a full disk corrupted Docker's build cache.** The build ran out of space while saving, and the next "cached" rebuild produced an image whose `.py` files were 0 bytes. Fix: `docker builder prune -af` + `docker build --no-cache`. Docker needs ~10 GB free.
- **Phone layout (checked at 390px): one `@media (max-width: 480px)` block in `index.css`, no CSS framework.** Dish rows stack (name → macros → buttons) instead of side by side, which squeezed names into ~120px; portion buttons become a full-width 4-column grid so they line up row to row. Desktop CSS is unchanged.
- **Every tappable thing is ≥44px tall on phones** (Apple's touch-target guideline). Portion buttons were 25px tall, Delete/"I understand" 21px. The file input's "Choose File" is sized via `::file-selector-button`, since the input itself can't be styled reliably.
- **How it was checked:** the app in a 390px-wide iframe in headless Chrome (headless Chrome has a minimum window width, so a plain 390px window isn't a real 390px viewport), with a script flagging any element past the right edge or under 32px tall. Throwaway, not committed.

## UI polish (frontend only, plain CSS)
- **Step 1: design tokens in `index.css`.** Every color, space, radius and font size is a CSS variable on `:root`; components only use the variables. Dark mode is one `@media (prefers-color-scheme: dark)` block that swaps just the color variables (it follows the phone/computer setting; no toggle). Not chosen: Tailwind or a UI kit (an extra build tool and new syntax to learn for one stylesheet), and a second dark stylesheet (two copies to keep in sync).
- **UMD red (`#e21833`) is the only accent; in dark mode the accent becomes a lighter red (`#ff4d61`)** because the real red is too dark to read as text on near-black. The header bar stays the real red in both themes, since it's the brand.
- **System font stack, not a web font** (San Francisco on iPhone, Segoe on Windows). It looks native and costs no download or extra request.
- **Layout: red header (title + the hall picker), then every screen is a `.card`.** The hall picker moved into the header because it controls the whole page. Meal names in the menu became `<h3>` under the card's `<h2>`, so headings stay in order for screen readers.
- **Screenshots for each step come from a throwaway Chrome DevTools-protocol script** (not committed). It sets a demo device ID, uses a real 390px viewport (`Emulation.setDeviceMetricsOverride`), forces light/dark, and holds `/recognize` answers 2.5s so loading states can be captured. It runs against a copy of the DB, so demo logs never touch real data.
