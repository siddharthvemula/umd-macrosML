# The FastAPI backend: serves the menus and nutrition the scraper saved to the
# database, for the React frontend to display. Run it locally with
#   .venv/bin/uvicorn api.main:app --reload
# then open http://127.0.0.1:8000/docs to try the endpoints in the browser.

import sqlite3
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query

from api.deps import get_db, get_today
from api.schemas import HallOut, MenuItemOut, MenuOut, NutritionOut
from db.database import get_menu, get_nutrition
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
