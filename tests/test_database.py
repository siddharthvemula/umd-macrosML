# Tests for db/database.py. Each test uses a fresh in-memory database,
# so they're fast, isolated from each other, and leave no files behind.

from datetime import date

import pytest

from db.database import (
    connect, create_tables, get_menu, get_nutrition, has_nutrition, save_menu, save_nutrition,
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
