# Shared pytest fixtures for the API tests (pytest loads this file automatically).
# `client` is a TestClient whose requests use a temporary database file and a fixed
# "today", swapped in through FastAPI's dependency_overrides, so API tests never
# touch the real database or the real clock.

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db, get_today
from api.main import app
from db.database import connect

TODAY = date(2026, 10, 12)


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
