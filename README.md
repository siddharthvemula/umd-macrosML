# UMD Dining Macro Tracker

A web app for University of Maryland students who eat at the dining halls. Every day it pulls the menu and the nutrition facts UMD publishes for each dish (from [nutrition.umd.edu](https://nutrition.umd.edu)). Students can then log a meal in a couple of taps instead of typing in macros by hand.

Students can also snap a photo of their plate, and the app guesses which of today's dishes are on it. A general calorie app has to recognize any food in the world. This one only has to choose from today's menu at one dining hall, which is a much smaller problem.

## Features

- Today's menu for **South Campus** and **Yahentamitsi**, grouped by meal (breakfast, brunch, lunch, dinner)
- Calories, protein, carbs and fat for every dish that has a UMD nutrition label
- One-tap logging with portion buttons (0.5x / 1x / 1.5x / 2x)
- A daily dashboard showing macro totals and the dishes you logged, with delete
- **Log from a photo:** take or upload a plate photo and get the top 5 guesses from today's menu (zero-shot CLIP), then log the right ones with the same portion buttons. If a dish was missed, search today's menu to add it. Each photo and the dishes logged from it are saved as training data for a future fine-tuned model.

## Tech stack

| Layer | Tech |
|---|---|
| Scraper | Python, `requests`, BeautifulSoup |
| Database | SQLite (plan: Postgres when deployed) |
| Backend | FastAPI, Pydantic, Uvicorn |
| Frontend | React 19 + Vite, plain CSS |
| Tests | pytest, Vitest + Testing Library |
| ML | PyTorch + Hugging Face CLIP (`openai/clip-vit-base-patch32`) |

## How it fits together

```
nutrition.umd.edu ──► Scraper ──► SQLite ──► FastAPI ──► React app
   (HTML pages)      (Python)    database    (JSON API)  (browser)
                                                │
                                          CLIP recognizer
                                          (plate photos)
```

1. **Scraper** (`scraper/`): `daily_scrape.py` downloads each hall's menu page and each dish's nutrition label. It waits 2 seconds between requests. Downloading (`fetcher.py`) and parsing (`menu_parser.py`, `label_parser.py`) are separate pieces, so the parsers are tested against saved copies of real pages.
2. **Database** (`db/database.py`): two main tables. `items` holds the nutrition for each dish, and `menu_entries` records what's served at each hall on each day. A dish is downloaded once and reused after that, so the database also works as the scraper's cache. Logged meals copy the dish's macros at the time you log it, so re-scraping later can't change past totals.
3. **API** (`api/`): `GET /halls`, `GET /menu`, `GET /items/{recipe_id}`, `POST/GET/DELETE /meals`, `GET /summary`, `POST /recognize`. "Today" is set to Eastern time, so the menu doesn't jump to tomorrow at 8pm.
4. **Recognizer** (`ml/`): `POST /recognize` scores a plate photo against the names of today's dishes that have nutrition, using CLIP (`recognizer.py`), and returns the top 5. CLIP loads on the first photo, not at server start. The photo is saved to `ml/training_photos/` (kept out of git). A dish logged from it is linked to it, and that link is the training label.
5. **React app** (`frontend/`): a hall picker shared by every screen, a photo logging screen, a menu screen and a Today dashboard. All backend calls go through one module (`src/api.js`).

The reasoning behind each design choice is in [DECISIONS.md](DECISIONS.md).

## Running it locally

You need Python 3.12+ and Node.js.

```bash
# 1. Backend setup
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Fill the database with today's menus (the first run takes ~10 min because of the polite delay)
.venv/bin/python -m scraper.daily_scrape          # or: --date 2026-10-14

# 3. Start the API (interactive docs at http://127.0.0.1:8000/docs)
.venv/bin/uvicorn api.main:app --reload

# 4. In a second terminal, start the frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

The Vite dev server forwards `/api/*` to FastAPI on port 8000, so you don't need any CORS setup. The first plate photo downloads CLIP (~600 MB) and takes a few seconds longer.

Measuring the recognizer:

```bash
.venv/bin/python -m ml.evaluate                  # hand-labeled photos in ml/eval_photos/
.venv/bin/python -m ml.export_training_data      # photos logged in the app -> CSV
.venv/bin/python -m ml.evaluate --training       # score CLIP on those
```

## Tests

**179 tests:** 132 backend tests (pytest) and 47 frontend tests (Vitest).

```bash
.venv/bin/python -m pytest          # scraper, database, API, recognizer, evaluation
cd frontend && npx vitest run       # React components and API client
```

The tests never contact the UMD site and never download CLIP. Scraper tests run on saved real pages in `tests/fixtures/`, API tests use a temporary database and photo folder, and recognizer tests use a fake scorer instead of the real model.

## Status / Roadmap

- [x] **Phase 1: Scraper.** Daily menus and nutrition labels saved to SQLite, for two dining halls
- [x] **Phase 2: Backend API.** Menu, nutrition, meal logging and daily totals
- [x] **Phase 3: Frontend.** Menu browsing, portion logging and a daily macro dashboard
- [x] **Phase 4: ML v1.** Upload a plate photo and get ranked guesses from today's menu using zero-shot CLIP. Logged dishes, including ones found with the menu search, are saved with the photo as training data. An evaluation script reports top-1, top-3 and recall@5 on hand-labeled Yahentamitsi photos (only a few so far, with more being collected).
- [ ] **Phase 5: ML v2.** Estimate portion size, using the standard-size dining hall plate as a scale reference, and fine-tune on users' corrections
- [ ] **Phase 6: Deploy.** Host the app, move to Postgres, get real UMD students using it
- [ ] **Phase 7: Expand.** The other UMD dining halls, then other schools

So far it runs locally only, for a single user. Accounts, scheduled daily scraping and hosting come in Phase 6.
