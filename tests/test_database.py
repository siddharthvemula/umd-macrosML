# Tests for db/database.py. Each test uses a fresh in-memory database,
# so they're fast, isolated from each other, and leave no files behind.

import sqlite3
from dataclasses import replace
from datetime import date, timedelta

import pytest

from conftest import DEVICE
from db.database import (
    connect, count_photos, create_tables, delete_meal_log, get_daily_totals, get_meal_logs, get_menu,
    get_nutrition, has_nutrition, log_meal, photo_exists, save_menu, save_nutrition, save_photo,
)
from scraper.label_parser import NutritionLabel
from scraper.menu_parser import MenuItem

DAY = date(2026, 10, 12)
HALL = "South Campus"


@pytest.fixture
def conn():
    """A brand-new empty database for each test."""
    connection = connect(":memory:")
    yield connection
    connection.close()


def make_label(name: str = "Banana", sugar_g=15.1) -> NutritionLabel:
    """Build a NutritionLabel with sensible defaults so tests only spell out what they check."""
    return NutritionLabel(
        name=name, serving_size="1 each", calories=109.8, protein_g=1.3, carbs_g=28.2,
        fat_g=0.4, sat_fat_g=0.1, sugar_g=sugar_g, fiber_g=3.2, sodium_mg=1.2,
        ingredients="Banana (Banana)", allergens=["Gluten", "Milk"],
    )


BANANA = MenuItem(name="Banana", recipe_id="111*1", station="Fruit", meal="Breakfast")
BURGER = MenuItem(name="Fresh Chicken Burger", recipe_id="080603*4", station="Broiler Works", meal="Lunch")


def test_create_tables_twice_is_safe(conn):
    create_tables(conn)  # connect() already ran it once


def test_saved_nutrition_comes_back_unchanged(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    save_menu(conn, DAY, HALL, [BANANA])
    assert get_menu(conn, DAY, HALL)[0].nutrition == make_label()


def test_blank_nutrient_stays_none_not_zero(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label(sugar_g=None))
    save_menu(conn, DAY, HALL, [BANANA])
    assert get_menu(conn, DAY, HALL)[0].nutrition.sugar_g is None


def test_get_nutrition_returns_saved_label(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    assert get_nutrition(conn, BANANA.recipe_id) == make_label()


def test_get_nutrition_for_unknown_dish_is_none(conn):
    assert get_nutrition(conn, "nope*1") is None


def test_has_nutrition_only_after_saving(conn):
    assert not has_nutrition(conn, BANANA.recipe_id)
    save_nutrition(conn, BANANA.recipe_id, make_label())
    assert has_nutrition(conn, BANANA.recipe_id)


def test_saving_nutrition_again_updates_instead_of_duplicating(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label(name="Banana"))
    save_nutrition(conn, BANANA.recipe_id, make_label(name="Ripe Banana"))
    count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert count == 1
    assert conn.execute("SELECT name FROM items").fetchone()[0] == "Ripe Banana"


def test_menu_keeps_page_order(conn):
    save_menu(conn, DAY, HALL, [BURGER, BANANA])
    assert [row.name for row in get_menu(conn, DAY, HALL)] == ["Fresh Chicken Burger", "Banana"]


def test_dish_without_nutrition_still_on_menu(conn):
    save_menu(conn, DAY, HALL, [BANANA])
    row = get_menu(conn, DAY, HALL)[0]
    assert row.name == "Banana"
    assert row.nutrition is None


def test_rescraping_replaces_the_day(conn):
    save_menu(conn, DAY, HALL, [BANANA, BURGER])
    save_menu(conn, DAY, HALL, [BURGER])
    assert [row.name for row in get_menu(conn, DAY, HALL)] == ["Fresh Chicken Burger"]


def test_rescraping_one_hall_leaves_other_halls_and_days_alone(conn):
    save_menu(conn, DAY, HALL, [BANANA])
    save_menu(conn, DAY, "Yahentamitsi", [BANANA])
    save_menu(conn, date(2026, 10, 13), HALL, [BANANA])
    save_menu(conn, DAY, HALL, [])
    assert len(get_menu(conn, DAY, "Yahentamitsi")) == 1
    assert len(get_menu(conn, date(2026, 10, 13), HALL)) == 1


def test_duplicate_dish_in_same_meal_is_stored_once(conn):
    save_menu(conn, DAY, HALL, [BANANA, BANANA])
    assert len(get_menu(conn, DAY, HALL)) == 1


def test_day_with_no_menu_returns_empty_list(conn):
    assert get_menu(conn, DAY, HALL) == []


def test_connect_creates_db_file_and_folder(tmp_path):
    db_path = tmp_path / "data" / "macros.db"
    connect(str(db_path)).close()
    assert db_path.exists()


# --- Meal logs ---


def test_logged_meal_copies_macros_per_serving(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    log = log_meal(conn, DAY, BANANA.recipe_id, 2, device_id=DEVICE)

    assert (log.name, log.servings, log.calories, log.date) == ("Banana", 2, 109.8, DAY)
    assert get_meal_logs(conn, DAY, device_id=DEVICE) == [log]


def test_logging_dish_without_nutrition_saves_nothing(conn):
    assert log_meal(conn, DAY, "nope*1", 1, device_id=DEVICE) is None
    assert get_meal_logs(conn, DAY, device_id=DEVICE) == []


def test_rescraped_dish_does_not_change_past_logs(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    log_meal(conn, DAY, BANANA.recipe_id, 1, device_id=DEVICE)
    save_nutrition(conn, BANANA.recipe_id, replace(make_label(), calories=500.0))

    assert get_meal_logs(conn, DAY, device_id=DEVICE)[0].calories == 109.8


def test_meal_logs_only_for_requested_day(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    log_meal(conn, DAY, BANANA.recipe_id, 1, device_id=DEVICE)
    assert get_meal_logs(conn, DAY + timedelta(days=1), device_id=DEVICE) == []


def test_delete_meal_log(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    log = log_meal(conn, DAY, BANANA.recipe_id, 1, device_id=DEVICE)

    assert delete_meal_log(conn, log.id, device_id=DEVICE) is True
    assert get_meal_logs(conn, DAY, device_id=DEVICE) == []
    assert delete_meal_log(conn, log.id, device_id=DEVICE) is False  # already gone


def test_daily_totals_multiply_by_servings(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    save_nutrition(conn, BURGER.recipe_id, replace(make_label("Burger"), calories=240.8, protein_g=15.0))
    log_meal(conn, DAY, BANANA.recipe_id, 2, device_id=DEVICE)
    log_meal(conn, DAY, BURGER.recipe_id, 0.5, device_id=DEVICE)

    totals = get_daily_totals(conn, DAY, device_id=DEVICE)
    assert totals.calories == pytest.approx(109.8 * 2 + 240.8 * 0.5)
    assert totals.protein_g == pytest.approx(1.3 * 2 + 15.0 * 0.5)
    assert totals.meal_count == 2


def test_daily_totals_for_empty_day_are_zero(conn):
    totals = get_daily_totals(conn, DAY, device_id=DEVICE)
    assert (totals.calories, totals.protein_g, totals.carbs_g, totals.fat_g, totals.meal_count) == (0, 0, 0, 0, 0)


# --- Plate photos (training data) ---


def test_saved_photo_exists_and_unknown_one_does_not(conn):
    photo_id = save_photo(conn, DAY, "Yahentamitsi", "Lunch", "abc.jpg", device_id=DEVICE)
    assert photo_exists(conn, photo_id, device_id=DEVICE)
    assert not photo_exists(conn, photo_id + 1, device_id=DEVICE)


def test_meal_logged_from_photo_keeps_photo_id(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    photo_id = save_photo(conn, DAY, "Yahentamitsi", None, "abc.jpg", device_id=DEVICE)
    log_meal(conn, DAY, BANANA.recipe_id, 1, photo_id=photo_id, device_id=DEVICE)
    log_meal(conn, DAY, BANANA.recipe_id, 1, device_id=DEVICE)  # logged from the menu instead

    assert [log.photo_id for log in get_meal_logs(conn, DAY, device_id=DEVICE)] == [photo_id, None]


def test_old_database_gets_new_columns_added(tmp_path):
    # A meal_logs table as it was before photo_id and device_id existed, with one logged meal.
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.execute(
        """CREATE TABLE meal_logs (id INTEGER PRIMARY KEY, date TEXT NOT NULL,
           recipe_id TEXT NOT NULL, name TEXT NOT NULL, servings REAL NOT NULL,
           calories REAL NOT NULL, protein_g REAL NOT NULL, carbs_g REAL NOT NULL,
           fat_g REAL NOT NULL, logged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
    )
    old.execute(
        "INSERT INTO meal_logs (date, recipe_id, name, servings, calories, protein_g, carbs_g, fat_g)"
        " VALUES ('2026-10-12', '111*1', 'Banana', 1, 109.8, 1.3, 28.2, 0.4)"
    )
    old.commit()
    old.close()

    conn = connect(path)  # should add the missing columns and keep the old row
    row = conn.execute("SELECT name, photo_id, device_id FROM meal_logs").fetchone()
    assert tuple(row) == ("Banana", None, None)
    # A log from before devices existed belongs to nobody, so no device sees it.
    assert get_meal_logs(conn, DAY, device_id=DEVICE) == []
    conn.close()


OTHER_DEVICE = "22222222-2222-4222-8222-222222222222"


def test_devices_only_see_and_delete_their_own_logs(conn):
    save_nutrition(conn, BANANA.recipe_id, make_label())
    mine = log_meal(conn, DAY, BANANA.recipe_id, 1, device_id=DEVICE)
    log_meal(conn, DAY, BANANA.recipe_id, 3, device_id=OTHER_DEVICE)

    assert get_meal_logs(conn, DAY, device_id=DEVICE) == [mine]
    assert get_daily_totals(conn, DAY, device_id=DEVICE).meal_count == 1
    assert delete_meal_log(conn, mine.id, device_id=OTHER_DEVICE) is False
    assert get_meal_logs(conn, DAY, device_id=DEVICE) == [mine]


def test_photos_belong_to_the_device_that_uploaded_them(conn):
    photo_id = save_photo(conn, DAY, "Yahentamitsi", "Lunch", "abc.jpg", device_id=DEVICE)
    assert not photo_exists(conn, photo_id, device_id=OTHER_DEVICE)
    assert count_photos(conn, DAY, device_id=DEVICE) == 1
    assert count_photos(conn, DAY, device_id=OTHER_DEVICE) == 0
    assert count_photos(conn, DAY + timedelta(days=1), device_id=DEVICE) == 0
