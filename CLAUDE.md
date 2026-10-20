# CLAUDE.md — UMD Dining Macro Tracker

## How to work with me
- **You write most of the code. My goal is to understand every part of it well enough to explain it in an internship interview.**
- How to work:
  1. **Plan before coding.** For any new piece, give me a short plan (files, functions, libraries, and *why*) and wait for my OK.
  2. **Small steps.** One feature or file at a time. Never build several layers in one go.
  3. **Explain after each step.** Walk me through what you wrote, step by step, with a concrete example of data flowing through it. Use analogies when a concept is new to me.
  4. **Quiz me briefly, only on code concepts.** After explaining, you may ask 1–2 short questions. If I say "skip the quiz," skip it. Don't push me to rewrite answers that are already roughly right.
  5. **Ask before installing** any new package or tool, and say in one line what it's for.
  6. **Keep `DECISIONS.md` updated:** one or two lines for every real choice (what we picked, what we didn't, why). This is my interview prep.
  7. **Commit and push automatically** after each step once the tests pass. Write the commit message yourself and push to GitHub; don't ask me to write it.
- Keep explanations concise and practical. Skip theory I don't need yet.

## Keep usage low
I'm on a shared usage limit with a busy college schedule, so be efficient:
- Keep explanations short. Lead with what matters; skip long recaps.
- Only read the files you need for the current task. Don't scan the whole project unless asked.
- One task per conversation. When a phase is done, tell me it's a good time to start a fresh conversation.
- Before a fresh start, make sure `DECISIONS.md` is up to date so nothing is lost.
- Don't re-explain things already covered in `DECISIONS.md`. Point to it instead.

## The project
A web app for UMD students who eat at the dining halls. It pulls each day's menu and published nutrition info from UMD Dining (nutrition.umd.edu) so students can log meals accurately without typing in macros by hand. Later, a student snaps a photo of their plate and the app estimates which items are on it and how much.

**Key ML insight:** a general calorie app has to recognize any food in the world. We only need to pick from the ~30 items on today's menu at one dining hall. Dining hall plates and bowls are a standard size, so they can serve as a scale reference for portion estimation.

## Stack (start simple, upgrade later)
- **Data / scraper:** Python (requests + BeautifulSoup, or whatever the site's structure actually needs; inspect it first)
- **Backend:** Python + FastAPI
- **Database:** SQLite to start (switch to Postgres when we deploy)
- **Frontend:** React (Vite) + plain CSS or Tailwind
- **ML:** Python (PyTorch / Hugging Face). Start with zero-shot image matching (e.g., CLIP) against today's menu item names, then fine-tune on our own labeled photos.

## Build phases
1. **Scraper:** daily menu + nutrition per item for one dining hall → saved to the database
2. **Backend API:** endpoints for today's menu, item nutrition, and logging a meal
3. **Frontend:** pick items from today's menu, set portion (0.5x / 1x / 1.5x / 2x), daily macro dashboard
4. **ML v1:** upload a plate photo → ranked guesses from today's menu → user confirms or corrects
5. **ML v2:** portion estimation using the plate as a scale reference; user corrections become training data
6. **Deploy + users:** host it, get UMD students using it, track usage numbers
7. **Expand:** the other UMD dining halls, then other schools

## Code style
- **Top of every file:** a short comment saying what the file is for and how it fits into the app.
- **Top of every function/method:** a docstring (Python) or JSDoc comment (React) explaining what it does, its inputs, what it returns, and a tiny example.
- **Inside functions:** short comments on the *why* behind anything that isn't obvious. Don't comment on what's obvious.
- **Names:** clear, descriptive names (`get_todays_menu`, not `gtm`). Keep functions small: one job each.
- **Python:** use type hints (e.g., `def get_menu(hall: str) -> list[MenuItem]:`).
- **Errors:** handle likely failures (website down, empty menu, bad photo) with a clear message instead of a crash.

## Testing
- Write tests **alongside** each feature, not at the end. Use `pytest` for Python and Vitest for React.
- For the scraper, save a sample copy of a real menu page and test against that, so tests don't hit the UMD site every time.
- Run the tests before saying a step is done, and show me the results.
- Explain each test in one plain sentence ("this checks that an empty menu returns an empty list instead of crashing").
- When something breaks, write a test that catches the bug first, then fix it.

## Rules
- Scrape politely: cache results, scrape at most once or twice a day, add a delay between requests, and check the site's terms/robots.txt before writing the scraper.
- Never commit API keys or secrets. Use a `.env` file and make sure it's in `.gitignore`.
- Keep the code readable over clever. Add short comments where the *why* isn't obvious.
- This is a personal project, not graded coursework.
