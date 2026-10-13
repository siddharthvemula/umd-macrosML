# The FastAPI backend: serves the menus and nutrition the scraper saved to the
# database, and lets a student log meals and see their daily totals. Run it locally with
#   .venv/bin/uvicorn api.main:app --reload
# then open http://127.0.0.1:8000/docs to try the endpoints in the browser.

import sqlite3
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query

from api.deps import get_db, get_today
from api.schemas import (
    DailySummaryOut, HallOut, MealLogIn, MealLogOut, MenuItemOut, MenuOut, NutritionOut,
)
from db.database import (
    MealLog, delete_meal_log, get_daily_totals, get_meal_logs, get_menu, get_nutrition, log_meal,
)
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


@app.get("/halls")
def list_halls() -> list[HallOut]:
    """List the dining halls we have menus for.

    Example response: [{"id": "south_campus", "name": "South Campus"}]
    """
    return [HallOut(id=id_, name=name) for id_, name in HALL_NAMES_BY_ID.items()]


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
    hall_name = HALL_NAMES_BY_ID.get(hall)
    if hall_name is None:
        raise HTTPException(status_code=404, detail=f"Unknown hall '{hall}'. See /halls for valid IDs.")

    day = menu_date or today
    rows = get_menu(conn, day, hall_name)
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
        servings=log.servings, logged_at=log.logged_at,
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
) -> MealLogOut:
    """Log that the student ate some servings of a dish.

    Body:
        {"recipe_id": "111*1", "servings": 1.5, "date": "2026-10-12"}  (date optional)

    Returns:
        201 with the new log. 404 if we have no nutrition for the dish.
        422 (automatic) if servings isn't in (0, 5].

    Example:
        POST /meals {"recipe_id": "111*1", "servings": 2}  # -> {"id": 1, "calories": 219.6, ...}
    """
    log = log_meal(conn, meal.log_date or today, meal.recipe_id, meal.servings)
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
) -> list[MealLogOut]:
    """List the dishes logged on a day (default today), oldest first.

    Example:
        GET /meals?date=2026-10-12  # -> [{"id": 1, "name": "Banana", ...}, ...]
    """
    return [to_meal_log_out(log) for log in get_meal_logs(conn, log_date or today)]


@app.delete("/meals/{log_id}", status_code=204)
def remove_meal_log(log_id: int, conn: sqlite3.Connection = Depends(get_db)) -> None:
    """Delete one logged dish. 204 (empty response) on success, 404 if there's no such log.

    Example:
        DELETE /meals/1
    """
    if not delete_meal_log(conn, log_id):
        raise HTTPException(status_code=404, detail=f"No meal log with id {log_id}.")


@app.get("/summary")
def read_daily_summary(
    log_date: date | None = Query(None, alias="date"),
    conn: sqlite3.Connection = Depends(get_db),
    today: date = Depends(get_today),
) -> DailySummaryOut:
    """Get a day's macro totals (default today). A day with nothing logged is all zeros.

    Example:
        GET /summary  # -> {"date": "2026-10-12", "calories": 460.4, ..., "meal_count": 2}
    """
    day = log_date or today
    totals = get_daily_totals(conn, day)
    return DailySummaryOut(
        date=day,
        calories=round_macro(totals.calories),
        protein_g=round_macro(totals.protein_g),
        carbs_g=round_macro(totals.carbs_g),
        fat_g=round_macro(totals.fat_g),
        meal_count=totals.meal_count,
    )
