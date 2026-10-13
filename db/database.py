# The app's SQLite database: where scraped menus and nutrition are stored.
# The scraper writes into it (save_menu, save_nutrition) and the backend will read
# from it (get_menu, get_nutrition). It also acts as our cache: has_nutrition lets the scraper skip
# dishes whose label we already have, so we don't re-download them from UMD.

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

from scraper.label_parser import NutritionLabel
from scraper.menu_parser import MenuItem

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "macros.db"

# Two tables:
#   items        - one row per dish (keyed by UMD's recipe ID) with its nutrition.
#                  A banana served every day is stored once here.
#   menu_entries - one row per "dish X served at hall H, meal M, on date D".
# menu_entries keeps the dish name itself and has no foreign key to items, so a
# menu can be saved even if one dish's label failed to download. get_menu then
# shows that dish with nutrition=None instead of losing it.
SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    recipe_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    serving_size TEXT NOT NULL,
    calories     REAL NOT NULL,
    protein_g    REAL NOT NULL,
    carbs_g      REAL NOT NULL,
    fat_g        REAL NOT NULL,
    sat_fat_g    REAL,
    sugar_g      REAL,
    fiber_g      REAL,
    sodium_mg    REAL,
    ingredients  TEXT NOT NULL,
    allergens    TEXT NOT NULL,  -- JSON list, e.g. '["Gluten", "Milk"]'
    updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS menu_entries (
    id        INTEGER PRIMARY KEY,
    date      TEXT NOT NULL,  -- ISO format, e.g. '2026-10-12'
    hall      TEXT NOT NULL,
    meal      TEXT NOT NULL,
    station   TEXT NOT NULL,
    name      TEXT NOT NULL,
    recipe_id TEXT NOT NULL,
    UNIQUE (date, hall, meal, recipe_id)
);
"""

NUTRITION_COLUMNS = [
    "name", "serving_size", "calories", "protein_g", "carbs_g", "fat_g",
    "sat_fat_g", "sugar_g", "fiber_g", "sodium_mg", "ingredients", "allergens",
]


@dataclass
class MenuRow:
    """One dish on a day's menu, joined with its nutrition (if we have it).

    Example:
        MenuRow(name="Banana", recipe_id="111*1", station="Fruit", meal="Breakfast",
                nutrition=NutritionLabel(name="Banana", calories=109.8, ...))
    """

    name: str
    recipe_id: str
    station: str
    meal: str
    # None means the label hasn't been scraped yet (e.g. its download failed).
    nutrition: Optional[NutritionLabel]


def connect(path: str = str(DEFAULT_DB_PATH), check_same_thread: bool = True) -> sqlite3.Connection:
    """Open the database (creating the file and tables if needed).

    Args:
        path: File path for the database, or ":memory:" for a throwaway one (tests).
        check_same_thread: sqlite3's guard that a connection is only used by the thread
            that opened it. The API turns it off (see api/deps.py).

    Returns:
        An open connection whose rows can be read by column name.

    Example:
        conn = connect(":memory:")
    """
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row  # lets us write row["calories"] instead of row[2]
    create_tables(conn)
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """Create the tables if they don't exist yet. Safe to call more than once.

    Example:
        create_tables(conn)  # second call does nothing
    """
    conn.executescript(SCHEMA)


def save_nutrition(conn: sqlite3.Connection, recipe_id: str, label: NutritionLabel) -> None:
    """Insert a dish's nutrition, or overwrite it if the dish is already stored.

    Args:
        recipe_id: UMD's ID for the dish, e.g. "080603*4".
        label: The parsed nutrition label.

    Example:
        save_nutrition(conn, "111*1", banana_label)
    """
    values = [getattr(label, column) for column in NUTRITION_COLUMNS]
    # SQLite has no list type, so allergens are stored as JSON text.
    values[NUTRITION_COLUMNS.index("allergens")] = json.dumps(label.allergens)

    columns = ", ".join(NUTRITION_COLUMNS)
    placeholders = ", ".join("?" for _ in NUTRITION_COLUMNS)
    updates = ", ".join(f"{column} = excluded.{column}" for column in NUTRITION_COLUMNS)
    # "Upsert": if this recipe_id exists, update it in place (UMD may fix a label).
    # The ? placeholders let sqlite3 escape values, which prevents SQL injection.
    with conn:
        conn.execute(
            f"""
            INSERT INTO items (recipe_id, {columns}) VALUES (?, {placeholders})
            ON CONFLICT (recipe_id) DO UPDATE SET {updates}, updated_at = CURRENT_TIMESTAMP
            """,
            [recipe_id, *values],
        )


def has_nutrition(conn: sqlite3.Connection, recipe_id: str) -> bool:
    """Check whether we already stored this dish's nutrition (so we can skip fetching it).

    Example:
        has_nutrition(conn, "111*1")  # -> True after save_nutrition(conn, "111*1", ...)
    """
    row = conn.execute("SELECT 1 FROM items WHERE recipe_id = ?", (recipe_id,)).fetchone()
    return row is not None


def save_menu(conn: sqlite3.Connection, menu_date: date, hall: str, items: List[MenuItem]) -> None:
    """Store a hall's menu for one day, replacing whatever was saved for that day before.

    Args:
        menu_date: The day the menu is for.
        hall: Dining hall name, e.g. "South Campus".
        items: Dishes from parse_menu_page. An empty list saves an empty day.

    Example:
        save_menu(conn, date(2026, 10, 12), "South Campus", menu_items)
    """
    # Replace the whole day instead of merging, so a dish UMD removed from the menu
    # disappears on re-scrape. Inside `with conn`, the delete and inserts happen as
    # one transaction: if anything fails, the old menu is kept untouched.
    with conn:
        conn.execute(
            "DELETE FROM menu_entries WHERE date = ? AND hall = ?",
            (menu_date.isoformat(), hall),
        )
        # OR IGNORE: if a dish is listed twice in the same meal, keep the first one.
        conn.executemany(
            """
            INSERT OR IGNORE INTO menu_entries (date, hall, meal, station, name, recipe_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (menu_date.isoformat(), hall, item.meal, item.station, item.name, item.recipe_id)
                for item in items
            ],
        )


def get_menu(conn: sqlite3.Connection, menu_date: date, hall: str) -> List[MenuRow]:
    """Get a hall's menu for one day, with each dish's nutrition attached.

    Returns:
        Dishes in the order they were saved (the order on UMD's page).
        An empty list if no menu is stored for that day.

    Example:
        get_menu(conn, date(2026, 10, 12), "South Campus")[0].nutrition.protein_g  # -> 15.0
    """
    # LEFT JOIN keeps menu dishes even when they have no row in items yet.
    rows = conn.execute(
        """
        SELECT menu_entries.name AS menu_name, menu_entries.recipe_id,
               menu_entries.station, menu_entries.meal, items.*
        FROM menu_entries
        LEFT JOIN items ON items.recipe_id = menu_entries.recipe_id
        WHERE menu_entries.date = ? AND menu_entries.hall = ?
        ORDER BY menu_entries.id
        """,
        (menu_date.isoformat(), hall),
    ).fetchall()
    return [_row_to_menu_row(row) for row in rows]


def get_nutrition(conn: sqlite3.Connection, recipe_id: str) -> Optional[NutritionLabel]:
    """Look up one dish's stored nutrition.

    Returns:
        The NutritionLabel, or None if we don't have this dish's label.

    Example:
        get_nutrition(conn, "111*1").calories  # -> 109.8
    """
    row = conn.execute("SELECT * FROM items WHERE recipe_id = ?", (recipe_id,)).fetchone()
    return None if row is None else _row_to_label(row)


def _row_to_label(row: sqlite3.Row) -> NutritionLabel:
    """Turn a row that has the items columns into a NutritionLabel (decoding allergens JSON)."""
    values = {column: row[column] for column in NUTRITION_COLUMNS}
    values["allergens"] = json.loads(values["allergens"])
    return NutritionLabel(**values)


def _row_to_menu_row(row: sqlite3.Row) -> MenuRow:
    """Turn one joined database row into a MenuRow (nutrition=None if the join found nothing)."""
    # calories is NOT NULL in items, so NULL here means the LEFT JOIN found no item row.
    nutrition = _row_to_label(row) if row["calories"] is not None else None
    return MenuRow(
        name=row["menu_name"],
        recipe_id=row["recipe_id"],
        station=row["station"],
        meal=row["meal"],
        nutrition=nutrition,
    )
