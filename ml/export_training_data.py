# Exports the training labels collected by the app (Phase 4 Step 6) to a CSV.
# Every plate photo POST /recognize saved, plus the dishes logged from it, becomes one
# row in the same format as ml/eval_photos/labels.csv, so ml/evaluate.py can score CLIP
# on real use (`--training`) and Phase 5 fine-tuning can read the same file.
#
# Run: .venv/bin/python -m ml.export_training_data

import csv
import sqlite3
from pathlib import Path

from db.database import DEFAULT_DB_PATH, PhotoLabels, connect, get_photo_labels
from ml.photo_store import DEFAULT_PHOTO_DIR

# Next to the photos, so it's gitignored with them (the dish names alone aren't private,
# but the file is useless without the photos, and it's rebuilt from the database anyway).
TRAINING_LABELS_PATH = DEFAULT_PHOTO_DIR / "labels.csv"
COLUMNS = ["photo", "date", "hall", "meal", "dishes", "notes"]


def to_csv_row(labels: PhotoLabels) -> dict[str, str]:
    """Turn one photo's labels into a labels.csv row.

    Example:
        to_csv_row(PhotoLabels(1, "3f2a.jpg", date(2026, 10, 15), "Yahentamitsi", None,
                               ["Spanish Rice", "Guacamole"]))
        # -> {"photo": "3f2a.jpg", "date": "2026-10-15", "hall": "Yahentamitsi", "meal": "",
        #     "dishes": "Spanish Rice;Guacamole", "notes": "photo_id 1"}
    """
    return {
        "photo": labels.filename,
        "date": labels.date.isoformat(),
        "hall": labels.hall,
        # "" = the whole day's menu was used; evaluate.py reads it the same way.
        "meal": labels.meal or "",
        # ";" like labels.csv, because some dish names contain commas.
        "dishes": ";".join(labels.dishes),
        # The id lets us trace a row back to the database when something looks wrong.
        "notes": f"photo_id {labels.photo_id}",
    }


def export_training_data(conn: sqlite3.Connection, path: Path = TRAINING_LABELS_PATH) -> int:
    """Write every labeled photo to `path`, replacing the old file.

    The database is the source of truth, so the file is rebuilt from scratch each time
    (a deleted log disappears from the export too).

    Returns:
        How many photos were written.

    Example:
        export_training_data(conn)  # -> 12, and ml/training_photos/labels.csv has 12 rows
    """
    rows = [to_csv_row(labels) for labels in get_photo_labels(conn)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    """Export from the real database and say how many photos were written."""
    conn = connect(str(DEFAULT_DB_PATH))
    count = export_training_data(conn)
    conn.close()
    print(f"Wrote {count} labeled photo(s) to {TRAINING_LABELS_PATH}")


if __name__ == "__main__":
    main()
