# The FastAPI backend: serves the menus and nutrition the scraper saved to the
# database, lets a student log meals and see their daily totals, and guesses which
# dishes are on a plate photo (POST /recognize), saving each photo so the dishes logged
# from it become ML training data. Meal logs and photos belong to a device (the
# X-Device-Id header, see api/deps.py), so each student sees only their own. Run it locally with
#   .venv/bin/uvicorn api.main:app --reload
# then open http://127.0.0.1:8000/docs to try the endpoints in the browser.

import sqlite3
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile

from api.deps import get_db, get_device_id, get_photo_dir, get_scorer, get_today
from api.schemas import (
    DailySummaryOut, GuessOut, HallOut, MealLogIn, MealLogOut, MenuItemOut, MenuOut,
    NutritionOut, RecognizeOut,
)
from db.database import (
    MealLog, count_photos, delete_meal_log, get_daily_totals, get_meal_logs, get_menu, get_nutrition, log_meal,
    photo_exists, save_photo,
)
from ml.candidates import is_candidate
from ml.photo_store import save_photo_file
from ml.recognizer import BadPhotoError, ImageTextScorer, load_photo, rank_menu_items, suggest_servings
from scraper.daily_scrape import HALLS

app = FastAPI(title="UMD Dining Macro Tracker")


def hall_id(hall_name: str) -> str:
    """Turn a hall's display name into its URL-friendly ID.

    Example:
        hall_id("South Campus")  # -> "south_campus"
    """
    return hall_name.lower().replace(" ", "_")


# Built once from the scraper's HALLS, so adding a hall there adds it to the API too.
HALL_NAMES_BY_ID: dict[str, str] = {hall_id(name): name for name in HALLS}


@app.get("/health")
def health_check(conn: sqlite3.Connection = Depends(get_db)) -> dict[str, str]:
    """Tell a hosting service the server is up and can reach its database.

    Hosts call this every few seconds and restart the server if it stops answering.
    It runs a trivial query instead of loading CLIP, so it stays fast.

    Example:
        GET /health  # -> {"status": "ok"}
    """
    conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/halls")
def list_halls() -> list[HallOut]:
    """List the dining halls we have menus for.

    Example response: [{"id": "south_campus", "name": "South Campus"}]
    """
    return [HallOut(id=id_, name=name) for id_, name in HALL_NAMES_BY_ID.items()]


# Phone photos are usually 2-5 MB; anything far bigger is probably not a plate photo.
MAX_PHOTO_BYTES = 10 * 1024 * 1024
# A few meals a day plus retakes is well under this. The cap stops one device (or a
# script) from filling the server's disk with photos.
MAX_PHOTOS_PER_DAY = 20


def get_hall_name(hall: str) -> str:
    """Look up a hall ID's display name, or raise a 404 for an unknown hall.

    Example:
        get_hall_name("south_campus")  # -> "South Campus"
    """
    hall_name = HALL_NAMES_BY_ID.get(hall)
    if hall_name is None:
        raise HTTPException(status_code=404, detail=f"Unknown hall '{hall}'. See /halls for valid IDs.")
    return hall_name


@app.get("/menu")
def read_menu(
    hall: str,
    # alias: the URL says ?date=..., but naming the variable `date` would hide the date type.
    menu_date: date | None = Query(None, alias="date"),
    conn: sqlite3.Connection = Depends(get_db),
    today: date = Depends(get_today),
) -> MenuOut:
    """Get one hall's menu for a day, with each dish's nutrition.

    Query params:
        hall: Hall ID from /halls, e.g. "south_campus".
        date: Optional, e.g. "2026-10-12". Defaults to today (Eastern time).

    Returns:
        The menu; items is [] if nothing is stored for that day.
        404 if the hall is unknown, 422 (automatic) if the date isn't a valid date.

    Example:
        GET /menu?hall=south_campus&date=2026-10-12
    """
    day = menu_date or today
    rows = get_menu(conn, day, get_hall_name(hall))
    return MenuOut(hall=hall, date=day, items=[MenuItemOut.model_validate(row) for row in rows])


@app.get("/items/{recipe_id}")
def read_item_nutrition(recipe_id: str, conn: sqlite3.Connection = Depends(get_db)) -> NutritionOut:
    """Get one dish's nutrition per serving by its UMD recipe ID.

    Returns:
        The nutrition. 404 if we haven't scraped this dish's label (or the ID is wrong).

    Example:
        GET /items/080603*4  # -> {"name": "Fresh Chicken Burger", "calories": 240.8, ...}
    """
    label = get_nutrition(conn, recipe_id)
    if label is None:
        raise HTTPException(status_code=404, detail=f"No nutrition stored for recipe '{recipe_id}'.")
    return NutritionOut.model_validate(label)


# A plain `def`, not `async def`: CLIP is slow CPU work, and FastAPI runs plain `def`
# endpoints on a worker thread, so one photo doesn't freeze the server for other requests.
@app.post("/recognize")
def recognize_photo(
    photo: UploadFile = File(...),
    hall: str = Form(...),
    meal: str | None = Form(None),
    conn: sqlite3.Connection = Depends(get_db),
    today: date = Depends(get_today),
    scorer: ImageTextScorer = Depends(get_scorer),
    photo_dir: Path = Depends(get_photo_dir),
    device_id: str = Depends(get_device_id),
) -> RecognizeOut:
    """Guess which of today's dishes are on a plate photo.

    Form fields (multipart upload, like a file input in an HTML form):
        photo: the image file (JPEG/PNG/...).
        hall: hall ID from /halls, e.g. "yahentamitsi".
        meal: optional, e.g. "Lunch". Without it, every dish served today is a candidate.

    Returns:
        Top 5 guesses, best first, each with nutrition so it can be logged right away,
        plus photo_id: the photo is saved, and POST /meals with that photo_id links a
        logged dish to it as a training label.
        guesses is [] (and photo_id null, nothing saved) if no menu is stored for today
        (or for that meal).
        400 for a file that isn't an image (or no X-Device-Id), 413 if it's over 10 MB,
        404 for an unknown hall, 429 if this device already saved 20 photos today.

    Example:
        POST /recognize  photo=plate.jpg, hall=yahentamitsi, meal=Lunch
        # -> {"guesses": [{"recipe_id": "...", "name": "Fried Chicken Thigh", "score": 0.31, ...}]}
    """
    hall_name = get_hall_name(hall)
    # Checked before running CLIP, so a device over the cap costs the server almost nothing.
    if count_photos(conn, today, device_id=device_id) >= MAX_PHOTOS_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=f"Daily photo limit reached ({MAX_PHOTOS_PER_DAY}). Log from the menu instead.",
        )

    data = photo.file.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photo is too large (max 10 MB).")
    try:
        image = load_photo(data)
    except BadPhotoError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    # is_candidate drops dishes with no nutrition (can't be logged) and condiments/Salad
    # Bar toppings (they crowd real dishes out of the top 5). Case-insensitive meal match.
    candidates = [
        row for row in get_menu(conn, today, hall_name)
        if is_candidate(row) and (meal is None or row.meal.lower() == meal.lower())
    ]
    # The recognizer works on names; this maps each guessed name back to its dish.
    rows_by_name = {}
    for row in candidates:
        rows_by_name.setdefault(row.name, row)

    guesses = rank_menu_items(image, list(rows_by_name), scorer)
    # Only the 5 guesses get a portion size, not all ~130 candidates (3 prompts each).
    servings = suggest_servings(image, [guess.name for guess in guesses], scorer)

    # Save only photos someone could label: with no guesses there's no menu to pick from.
    # The file is written before the database row, so a row never points to a missing file.
    photo_id = None
    if guesses:
        filename = save_photo_file(photo_dir, data)
        photo_id = save_photo(conn, today, hall_name, meal, filename, device_id=device_id)

    return RecognizeOut(
        hall=hall, date=today, meal=meal, photo_id=photo_id,
        guesses=[
            GuessOut(
                recipe_id=rows_by_name[guess.name].recipe_id,
                name=guess.name,
                score=round(guess.score, 3),
                suggested_servings=servings[guess.name],
                nutrition=NutritionOut.model_validate(rows_by_name[guess.name].nutrition),
            )
            for guess in guesses
        ],
    )


def round_macro(value: float) -> float:
    """Round a macro for display, only at the very end so errors don't add up.

    Example:
        round_macro(109.8 * 1.5)  # -> 164.7 instead of 164.70000000000002
    """
    return round(value, 1)


def to_meal_log_out(log: MealLog) -> MealLogOut:
    """Turn a stored MealLog (per-serving macros) into the API shape (macros x servings).

    Example:
        A log of 2 servings of a 109.8-calorie banana comes out with calories=219.6.
    """
    return MealLogOut(
        id=log.id, date=log.date, recipe_id=log.recipe_id, name=log.name,
        servings=log.servings, logged_at=log.logged_at, photo_id=log.photo_id,
        suggested_servings=log.suggested_servings,
        calories=round_macro(log.calories * log.servings),
        protein_g=round_macro(log.protein_g * log.servings),
        carbs_g=round_macro(log.carbs_g * log.servings),
        fat_g=round_macro(log.fat_g * log.servings),
    )


@app.post("/meals", status_code=201)
def create_meal_log(
    meal: MealLogIn,
    conn: sqlite3.Connection = Depends(get_db),
    today: date = Depends(get_today),
    device_id: str = Depends(get_device_id),
) -> MealLogOut:
    """Log that the student ate some servings of a dish.

    Body:
        {"recipe_id": "111*1", "servings": 1.5, "date": "2026-10-12", "photo_id": 7,
         "suggested_servings": 1.5}
        (date, photo_id and suggested_servings optional; the last two come from POST
        /recognize, and suggested_servings needs photo_id)

    Returns:
        201 with the new log. 404 if we have no nutrition for the dish, or this device
        has no such photo.
        422 (automatic) if servings isn't in (0, 5], or suggested_servings comes without photo_id.

    Example:
        POST /meals {"recipe_id": "111*1", "servings": 2}  # -> {"id": 1, "calories": 219.6, ...}
    """
    # Checked here so a typo'd photo_id fails loudly instead of saving a broken label.
    if meal.photo_id is not None and not photo_exists(conn, meal.photo_id, device_id=device_id):
        raise HTTPException(status_code=404, detail=f"No photo with id {meal.photo_id}.")
    log = log_meal(
        conn, meal.log_date or today, meal.recipe_id, meal.servings, meal.photo_id,
        device_id=device_id, suggested_servings=meal.suggested_servings,
    )
    if log is None:
        raise HTTPException(
            status_code=404, detail=f"Can't log '{meal.recipe_id}': no nutrition stored for it."
        )
    return to_meal_log_out(log)


@app.get("/meals")
def list_meal_logs(
    log_date: date | None = Query(None, alias="date"),
    conn: sqlite3.Connection = Depends(get_db),
    today: date = Depends(get_today),
    device_id: str = Depends(get_device_id),
) -> list[MealLogOut]:
    """List the dishes this device logged on a day (default today), oldest first.

    Example:
        GET /meals?date=2026-10-12  # -> [{"id": 1, "name": "Banana", ...}, ...]
    """
    return [to_meal_log_out(log) for log in get_meal_logs(conn, log_date or today, device_id=device_id)]


@app.delete("/meals/{log_id}", status_code=204)
def remove_meal_log(
    log_id: int,
    conn: sqlite3.Connection = Depends(get_db),
    device_id: str = Depends(get_device_id),
) -> None:
    """Delete one logged dish. 204 (empty response) on success, 404 if this device has
    no such log (another student's log counts as missing).

    Example:
        DELETE /meals/1
    """
    if not delete_meal_log(conn, log_id, device_id=device_id):
        raise HTTPException(status_code=404, detail=f"No meal log with id {log_id}.")


@app.get("/summary")
def read_daily_summary(
    log_date: date | None = Query(None, alias="date"),
    conn: sqlite3.Connection = Depends(get_db),
    today: date = Depends(get_today),
    device_id: str = Depends(get_device_id),
) -> DailySummaryOut:
    """Get this device's macro totals for a day (default today). A day with nothing logged is all zeros.

    Example:
        GET /summary  # -> {"date": "2026-10-12", "calories": 460.4, ..., "meal_count": 2}
    """
    day = log_date or today
    totals = get_daily_totals(conn, day, device_id=device_id)
    return DailySummaryOut(
        date=day,
        calories=round_macro(totals.calories),
        protein_g=round_macro(totals.protein_g),
        carbs_g=round_macro(totals.carbs_g),
        fat_g=round_macro(totals.fat_g),
        meal_count=totals.meal_count,
    )
