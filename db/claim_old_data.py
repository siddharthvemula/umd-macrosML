# One-time script: gives the meal logs and photos saved before devices existed (their
# device_id is NULL, so nobody sees them) to one device, so its owner gets their history
# back. You pass the 8-character device code from the app's Privacy footer; the script
# finds the full device ID in the database (that device must have logged something
# already). Run it against the database the app actually uses:
#   .venv/bin/python -m db.claim_old_data 3f2a9c1e
#   MACROS_DB_PATH=/data/macros.db python -m db.claim_old_data 3f2a9c1e   # on the server

import argparse
import re
import sqlite3
import sys
import uuid

from db.database import DEFAULT_DB_PATH, connect

DEVICE_CODE = re.compile(r"^[0-9a-f]{8}$")


class DeviceNotFoundError(Exception):
    """The code matches no device (or several), so we don't know whose data to assign."""


def find_device_id(conn: sqlite3.Connection, code: str) -> str:
    """Turn a device code from the Privacy footer (or a full device ID) into the full ID.

    Args:
        code: 8 hex characters, e.g. "3f2a9c1e", or a whole UUID.

    Returns:
        The full device ID, e.g. "3f2a9c1e-7b4d-4e8a-9c2f-1a2b3c4d5e6f".

    Raises:
        DeviceNotFoundError: if the code is malformed, no device with that code has
            logged anything yet, or (very unlikely) two devices share the code.

    Example:
        find_device_id(conn, "3F2A9C1E")  # -> "3f2a9c1e-7b4d-..."
    """
    code = code.strip().lower()
    try:
        return str(uuid.UUID(code))  # a full ID needs no lookup
    except ValueError:
        pass
    # Only hex is allowed, which also means the code can't contain LIKE's % or _ wildcards.
    if not DEVICE_CODE.match(code):
        raise DeviceNotFoundError(f"'{code}' isn't a device code (8 letters/digits, 0-9 and a-f).")

    rows = conn.execute(
        """
        SELECT device_id FROM meal_logs WHERE device_id LIKE ? || '%'
        UNION
        SELECT device_id FROM photos WHERE device_id LIKE ? || '%'
        """,
        (code, code),
    ).fetchall()
    if not rows:
        raise DeviceNotFoundError(
            f"No device with code {code} has logged anything in this database. "
            "Log one dish from the app on that device first, then run this again."
        )
    if len(rows) > 1:
        raise DeviceNotFoundError(f"Several devices start with {code}; pass the full device ID.")
    return rows[0]["device_id"]


def claim_unowned_data(conn: sqlite3.Connection, device_id: str) -> tuple[int, int]:
    """Assign every meal log and photo that has no device to `device_id`.

    Rows that already belong to a device are never touched, so running this twice is safe
    (the second run assigns nothing).

    Returns:
        (meal logs assigned, photos assigned), e.g. (14, 6).

    Example:
        claim_unowned_data(conn, "3f2a9c1e-...")  # -> (14, 6)
    """
    # One transaction: either both tables are updated or neither is.
    with conn:
        logs = conn.execute(
            "UPDATE meal_logs SET device_id = ? WHERE device_id IS NULL", (device_id,)
        ).rowcount
        photos = conn.execute(
            "UPDATE photos SET device_id = ? WHERE device_id IS NULL", (device_id,)
        ).rowcount
    return logs, photos


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the exit code (0 ok, 1 device not found).

    Example:
        main(["3f2a9c1e", "--db", "data/macros.db"])  # prints the counts, returns 0
    """
    parser = argparse.ArgumentParser(description="Give pre-device meal logs and photos to one device.")
    parser.add_argument("device_code", help="8-character code from the app's Privacy footer, or a full device ID")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="database file path")
    args = parser.parse_args(argv)

    conn = connect(args.db)
    try:
        device_id = find_device_id(conn, args.device_code)
        logs, photos = claim_unowned_data(conn, device_id)
    except DeviceNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"Assigned {logs} meal logs and {photos} photos to device {device_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
