# Tests for the /halls and /menu endpoints in api/main.py. Each test gets its own
# temporary database file and a fixed "today", swapped in through FastAPI's
# dependency_overrides, so tests never touch the real database or the real clock.

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db, get_today
from api.main import app
from db.database import connect, save_menu, save_nutrition
from scraper.label_parser import NutritionLabel
from scraper.menu_parser import MenuItem

TODAY = date(2026, 10, 12)
HALL = "South Campus"

BANANA_LABEL = NutritionLabel(
    name="Banana", serving_size="1 each", calories=109.8, protein_g=1.3, carbs_g=28.2,
    fat_g=0.4, sat_fat_g=None, sugar_g=15.1, fiber_g=3.2, sodium_mg=1.2,
    ingredients="Banana (Banana)", allergens=[],
)
BANANA = MenuItem(name="Banana", recipe_id="111*1", station="Fruit", meal="Breakfast")
BURGER = MenuItem(name="Fresh Chicken Burger", recipe_id="080603*4", station="Broiler Works", meal="Lunch")


@pytest.fixture
def db_path(tmp_path):
    """Path to a fresh, empty database file for this test (pytest deletes tmp_path after)."""
    path = str(tmp_path / "test.db")
    connect(path).close()  # creates the tables
    return path


@pytest.fixture
def client(db_path):
    """A TestClient whose requests use the test database and a fixed date of TODAY."""

    def get_test_db():
        # A file, not ":memory:": each in-memory connection is its own separate,
        # empty database, so data seeded by the test wouldn't be visible here.
        conn = connect(db_path, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_today] = lambda: TODAY
    yield TestClient(app)
    app.dependency_overrides.clear()  # don't leak fakes into other test files


def seed(db_path: str, day: date, items: list[MenuItem]) -> None:
    """Save a menu (and the banana's nutrition) into the test database."""
    conn = connect(db_path)
    save_nutrition(conn, BANANA.recipe_id, BANANA_LABEL)
    save_menu(conn, day, HALL, items)
    conn.close()


def test_halls_lists_south_campus(client):
    response = client.get("/halls")
    assert response.status_code == 200
    assert response.json() == [{"id": "south_campus", "name": "South Campus"}]


def test_menu_returns_items_with_nutrition(client, db_path):
    seed(db_path, TODAY, [BANANA])
    response = client.get("/menu", params={"hall": "south_campus", "date": "2026-10-12"})

    assert response.status_code == 200
    body = response.json()
    assert body["hall"] == "south_campus"
    assert body["date"] == "2026-10-12"
    banana = body["items"][0]
    assert banana["recipe_id"] == "111*1"
    assert banana["nutrition"]["protein_g"] == 1.3
    assert banana["nutrition"]["sat_fat_g"] is None  # blank stays null, not 0


def test_menu_item_without_scraped_label_has_null_nutrition(client, db_path):
    seed(db_path, TODAY, [BANANA, BURGER])
    items = client.get("/menu", params={"hall": "south_campus"}).json()["items"]

    assert [item["name"] for item in items] == ["Banana", "Fresh Chicken Burger"]
    assert items[1]["nutrition"] is None


def test_menu_defaults_to_today(client, db_path):
    seed(db_path, TODAY, [BANANA])
    body = client.get("/menu", params={"hall": "south_campus"}).json()

    assert body["date"] == "2026-10-12"
    assert len(body["items"]) == 1


def test_menu_for_day_with_nothing_stored_is_empty(client):
    response = client.get("/menu", params={"hall": "south_campus", "date": "2026-10-13"})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_unknown_hall_is_404(client):
    response = client.get("/menu", params={"hall": "nowhere"})
    assert response.status_code == 404
    assert "Unknown hall" in response.json()["detail"]


def test_bad_date_is_422(client):
    response = client.get("/menu", params={"hall": "south_campus", "date": "not-a-date"})
    assert response.status_code == 422


def test_missing_hall_is_422(client):
    assert client.get("/menu").status_code == 422
