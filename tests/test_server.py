# Tests for the production server (api/server.py) and GET /health: the API answers under
# /api, the React files are served everywhere else, and a missing frontend build gives a
# clear error. A tiny fake "build" folder stands in for frontend/dist.

import pytest
from fastapi.testclient import TestClient

from api.server import create_server


@pytest.fixture
def frontend_dir(tmp_path):
    """A fake built frontend: just an index.html."""
    folder = tmp_path / "dist"
    folder.mkdir()
    (folder / "index.html").write_text("<h1>Macro Tracker</h1>")
    return folder


def test_health_says_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_is_served_under_api_prefix(client, frontend_dir):
    # `client` is used only for its database/date overrides, which the mounted API shares.
    server = TestClient(create_server(frontend_dir))
    assert server.get("/api/health").json() == {"status": "ok"}
    assert server.get("/api/halls").status_code == 200


def test_frontend_is_served_at_the_root(frontend_dir):
    server = TestClient(create_server(frontend_dir))
    response = server.get("/")
    assert response.status_code == 200
    assert "Macro Tracker" in response.text


def test_missing_frontend_build_gives_a_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="npm run build"):
        create_server(tmp_path / "no_such_folder")
