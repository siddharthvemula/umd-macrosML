# Shared "dependencies" that FastAPI hands to endpoints: a database connection and
# today's date. Endpoints ask for them as parameters instead of creating them, so
# tests can swap in a test database or a fixed date (app.dependency_overrides).

import sqlite3
from datetime import date, datetime
from typing import Iterator
from zoneinfo import ZoneInfo

from db.database import DEFAULT_DB_PATH, connect

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
