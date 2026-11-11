# Tests for POST /recognize in api/main.py. A fake scorer replaces CLIP (swapped in
# through dependency_overrides) and photos are tiny images made in memory, so these
# run in milliseconds with no model download and no photo files.

import io
from datetime import date, timedelta
from pathlib import Path

import pytest
from PIL import Image

import api.main
from api.deps import get_fetcher, get_scorer
from api.main import MAX_PHOTO_BYTES, app
from conftest import DEVICE, TODAY, OfflineFetcher
from db.database import connect, get_menu, get_photo_labels, photo_exists, save_menu, save_nutrition
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
SALAD = MenuItem(name="Salad", recipe_id="2*1", station="Mezza Sides", meal="Lunch")
PANCAKES = MenuItem(name="Pancakes", recipe_id="3*1", station="Grill", meal="Breakfast")
# On the menu, but its label was never scraped.
MYSTERY = MenuItem(name="Mystery Stew", recipe_id="4*1", station="Soup", meal="Lunch")
# Have nutrition, but are a condiment and a Salad Bar topping (ml/candidates.py).
RANCH = MenuItem(name="Ranch Dressing", recipe_id="5*1", station="Grill", meal="Lunch")
CROUTON = MenuItem(name="Crouton", recipe_id="6*1", station="Salad Bar", meal="Lunch")


class FakeScorer:
    """Scores each prompt by a fixed number per dish name, so the ranking is known."""

    SCORES = {
        "Rice": 3.0, "Pancakes": 2.0, "Salad": 1.0, "Mystery Stew": 9.0,
        "Ranch Dressing": 9.0, "Crouton": 9.0,
    }

    def __init__(self) -> None:
        # Every prompt from every call (ranking, then portion sizes for the guesses).
        self.seen_prompts: list[str] = []

    def score(self, image, texts):
        self.seen_prompts += texts
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
    for item, calories in [(RICE, 200.0), (SALAD, 50.0), (PANCAKES, 300.0), (RANCH, 70.0), (CROUTON, 30.0)]:
        save_nutrition(conn, item.recipe_id, make_label(item.name, calories))
    save_menu(conn, TODAY, "Yahentamitsi", [RICE, SALAD, PANCAKES, MYSTERY, RANCH, CROUTON])
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
    # The fake scores every portion of a dish the same, so the suggestion is the 1x default.
    assert body["guesses"][0]["suggested_servings"] == 1.0
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


def test_condiments_and_salad_bar_are_not_guessed(client, db_path, scorer):
    seed_menu(db_path)
    post_photo(client, png_bytes())

    # Both would score highest, but neither is sent to the model.
    assert not any("Ranch Dressing" in prompt or "Crouton" in prompt for prompt in scorer.seen_prompts)


def test_no_menu_today_gives_empty_guesses(client, scorer):
    response = post_photo(client, png_bytes())

    assert response.status_code == 200
    assert response.json()["guesses"] == []


def test_photo_is_saved_with_an_id(client, db_path, photo_dir, scorer):
    seed_menu(db_path)
    data = png_bytes()
    photo_id = post_photo(client, data).json()["photo_id"]

    [saved_file] = photo_dir.iterdir()
    # Re-encoded without metadata (see test_photo_store.py), but the same picture.
    assert Image.open(saved_file).tobytes() == Image.open(io.BytesIO(data)).tobytes()
    conn = connect(db_path)
    assert photo_exists(conn, photo_id, device_id=DEVICE)
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


# --- Photos from a past day (the `date` form field) ---

PAST = TODAY - timedelta(days=3)
FIXTURES = Path(__file__).parent / "fixtures"


def seed_menu_on(db_path: str, day: date) -> None:
    """Like seed_menu, but for another day (nutrition is already shared by dish)."""
    seed_menu(db_path)
    conn = connect(db_path)
    save_menu(conn, day, "Yahentamitsi", [RICE, SALAD, PANCAKES])
    conn.close()


class FixtureFetcher:
    """Serves a saved real menu page and one saved label for every dish, and counts requests."""

    def __init__(self) -> None:
        self.menu_requests: list[date] = []
        self.menu_html = (FIXTURES / "menu_south_campus_2026-10-12.html").read_text()
        self.label_html = (FIXTURES / "label_banana.html").read_text()

    def fetch_menu_html(self, location_num: int, day: date) -> str:
        self.menu_requests.append(day)
        return self.menu_html

    def fetch_label_html(self, recipe_id: str) -> str:
        return self.label_html


class EqualScorer:
    """Scores every prompt the same, for tests where which dish wins doesn't matter."""

    def score(self, image, texts):
        return [1.0] * len(texts)


def test_date_picks_that_days_menu(client, db_path, scorer):
    seed_menu_on(db_path, PAST)
    conn = connect(db_path)
    save_menu(conn, TODAY, "Yahentamitsi", [PANCAKES])  # today's menu is different
    conn.close()

    body = post_photo(client, png_bytes(), date=PAST.isoformat(), meal="Lunch").json()

    assert body["date"] == PAST.isoformat()
    assert [g["name"] for g in body["guesses"]] == ["Rice", "Salad"]


def test_photo_is_saved_under_the_plates_date_not_the_upload_date(client, db_path, scorer):
    seed_menu_on(db_path, PAST)
    photo_id = post_photo(client, png_bytes(), date=PAST.isoformat()).json()["photo_id"]

    conn = connect(db_path)
    client.post("/meals", json={"recipe_id": "1*1", "servings": 1, "photo_id": photo_id, "date": PAST.isoformat()})
    [labels] = get_photo_labels(conn)
    conn.close()
    assert labels.date == PAST


def test_logging_with_the_plates_date_files_the_meal_under_that_day(client, db_path, scorer):
    seed_menu_on(db_path, PAST)
    photo_id = post_photo(client, png_bytes(), date=PAST.isoformat()).json()["photo_id"]

    client.post("/meals", json={"recipe_id": "1*1", "servings": 1, "photo_id": photo_id, "date": PAST.isoformat()})

    assert [log["name"] for log in client.get(f"/meals?date={PAST.isoformat()}").json()] == ["Rice"]
    assert client.get("/meals").json() == []  # nothing logged today


def test_missing_past_menu_is_scraped_automatically(client, db_path, scorer):
    fetcher = FixtureFetcher()
    app.dependency_overrides[get_fetcher] = lambda: fetcher
    app.dependency_overrides[get_scorer] = lambda: EqualScorer()

    body = post_photo(client, png_bytes(), hall="south_campus", date=PAST.isoformat()).json()

    assert fetcher.menu_requests == [PAST]
    assert len(body["guesses"]) == 5
    conn = connect(db_path)
    assert get_menu(conn, PAST, "South Campus")  # saved, so the next photo needs no scrape
    conn.close()


def test_stored_menu_is_not_scraped_again(client, db_path, scorer):
    seed_menu_on(db_path, PAST)
    fetcher = FixtureFetcher()
    app.dependency_overrides[get_fetcher] = lambda: fetcher

    post_photo(client, png_bytes(), date=PAST.isoformat())

    assert fetcher.menu_requests == []


def test_failed_scrape_gives_empty_guesses_not_an_error(client, scorer):
    # conftest's OfflineFetcher fails every download.
    response = post_photo(client, png_bytes(), date=PAST.isoformat())

    assert response.status_code == 200
    assert response.json()["guesses"] == []
    assert response.json()["photo_id"] is None


def test_bad_photo_does_not_trigger_a_scrape(client, scorer):
    fetcher = OfflineFetcher()
    app.dependency_overrides[get_fetcher] = lambda: fetcher

    assert post_photo(client, b"not a photo", date=PAST.isoformat()).status_code == 400
    assert fetcher.menu_requests == []


def test_future_date_is_400_and_not_scraped(client, scorer):
    fetcher = OfflineFetcher()
    app.dependency_overrides[get_fetcher] = lambda: fetcher

    response = post_photo(client, png_bytes(), date=(TODAY + timedelta(days=1)).isoformat())

    assert response.status_code == 400
    assert "hasn't been served" in response.json()["detail"]
    assert fetcher.menu_requests == []


def test_invalid_date_is_422(client, scorer):
    assert post_photo(client, png_bytes(), date="last tuesday").status_code == 422


def test_daily_cap_counts_the_upload_day_so_old_dates_cannot_dodge_it(client, db_path, scorer, monkeypatch):
    monkeypatch.setattr(api.main, "MAX_PHOTOS_PER_DAY", 2)
    seed_menu_on(db_path, PAST)
    for _ in range(2):
        assert post_photo(client, png_bytes(), date=PAST.isoformat()).status_code == 200

    assert post_photo(client, png_bytes(), date=PAST.isoformat()).status_code == 429
    assert post_photo(client, png_bytes()).status_code == 429  # the cap is per upload day, whatever the plate's day
