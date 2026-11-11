# App settings that change between your laptop and the hosted server. Each setting is
# read from an environment variable when one is set (on the server, the files live on a
# separate disk), and otherwise falls back to the usual folder inside the project, so
# running things locally works exactly as before with nothing to configure.
#
#   MACROS_DB_PATH       the SQLite database file      (default: data/macros.db)
#   MACROS_PHOTO_DIR     saved plate photos            (default: ml/training_photos/)
#   MACROS_FRONTEND_DIR  the built React app to serve  (default: frontend/dist/)
#
# The export and eval tools (ml/export_training_data.py, ml/evaluate.py) use TOOLS_DB_PATH and
# TOOLS_PHOTO_DIR instead: the same variables win, but when they're unset and docker-data/
# exists, they read from it, because that's where the Dockerized app saves real plates.

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def path_from_env(variable: str, default: Path) -> Path:
    """Return the path in an environment variable, or the default if it isn't set.

    Args:
        variable: Environment variable name, e.g. "MACROS_DB_PATH".
        default: Path to use when the variable is missing or empty.

    Example:
        # with MACROS_DB_PATH=/data/macros.db set:
        path_from_env("MACROS_DB_PATH", Path("data/macros.db"))  # -> Path("/data/macros.db")
    """
    # An empty value (MACROS_DB_PATH=) counts as unset, so a blank line in a config
    # file can't make the app use the current folder by accident.
    value = os.environ.get(variable, "").strip()
    return Path(value) if value else default


DB_PATH = path_from_env("MACROS_DB_PATH", PROJECT_ROOT / "data" / "macros.db")
PHOTO_DIR = path_from_env("MACROS_PHOTO_DIR", PROJECT_ROOT / "ml" / "training_photos")
FRONTEND_DIR = path_from_env("MACROS_FRONTEND_DIR", PROJECT_ROOT / "frontend" / "dist")

DOCKER_DATA_DIR = PROJECT_ROOT / "docker-data"


def prefer_docker_data(variable: str, docker_path: Path, local_default: Path) -> Path:
    """Pick the path an offline tool should read: env var, else docker-data if present, else local.

    Example:
        # no env var, docker-data/macros.db exists:
        prefer_docker_data("MACROS_DB_PATH", Path("docker-data/macros.db"), Path("data/macros.db"))
        # -> Path("docker-data/macros.db")
    """
    # Only the offline tools use this. The app and scraper keep DB_PATH so a stray
    # docker-data/ folder can never redirect them.
    return path_from_env(variable, docker_path if docker_path.exists() else local_default)


TOOLS_DB_PATH = prefer_docker_data("MACROS_DB_PATH", DOCKER_DATA_DIR / "macros.db", DB_PATH)
TOOLS_PHOTO_DIR = prefer_docker_data("MACROS_PHOTO_DIR", DOCKER_DATA_DIR / "photos", PHOTO_DIR)
