# Tests for the meal logging endpoints in api/main.py: POST/GET/DELETE /meals and
# GET /summary. The `client` and `db_path` fixtures come from conftest.py
# (a temp database per test and a fixed "today" of 2026-10-12).

from db.database import connect, save_nutrition
from scraper.label_parser import NutritionLabel

BANANA_ID = "111*1"
BANANA_LABEL = NutritionLabel(
    name="Banana", serving_size="1 each", calories=109.8, protein_g=1.3, carbs_g=28.2,
    fat_g=0.4, sat_fat_g=None, sugar_g=15.1, fiber_g=3.2, sodium_mg=1.2,
    ingredients="Banana (Banana)", allergens=[],
)


def seed_banana(db_path: str) -> None:
    """Save the banana's nutrition so it can be logged."""
    conn = connect(db_path)
    save_nutrition(conn, BANANA_ID, BANANA_LABEL)
    conn.close()


def test_log_meal_returns_201_with_totals(client, db_path):
    seed_banana(db_path)
    response = client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 1.5})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Banana"
    assert body["date"] == "2026-10-12"  # defaulted to "today"
    assert body["calories"] == 164.7  # 109.8 x 1.5, rounded (not 164.70000000000002)


def test_log_meal_for_another_date(client, db_path):
    seed_banana(db_path)
    client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 1, "date": "2026-10-11"})

    assert len(client.get("/meals", params={"date": "2026-10-11"}).json()) == 1
    assert client.get("/meals").json() == []  # today has nothing


def test_log_dish_without_nutrition_is_404(client):
    response = client.post("/meals", json={"recipe_id": "nope*1", "servings": 1})
    assert response.status_code == 404
    assert "nope*1" in response.json()["detail"]


def test_bad_servings_are_422(client, db_path):
    seed_banana(db_path)
    for servings in [0, -1, 5.5]:
        response = client.post("/meals", json={"recipe_id": BANANA_ID, "servings": servings})
        assert response.status_code == 422, servings


def test_list_meals_in_logged_order(client, db_path):
    seed_banana(db_path)
    client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 1})
    client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 2})

    assert [log["servings"] for log in client.get("/meals").json()] == [1, 2]


def test_delete_meal_is_204_then_404(client, db_path):
    seed_banana(db_path)
    log_id = client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 1}).json()["id"]

    assert client.delete(f"/meals/{log_id}").status_code == 204
    assert client.get("/meals").json() == []
    assert client.delete(f"/meals/{log_id}").status_code == 404


def test_summary_totals_and_updates_after_delete(client, db_path):
    seed_banana(db_path)
    client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 2})
    log_id = client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 1}).json()["id"]

    summary = client.get("/summary").json()
    assert summary["calories"] == 329.4  # 109.8 x 3
    assert summary["meal_count"] == 2

    client.delete(f"/meals/{log_id}")
    assert client.get("/summary").json()["calories"] == 219.6


def test_summary_for_empty_day_is_zeros(client):
    summary = client.get("/summary", params={"date": "2026-10-13"}).json()
    assert summary == {
        "date": "2026-10-13", "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "meal_count": 0,
    }
