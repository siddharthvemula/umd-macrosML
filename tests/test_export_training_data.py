# Tests for get_photo_labels (db/database.py) and ml/export_training_data.py: turning
# photos + the dishes logged from them into a labels.csv-style file. Uses a temp database
# and a temp output file; no real photos are needed because only filenames are exported.

from datetime import date

import pytest

from db.database import connect, get_photo_labels, log_meal, save_nutrition, save_photo
from ml.evaluate import read_labels
from ml.export_training_data import export_training_data
from scraper.label_parser import NutritionLabel

DAY = date(2026, 10, 15)


def make_label(name: str) -> NutritionLabel:
    """A minimal nutrition label so the dish can be logged."""
    return NutritionLabel(
        name=name, serving_size="1 each", calories=100.0, protein_g=1.0, carbs_g=1.0,
        fat_g=1.0, sat_fat_g=None, sugar_g=None, fiber_g=None, sodium_mg=None,
        ingredients="", allergens=[],
    )


@pytest.fixture
def conn():
    """An in-memory database where "Spanish Rice" (1*1) and "Salsa, Roja" (2*1) can be logged."""
    connection = connect(":memory:")
    save_nutrition(connection, "1*1", make_label("Spanish Rice"))
    save_nutrition(connection, "2*1", make_label("Salsa, Roja"))  # comma on purpose
    yield connection
    connection.close()


def test_photo_labels_group_dishes_per_photo_without_repeats(conn):
    lunch = save_photo(conn, DAY, "Yahentamitsi", "Lunch", "a.jpg")
    log_meal(conn, DAY, "1*1", 1, photo_id=lunch)
    log_meal(conn, DAY, "2*1", 1, photo_id=lunch)
    log_meal(conn, DAY, "1*1", 0.5, photo_id=lunch)  # rice logged twice: one label

    [labels] = get_photo_labels(conn)
    assert (labels.filename, labels.meal, labels.dishes) == ("a.jpg", "Lunch", ["Spanish Rice", "Salsa, Roja"])


def test_unlogged_photos_and_menu_logs_are_left_out(conn):
    save_photo(conn, DAY, "Yahentamitsi", "Lunch", "nobody-logged-this.jpg")
    log_meal(conn, DAY, "1*1", 1)  # from the menu, no photo

    assert get_photo_labels(conn) == []


def test_export_round_trips_through_evaluates_reader(conn, tmp_path):
    photo = save_photo(conn, DAY, "Yahentamitsi", None, "a.jpg")  # meal "Any"
    log_meal(conn, DAY, "2*1", 1, photo_id=photo)
    path = tmp_path / "labels.csv"

    assert export_training_data(conn, path) == 1
    # evaluate.py must read our file exactly like a hand-written labels.csv.
    [row] = read_labels(path)
    assert (row.photo, row.day, row.hall, row.meal, row.dishes) == ("a.jpg", DAY, "Yahentamitsi", "", ["Salsa, Roja"])


def test_export_with_no_labels_writes_just_the_header(conn, tmp_path):
    path = tmp_path / "labels.csv"
    assert export_training_data(conn, path) == 0
    assert path.read_text().strip() == "photo,date,hall,meal,dishes,notes"
