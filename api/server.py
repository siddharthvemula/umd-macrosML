# The production server: one web address that serves both the built React app and the
# API. The API (api/main.py) is mounted under /api, the same paths the frontend already
# calls through Vite's dev proxy, so the browser sees one origin and we still need no CORS.
# Locally you keep using `uvicorn api.main:app --reload` + `npm run dev`. On the server:
#   cd frontend && npm run build && cd ..
#   .venv/bin/uvicorn api.server:create_server --factory --host 0.0.0.0 --port 8080

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.main import app as api_app
from config import FRONTEND_DIR


def create_server(frontend_dir: Path | None = None) -> FastAPI:
    """Build the app that serves the API at /api/* and the React files at everything else.

    A function (uvicorn's --factory option calls it) instead of a module-level object, so
    importing this file never fails just because the frontend hasn't been built yet.

    Args:
        frontend_dir: Folder with the built frontend (index.html + assets/).
            Defaults to config.FRONTEND_DIR (frontend/dist, or MACROS_FRONTEND_DIR).

    Returns:
        The combined FastAPI app.

    Raises:
        RuntimeError: if the folder has no index.html, i.e. `npm run build` wasn't run.

    Example:
        server = create_server(Path("frontend/dist"))
        # GET /api/halls -> the API's /halls;  GET / -> frontend/dist/index.html
    """
    frontend_dir = frontend_dir or FRONTEND_DIR
    if not (frontend_dir / "index.html").is_file():
        raise RuntimeError(
            f"No built frontend in {frontend_dir}. Run `npm run build` in frontend/ first."
        )

    server = FastAPI(title="UMD Dining Macro Tracker", docs_url=None, redoc_url=None)
    # Order matters: mounts are checked top to bottom, so /api must come before the
    # catch-all "/" or the React files would swallow every API request.
    server.mount("/api", api_app)
    # html=True serves index.html for "/", like a normal website.
    server.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return server
