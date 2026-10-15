# The app's SQLite database: where scraped menus and nutrition are stored, plus the
# meals a student logs. The scraper writes menus into it (save_menu, save_nutrition)
# and the backend reads them (get_menu, get_nutrition) and manages meal logs
# (log_meal, get_meal_logs, delete_meal_log, get_daily_totals). It also acts as our cache: has_nutrition lets the scraper skip
# dishes whose label we already have, so we don't re-download them from UMD.
# Plate photos sent to the recognizer are recorded in `photos` (save_photo); a meal log
# with a photo_id says "this dish was on that photo", which is our ML training label.

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

-- One row per dish a student logged. The macros are copied from items at log time
-- (per serving), so re-scraping a dish later never changes a past log.
CREATE TABLE IF NOT EXISTS meal_logs (
    id        INTEGER PRIMARY KEY,
    date      TEXT NOT NULL,  -- campus date the meal counts toward, ISO format
    recipe_id TEXT NOT NULL,
    name      TEXT NOT NULL,
    servings  REAL NOT NULL,  -- e.g. 1.5 for one and a half servings
    calories  REAL NOT NULL,
    protein_g REAL NOT NULL,
    carbs_g   REAL NOT NULL,
    fat_g     REAL NOT NULL,
    logged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- UTC
    photo_id  INTEGER  -- photos.id if logged from a plate photo, else NULL
);

-- One row per plate photo the recognizer saw. The image itself is a file on disk
-- (databases are bad at big blobs); this row says where it is and what menu it was
-- matched against. Its labels are the meal_logs rows that point to it.
CREATE TABLE IF NOT EXISTS photos (
    id          INTEGER PRIMARY KEY,
    date        TEXT NOT NULL,  -- campus date, ISO format
    hall        TEXT NOT NULL,  -- display name, like menu_entries.hall
    meal        TEXT,           -- e.g. 'Lunch'; NULL if the whole day's menu was used
    filename    TEXT NOT NULL UNIQUE,  -- e.g. '3f2a...c1.jpg', inside the photo folder
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP  -- UTC
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


@dataclass
class MealLog:
    """One logged dish. Macros are per serving; multiply by servings for the total.

    Example:
        MealLog(id=1, date=date(2026, 10, 12), recipe_id="111*1", name="Banana",
                servings=2.0, calories=109.8, protein_g=1.3, carbs_g=28.2, fat_g=0.4,
                logged_at="2026-10-12 16:30:00")
    """

    id: int
    date: date
    recipe_id: str
    name: str
    servings: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    logged_at: str
    # The plate photo this dish was logged from, or None if logged from the menu.
    photo_id: Optional[int] = None


@dataclass
class DailyTotals:
    """A day's macro totals across all logged dishes (servings already applied).

    Example:
        DailyTotals(calories=829.2, protein_g=27.4, carbs_g=104.4, fat_g=10.3, meal_count=2)
    """

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_count: int


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
    _add_missing_columns(conn)


# Columns added after a table first shipped: (table, column, SQL type). CREATE TABLE IF
# NOT EXISTS skips a table that already exists, so an older database file would never
# get these. This list is a tiny "migration" step that adds them.
ADDED_COLUMNS = [("meal_logs", "photo_id", "INTEGER")]


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Add any column from ADDED_COLUMNS that an older database file is missing.

    Example:
        A database made before photo_id existed gets `meal_logs.photo_id` (NULL for old rows).
    """
    for table, column, sql_type in ADDED_COLUMNS:
        # PRAGMA table_info lists a table's columns; row["name"] is each column's name.
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            with conn:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")


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


def log_meal(
    conn: sqlite3.Connection, day: date, recipe_id: str, servings: float,
    photo_id: Optional[int] = None,
) -> Optional[MealLog]:
    """Log that a student ate `servings` of a dish on `day`.

    Args:
        photo_id: The plate photo this dish was picked from (see save_photo), or None.
            Check it exists first with photo_exists.

    Returns:
        The saved MealLog, or None (and nothing saved) if we have no nutrition for
        this dish, since we can't count macros we don't know.

    Example:
        log_meal(conn, date(2026, 10, 12), "111*1", 1.5).calories  # -> 109.8 (per serving)
    """
    label = get_nutrition(conn, recipe_id)
    if label is None:
        return None
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO meal_logs
                (date, recipe_id, name, servings, calories, protein_g, carbs_g, fat_g, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (day.isoformat(), recipe_id, label.name, servings,
             label.calories, label.protein_g, label.carbs_g, label.fat_g, photo_id),
        )
    # Read the row back so the result includes the id and logged_at SQLite filled in.
    row = conn.execute("SELECT * FROM meal_logs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_meal_log(row)


def get_meal_logs(conn: sqlite3.Connection, day: date) -> List[MealLog]:
    """Get every dish logged on `day`, oldest first. An empty list if none.

    Example:
        [log.name for log in get_meal_logs(conn, date(2026, 10, 12))]  # -> ["Banana", ...]
    """
    rows = conn.execute(
        "SELECT * FROM meal_logs WHERE date = ? ORDER BY id", (day.isoformat(),)
    ).fetchall()
    return [_row_to_meal_log(row) for row in rows]


def delete_meal_log(conn: sqlite3.Connection, log_id: int) -> bool:
    """Delete one meal log.

    Returns:
        True if it was deleted, False if no log has that id.

    Example:
        delete_meal_log(conn, 1)  # -> True, then False if called again
    """
    with conn:
        cursor = conn.execute("DELETE FROM meal_logs WHERE id = ?", (log_id,))
    return cursor.rowcount > 0


def get_daily_totals(conn: sqlite3.Connection, day: date) -> DailyTotals:
    """Add up a day's macros, multiplying each dish by its servings.

    Returns:
        The totals. A day with nothing logged gives all zeros.

    Example:
        # 2 bananas (109.8 cal each) + 1 burger (240.8 cal)
        get_daily_totals(conn, date(2026, 10, 12)).calories  # -> 460.4
    """
    # SUM over zero rows is NULL in SQL, so COALESCE turns that into 0.
    row = conn.execute(
        """
        SELECT COALESCE(SUM(calories * servings), 0)  AS calories,
               COALESCE(SUM(protein_g * servings), 0) AS protein_g,
               COALESCE(SUM(carbs_g * servings), 0)   AS carbs_g,
               COALESCE(SUM(fat_g * servings), 0)     AS fat_g,
               COUNT(*)                               AS meal_count
        FROM meal_logs WHERE date = ?
        """,
        (day.isoformat(),),
    ).fetchone()
    return DailyTotals(**dict(row))


def save_photo(
    conn: sqlite3.Connection, day: date, hall: str, meal: Optional[str], filename: str,
) -> int:
    """Record a plate photo that was saved to disk as `filename`.

    Args:
        day: The campus date whose menu the photo was matched against.
        hall: Hall display name, e.g. "Yahentamitsi".
        meal: e.g. "Lunch", or None if the whole day's menu was used.
        filename: The file's name inside the photo folder.

    Returns:
        The new photo's id, which meal logs use as photo_id.

    Example:
        save_photo(conn, date(2026, 10, 15), "Yahentamitsi", "Lunch", "3f2a.jpg")  # -> 1
    """
    with conn:
        cursor = conn.execute(
            "INSERT INTO photos (date, hall, meal, filename) VALUES (?, ?, ?, ?)",
            (day.isoformat(), hall, meal, filename),
        )
    return cursor.lastrowid


def photo_exists(conn: sqlite3.Connection, photo_id: int) -> bool:
    """Check whether a photo with this id was recorded.

    Example:
        photo_exists(conn, 1)  # -> True after the first save_photo
    """
    row = conn.execute("SELECT 1 FROM photos WHERE id = ?", (photo_id,)).fetchone()
    return row is not None


def _row_to_meal_log(row: sqlite3.Row) -> MealLog:
    """Turn one meal_logs row into a MealLog (parsing the ISO date text back into a date)."""
    values = dict(row)
    values["date"] = date.fromisoformat(values["date"])
    return MealLog(**values)
