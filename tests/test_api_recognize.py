# Tests for POST /recognize in api/main.py. A fake scorer replaces CLIP (swapped in
# through dependency_overrides) and photos are tiny images made in memory, so these
# run in milliseconds with no model download and no photo files.

import io

import pytest
from PIL import Image

from api.deps import get_scorer
from api.main import MAX_PHOTO_BYTES, app
from conftest import TODAY
from db.database import connect, photo_exists, save_menu, save_nutrition
from scraper.label_parser import NutritionLabel
from scraper.menu_parser import MenuItem

HALL_ID = "yahentamitsi"


def make_label(name: str, calories: float) -> NutritionLabel:
    """A minimal nutrition label for a test dish."""
    return NutritionLabel(
        name=name, serving_size="1 each", calories=calories, protein_g=1.0, carbs_g=1.0,
        fat_g=1.0, sat_fat_g=None, sugar_g=None, fiber_g=None, sodium_mg=None,
        ingredients="", allergens=[],
    )


RICE = MenuItem(name="Rice", recipe_id="1*1", station="Grill", meal="Lunch")
SALAD = MenuItem(name="Salad", recipe_id="2*1", station="Salad Bar", meal="Lunch")
PANCAKES = MenuItem(name="Pancakes", recipe_id="3*1", station="Grill", meal="Breakfast")
# On the menu, but its label was never scraped.
MYSTERY = MenuItem(name="Mystery Stew", recipe_id="4*1", station="Soup", meal="Lunch")


class FakeScorer:
    """Scores each prompt by a fixed number per dish name, so the ranking is known."""

    SCORES = {"Rice": 3.0, "Pancakes": 2.0, "Salad": 1.0, "Mystery Stew": 9.0}

    def __init__(self) -> None:
        self.seen_prompts: list[str] = []

    def score(self, image, texts):
        self.seen_prompts = texts
        return [next(s for name, s in self.SCORES.items() if name in text) for text in texts]


@pytest.fixture
def scorer(client):
    """Swap the fake scorer in for CLIP (conftest's `client` clears overrides after)."""
    fake = FakeScorer()
    app.dependency_overrides[get_scorer] = lambda: fake
    return fake


def seed_menu(db_path: str) -> None:
    """Save today's Yahentamitsi menu, with nutrition for every dish except MYSTERY."""
    conn = connect(db_path)
    for item, calories in [(RICE, 200.0), (SALAD, 50.0), (PANCAKES, 300.0)]:
        save_nutrition(conn, item.recipe_id, make_label(item.name, calories))
    save_menu(conn, TODAY, "Yahentamitsi", [RICE, SALAD, PANCAKES, MYSTERY])
    conn.close()


def png_bytes() -> bytes:
    """A real (tiny) PNG file's bytes."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def post_photo(client, data: bytes, **form):
    """Upload `data` as the photo, with the given form fields (hall defaults to Yahentamitsi)."""
    form.setdefault("hall", HALL_ID)
    return client.post("/recognize", files={"photo": ("plate.png", data, "image/png")}, data=form)


def test_guesses_are_ranked_with_recipe_ids_and_nutrition(client, db_path, scorer):
    seed_menu(db_path)
    response = post_photo(client, png_bytes())

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == TODAY.isoformat()
    assert [g["name"] for g in body["guesses"]] == ["Rice", "Pancakes", "Salad"]
    assert body["guesses"][0]["recipe_id"] == "1*1"
    assert body["guesses"][0]["nutrition"]["calories"] == 200.0
    assert sum(g["score"] for g in body["guesses"]) == pytest.approx(1, abs=0.01)


def test_meal_limits_the_candidates(client, db_path, scorer):
    seed_menu(db_path)
    body = post_photo(client, png_bytes(), meal="lunch").json()  # case doesn't matter

    assert [g["name"] for g in body["guesses"]] == ["Rice", "Salad"]


def test_dishes_without_nutrition_are_not_guessed(client, db_path, scorer):
    seed_menu(db_path)
    post_photo(client, png_bytes())

    # Mystery Stew would score highest, but it's never even sent to the model.
    assert not any("Mystery Stew" in prompt for prompt in scorer.seen_prompts)


def test_no_menu_today_gives_empty_guesses(client, scorer):
    response = post_photo(client, png_bytes())

    assert response.status_code == 200
    assert response.json()["guesses"] == []


def test_photo_is_saved_with_an_id(client, db_path, photo_dir, scorer):
    seed_menu(db_path)
    data = png_bytes()
    photo_id = post_photo(client, data).json()["photo_id"]

    [saved_file] = photo_dir.iterdir()
    assert saved_file.read_bytes() == data
    conn = connect(db_path)
    assert photo_exists(conn, photo_id)
    conn.close()


def test_photo_with_no_guesses_is_not_saved(client, photo_dir, scorer):
    body = post_photo(client, png_bytes()).json()

    assert body["photo_id"] is None
    assert not photo_dir.exists()


def test_bad_photo_is_not_saved(client, db_path, photo_dir, scorer):
    seed_menu(db_path)
    post_photo(client, b"this is not a photo")
    assert not photo_dir.exists()


def test_non_image_file_is_400(client, db_path, scorer):
    seed_menu(db_path)
    response = post_photo(client, b"this is not a photo")

    assert response.status_code == 400
    assert "readable image" in response.json()["detail"]


def test_too_large_photo_is_413(client, db_path, scorer):
    response = post_photo(client, b"x" * (MAX_PHOTO_BYTES + 1))
    assert response.status_code == 413


def test_unknown_hall_is_404(client, scorer):
    response = post_photo(client, png_bytes(), hall="hogwarts")
    assert response.status_code == 404


def test_missing_photo_is_422(client, scorer):
    response = client.post("/recognize", data={"hall": HALL_ID})
    assert response.status_code == 422
