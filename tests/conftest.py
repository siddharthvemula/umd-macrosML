# Shared pytest fixtures for the API tests (pytest loads this file automatically).
# `client` is a TestClient whose requests use a temporary database file, a temporary
# photo folder, a fixed "today" and one device's X-Device-Id header, swapped in through FastAPI's dependency_overrides,
# so API tests never touch the real database, real training photos, or the real clock.

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db, get_photo_dir, get_today
from api.main import app
from db.database import connect

TODAY = date(2026, 10, 12)
# The device every `client` request comes from (sent as the X-Device-Id header).
DEVICE = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def db_path(tmp_path):
    """Path to a fresh, empty database file for this test (pytest deletes tmp_path after)."""
    path = str(tmp_path / "test.db")
    connect(path).close()  # creates the tables
    return path


@pytest.fixture
def photo_dir(tmp_path):
    """A temp folder for saved plate photos (doesn't exist until a photo is saved)."""
    return tmp_path / "photos"


@pytest.fixture
def client(db_path, photo_dir):
    """A TestClient using the test database, the temp photo folder, and a date of TODAY."""

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
    app.dependency_overrides[get_photo_dir] = lambda: photo_dir
    # headers= is sent with every request, like the real frontend does.
    yield TestClient(app, headers={"X-Device-Id": DEVICE})
    app.dependency_overrides.clear()  # don't leak fakes into other test files
