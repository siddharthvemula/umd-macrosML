# Tests for db/claim_old_data.py: finding a device from its short code, and giving it
# the logs/photos that have no device, without touching anyone else's.

from datetime import date

import pytest

from conftest import DEVICE
from db.claim_old_data import DeviceNotFoundError, claim_unowned_data, find_device_id, main
from db.database import connect, get_meal_logs, log_meal, photo_exists, save_nutrition, save_photo
from scraper.label_parser import NutritionLabel

DAY = date(2026, 10, 12)
OTHER = "22222222-2222-4222-8222-222222222222"
BANANA = NutritionLabel(
    name="Banana", serving_size="1 each", calories=109.8, protein_g=1.3, carbs_g=28.2,
    fat_g=0.4, sat_fat_g=None, sugar_g=None, fiber_g=None, sodium_mg=None,
    ingredients="", allergens=[],
)


@pytest.fixture
def conn():
    """A fresh in-memory DB with one old (no-device) log + photo, and one log each for DEVICE and OTHER."""
    db = connect(":memory:")
    save_nutrition(db, "111*1", BANANA)
    # Old rows from before devices existed: device_id NULL.
    db.execute("INSERT INTO photos (date, hall, filename) VALUES ('2026-10-12', 'Yahentamitsi', 'old.jpg')")
    db.execute(
        "INSERT INTO meal_logs (date, recipe_id, name, servings, calories, protein_g, carbs_g, fat_g)"
        " VALUES ('2026-10-12', '111*1', 'Banana', 1, 109.8, 1.3, 28.2, 0.4)"
    )
    db.commit()
    log_meal(db, DAY, "111*1", 2, device_id=DEVICE)
    log_meal(db, DAY, "111*1", 3, device_id=OTHER)
    yield db
    db.close()


def test_short_code_finds_the_full_device_id(conn):
    assert find_device_id(conn, DEVICE[:8]) == DEVICE
    assert find_device_id(conn, DEVICE[:8].upper() + " ") == DEVICE  # typed sloppily


def test_full_device_id_is_accepted_as_is(conn):
    assert find_device_id(conn, DEVICE.upper()) == DEVICE


@pytest.mark.parametrize("code", ["99999999", "not-hex!", "1111%"])
def test_unknown_or_malformed_code_is_an_error(conn, code):
    with pytest.raises(DeviceNotFoundError):
        find_device_id(conn, code)


def test_old_rows_go_to_the_device_and_others_are_untouched(conn):
    assert claim_unowned_data(conn, DEVICE) == (1, 1)

    assert [log.servings for log in get_meal_logs(conn, DAY, device_id=DEVICE)] == [1, 2]
    assert [log.servings for log in get_meal_logs(conn, DAY, device_id=OTHER)] == [3]
    photo_id = conn.execute("SELECT id FROM photos WHERE filename = 'old.jpg'").fetchone()[0]
    assert photo_exists(conn, photo_id, device_id=DEVICE)


def test_running_it_twice_assigns_nothing_the_second_time(conn):
    claim_unowned_data(conn, DEVICE)
    assert claim_unowned_data(conn, OTHER) == (0, 0)


def test_command_line_run(tmp_path, capsys):
    path = str(tmp_path / "test.db")
    db = connect(path)
    save_photo(db, DAY, "Yahentamitsi", None, "new.jpg", device_id=DEVICE)
    db.execute("INSERT INTO photos (date, hall, filename) VALUES ('2026-10-12', 'Yahentamitsi', 'old.jpg')")
    db.commit()
    db.close()

    assert main([DEVICE[:8], "--db", path]) == 0
    assert "Assigned 0 meal logs and 1 photos" in capsys.readouterr().out
    assert main(["99999999", "--db", path]) == 1
