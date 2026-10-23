# Tests for ml/evaluate.py. A fake scorer stands in for CLIP and a temporary SQLite
# database holds a tiny menu, so these never load the model or touch real data.

from datetime import date

import pytest
from PIL import Image

from db.database import connect, save_menu, save_nutrition
from ml.evaluate import (
    LabeledPhoto,
    append_history,
    evaluate,
    find_unknown_dishes,
    load_candidates,
    read_labels,
    score_photo,
    summarize,
)
from ml.recognizer import Guess
from scraper.label_parser import NutritionLabel
from scraper.menu_parser import MenuItem

DAY = date(2026, 10, 14)
LUNCH = ["Spanish Rice", "Pork Carnitas", "Corn Tostada", "Charro Beans", "Chipotle Chicken", "Banana"]


class FakeScorer:
    """Scores each prompt by which dish name it contains, ignoring the image."""

    def __init__(self, scores_by_name: dict[str, float]) -> None:
        self.scores_by_name = scores_by_name

    def score(self, image: Image.Image, texts: list[str]) -> list[float]:
        return [
            next((s for name, s in self.scores_by_name.items() if name in text), 0.0)
            for text in texts
        ]


def guesses(*names: str) -> list[Guess]:
    """Build a ranked guess list from names, best first."""
    return [Guess(name=name, score=0.1) for name in names]


# On the lunch menu, but UMD published no nutrition for it, so /recognize never guesses it.
NO_NUTRITION_DISH = "Maryland Crab Soup"
# On the lunch menu with nutrition, but a condiment, so /recognize never guesses it either.
CONDIMENT = "Salsa Roja"


def make_label(name: str) -> NutritionLabel:
    """A minimal nutrition label, so a menu dish counts as loggable."""
    return NutritionLabel(
        name=name, serving_size="1 each", calories=100.0, protein_g=1.0, carbs_g=1.0,
        fat_g=1.0, sat_fat_g=None, sugar_g=None, fiber_g=None, sodium_mg=None,
        ingredients="", allergens=[],
    )


@pytest.fixture
def conn(tmp_path):
    """A temporary database with one Yahentamitsi lunch menu: LUNCH and CONDIMENT (with
    nutrition) plus NO_NUTRITION_DISH (without)."""
    connection = connect(str(tmp_path / "test.db"))
    items = [MenuItem(name=name, recipe_id=f"{i}*1", station="Grill", meal="Lunch") for i, name in enumerate(LUNCH)]
    items.append(MenuItem(name=CONDIMENT, recipe_id="98*1", station="Grill", meal="Lunch"))
    for item in items:
        save_nutrition(connection, item.recipe_id, make_label(item.name))
    items.append(MenuItem(name=NO_NUTRITION_DISH, recipe_id="99*1", station="Soup", meal="Lunch"))
    save_menu(connection, DAY, "Yahentamitsi", items)
    yield connection
    connection.close()


@pytest.fixture
def photo_dir(tmp_path):
    """A folder with one small real JPEG, plate.jpg."""
    folder = tmp_path / "photos"
    folder.mkdir()
    Image.new("RGB", (8, 8), "white").save(folder / "plate.jpg")
    return folder


def test_score_photo_top1_hit():
    result = score_photo("p.jpg", guesses("Rice", "Salad", "Beans"), ["Rice"])
    assert result.top1_hit and result.top3_hit and result.recall_at_5 == 1.0


def test_score_photo_hit_only_at_rank_3():
    result = score_photo("p.jpg", guesses("Rice", "Salad", "Beans"), ["Beans"])
    assert not result.top1_hit and result.top3_hit


def test_score_photo_total_miss():
    result = score_photo("p.jpg", guesses("Rice", "Salad"), ["Tacos"])
    assert not result.top1_hit and not result.top3_hit and result.recall_at_5 == 0.0


def test_score_photo_partial_recall_ignores_rank_6():
    result = score_photo("p.jpg", guesses("A", "B", "C", "D", "E", "F"), ["A", "E", "F", "G"])
    assert result.recall_at_5 == 0.5  # A and E found; F is rank 6, G never guessed


def test_read_labels_skips_menu_unavailable_and_splits_on_semicolon(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text(
        "photo,date,hall,meal,dishes,notes\n"
        'a.jpg,2026-10-14,yahentamitsi,Lunch,"Rice; Mac, Cheese",\n'
        "b.jpg,2026-10-14,yahentamitsi,Lunch,Rice,menu unavailable (not scraped)\n"
    )
    photos = read_labels(path)
    assert [p.photo for p in photos] == ["a.jpg"]
    assert photos[0].dishes == ["Rice", "Mac, Cheese"]
    assert photos[0].day == DAY


def test_load_candidates_matches_hall_case_insensitively(conn):
    assert load_candidates(conn, DAY, "yahentamitsi", "Lunch") == LUNCH


def test_load_candidates_leaves_out_dishes_without_nutrition(conn):
    # Same rule as POST /recognize, so the eval scores what the app would really show.
    assert NO_NUTRITION_DISH not in load_candidates(conn, DAY, "yahentamitsi", "Lunch")


def test_load_candidates_leaves_out_condiments(conn):
    # Same rule as POST /recognize (ml/candidates.py).
    assert CONDIMENT not in load_candidates(conn, DAY, "yahentamitsi", "Lunch")


def test_load_candidates_with_empty_meal_uses_whole_day(conn):
    # Photos taken with meal "Any" in the app are exported with meal "".
    assert load_candidates(conn, DAY, "yahentamitsi", "") == LUNCH


def test_load_candidates_returns_empty_for_missing_menu(conn):
    assert load_candidates(conn, date(2026, 1, 1), "yahentamitsi", "Lunch") == []


def test_find_unknown_dishes_flags_typo():
    assert find_unknown_dishes(["Pork Carnitas", "Pork Carnitass"], LUNCH) == ["Pork Carnitass"]


def test_evaluate_end_to_end_with_fake_scorer(conn, photo_dir):
    photos = [LabeledPhoto("plate.jpg", DAY, "yahentamitsi", "Lunch", ["Pork Carnitas", "Charro Beans", "Not A Dish"])]
    scorer = FakeScorer({"Pork Carnitas": 10.0, "Spanish Rice": 5.0})

    [result] = evaluate(photos, scorer, conn, "a photo of {name}", photo_dir)

    assert result.guesses[0].name == "Pork Carnitas"
    assert result.true_dishes == ["Pork Carnitas", "Charro Beans"]  # unknown name left out of scoring
    assert result.top1_hit and result.recall_at_5 == 1.0  # Charro Beans makes the top 5 of 6


def test_evaluate_skips_missing_photo_and_missing_menu(conn, photo_dir):
    photos = [
        LabeledPhoto("gone.jpg", DAY, "yahentamitsi", "Lunch", ["Pork Carnitas"]),
        LabeledPhoto("plate.jpg", date(2026, 1, 1), "yahentamitsi", "Lunch", ["Pork Carnitas"]),
    ]
    assert evaluate(photos, FakeScorer({}), conn, "{name}", photo_dir) == []


def test_summarize_averages_and_handles_empty():
    hit = score_photo("a", guesses("Rice"), ["Rice"])
    miss = score_photo("b", guesses("Rice"), ["Salad"])
    assert summarize([hit, miss]) == {"photos": 2, "top1": 0.5, "top3": 0.5, "recall_at_5": 0.5}
    assert summarize([])["photos"] == 0


def test_append_history_writes_header_once(tmp_path):
    path = tmp_path / "history.csv"
    summary = {"photos": 3, "top1": 2 / 3, "top3": 1.0, "recall_at_5": 0.5}
    append_history(summary, "{name}", DAY, path)
    append_history(summary, "{name}", DAY, path)
    lines = path.read_text().splitlines()
    assert lines[0] == "run_date,template,photos,top1,top3,recall_at_5"
    assert lines[1] == "2026-10-14,{name},3,0.667,1.000,0.500"
    assert len(lines) == 3
