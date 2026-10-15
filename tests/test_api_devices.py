# Tests for "one user per device": every meal/photo endpoint needs a valid X-Device-Id
# header, each device only sees and changes its own logs and photos, and one device can
# save at most MAX_PHOTOS_PER_DAY photos a day. `client` (conftest.py) sends DEVICE's
# header by default; passing headers= to a request switches to another device.

import pytest

import api.main
from conftest import TODAY
from db.database import connect, save_photo
from test_api_meals import BANANA_ID, seed_banana
from test_api_recognize import png_bytes, post_photo, scorer, seed_menu  # noqa: F401 (fixture)

OTHER = {"X-Device-Id": "22222222-2222-4222-8222-222222222222"}


@pytest.mark.parametrize("headers", [{"X-Device-Id": ""}, {"X-Device-Id": "not-a-uuid"}])
def test_missing_or_invalid_device_id_is_400(client, headers):
    response = client.get("/meals", headers=headers)
    assert response.status_code == 400
    assert "X-Device-Id" in response.json()["detail"]


def test_device_id_spelling_does_not_matter(client, db_path):
    seed_banana(db_path)
    client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 1})
    upper = {"X-Device-Id": "11111111-1111-4111-8111-111111111111".upper()}
    assert len(client.get("/meals", headers=upper).json()) == 1


def test_menu_endpoints_need_no_device_id(client):
    # Menus are public: same for everyone, nothing personal in them.
    assert client.get("/halls", headers={"X-Device-Id": ""}).status_code == 200


def test_other_devices_cannot_see_or_delete_my_logs(client, db_path):
    seed_banana(db_path)
    log_id = client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 2}).json()["id"]

    assert client.get("/meals", headers=OTHER).json() == []
    assert client.get("/summary", headers=OTHER).json()["meal_count"] == 0
    assert client.delete(f"/meals/{log_id}", headers=OTHER).status_code == 404
    assert len(client.get("/meals").json()) == 1  # still there for me


def test_cannot_label_another_devices_photo(client, db_path):
    seed_banana(db_path)
    conn = connect(db_path)
    photo_id = save_photo(conn, TODAY, "Yahentamitsi", "Lunch", "a.jpg", device_id="someone-else")
    conn.close()
    response = client.post("/meals", json={"recipe_id": BANANA_ID, "servings": 1, "photo_id": photo_id})
    assert response.status_code == 404


def test_daily_photo_cap_is_per_device(client, db_path, photo_dir, scorer, monkeypatch):
    monkeypatch.setattr(api.main, "MAX_PHOTOS_PER_DAY", 2)  # 2 instead of 20 keeps it quick
    seed_menu(db_path)
    for _ in range(2):
        assert post_photo(client, png_bytes()).status_code == 200

    blocked = post_photo(client, png_bytes())
    assert blocked.status_code == 429
    assert "limit" in blocked.json()["detail"]
    assert len(list(photo_dir.iterdir())) == 2  # the blocked photo wasn't saved
    # Another student isn't affected by my uploads.
    other = client.post(
        "/recognize", files={"photo": ("p.png", png_bytes(), "image/png")},
        data={"hall": "yahentamitsi"}, headers=OTHER,
    )
    assert other.status_code == 200
