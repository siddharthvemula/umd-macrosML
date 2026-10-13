# Tests for the /items/{recipe_id} endpoint in api/main.py. The `client` and
# `db_path` fixtures come from conftest.py (a temp database per test).

from db.database import connect, save_nutrition
from scraper.label_parser import NutritionLabel

BURGER_ID = "080603*4"  # real UMD ID; the * must survive the trip through the URL
BURGER_LABEL = NutritionLabel(
    name="Fresh Chicken Burger", serving_size="4 oz", calories=240.8, protein_g=15.0,
    carbs_g=32.0, fat_g=6.3, sat_fat_g=1.4, sugar_g=0.5, fiber_g=1.6, sodium_mg=None,
    ingredients="Chicken, Bun", allergens=["Gluten", "Soy"],
)


def seed_burger(db_path: str) -> None:
    """Save the burger's nutrition into the test database."""
    conn = connect(db_path)
    save_nutrition(conn, BURGER_ID, BURGER_LABEL)
    conn.close()


def test_item_returns_its_nutrition(client, db_path):
    seed_burger(db_path)
    response = client.get(f"/items/{BURGER_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Fresh Chicken Burger"
    assert body["calories"] == 240.8
    assert body["allergens"] == ["Gluten", "Soy"]
    assert body["sodium_mg"] is None


def test_unknown_item_is_404(client):
    response = client.get("/items/nope*1")
    assert response.status_code == 404
    assert "nope*1" in response.json()["detail"]
