# Shared "dependencies" that FastAPI hands to endpoints: a database connection,
# today's date, the CLIP photo scorer, the folder for saved plate photos, and which
# device (phone/browser) is asking, so each student only sees their own meals. Endpoints
# ask for them as parameters instead of creating them, so tests can swap in a test
# database, a fixed date, a fake scorer, or a temp folder (app.dependency_overrides).

import sqlite3
import uuid
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

from fastapi import Header, HTTPException

from db.database import DEFAULT_DB_PATH, connect
from ml.photo_store import DEFAULT_PHOTO_DIR
from ml.recognizer import ClipScorer, ImageTextScorer

# UMD's dining halls run on Eastern time. A server hosted elsewhere (often UTC) would
# otherwise flip to "tomorrow's" menu at 8pm here.
CAMPUS_TIMEZONE = ZoneInfo("America/New_York")


def get_db() -> Iterator[sqlite3.Connection]:
    """Open a database connection for one request and close it when the request ends.

    Yields:
        An open connection (FastAPI runs the code after `yield` once the response is sent).

    Example:
        def read_menu(conn: sqlite3.Connection = Depends(get_db)): ...
    """
    # FastAPI may run this dependency and the endpoint on different worker threads, so
    # sqlite3's same-thread check would wrongly fail. It's safe to turn off because
    # each request gets its own connection that no other request ever touches.
    conn = connect(str(DEFAULT_DB_PATH), check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


def get_today() -> date:
    """Return today's date on campus (Eastern time), not the server's local date.

    Example:
        get_today()  # -> date(2026, 10, 12) at 11pm Eastern, even if UTC is already the 13th
    """
    return datetime.now(CAMPUS_TIMEZONE).date()


# maxsize=1: the first call loads CLIP, and every later call returns that same object.
@lru_cache(maxsize=1)
def get_scorer() -> ImageTextScorer:
    """Return the CLIP scorer, loading it on the first photo instead of at server start.

    Loading takes a few seconds and ~600 MB of memory, so it happens once and is reused.
    The server still starts instantly, and the menu/meal endpoints never pay for it.

    Example:
        def recognize_photo(scorer: ImageTextScorer = Depends(get_scorer)): ...
    """
    return ClipScorer()


def get_photo_dir() -> Path:
    """Return the folder where plate photos are saved as training data.

    Example:
        get_photo_dir()  # -> Path(".../ml/training_photos")
    """
    return DEFAULT_PHOTO_DIR


def get_device_id(x_device_id: str | None = Header(None)) -> str:
    """Read which device is making the request from its X-Device-Id header.

    The browser makes a random ID (a UUID) the first time the app opens, keeps it, and
    sends it with every request (frontend/src/device.js). There are no passwords: the ID
    only keeps one student's meals apart from another's.

    Args:
        x_device_id: FastAPI fills this from the "X-Device-Id" header (it turns the
            underscores into dashes for us).

    Returns:
        The ID in standard lowercase UUID form.

    Raises:
        HTTPException 400: if the header is missing or isn't a UUID.

    Example:
        get_device_id("3F2A9C1E-...")  # -> "3f2a9c1e-..."
    """
    try:
        # Parsing rejects junk (and very long strings) before it reaches the database,
        # and str() gives one spelling, so "ABC..." and "abc..." are the same device.
        return str(uuid.UUID(x_device_id or ""))
    except ValueError as error:
        raise HTTPException(
            status_code=400, detail="Missing or invalid X-Device-Id header. Try reloading the app."
        ) from error
