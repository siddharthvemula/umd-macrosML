# Evaluation script for the plate recognizer (Phase 4 Step 3).
# Runs ml/recognizer.py on our labeled photos (ml/eval_photos/labels.csv), compares its
# guesses with what was really on each plate, and reports top-1 / top-3 / recall@5 for
# a few prompt wordings. Each run is appended to ml/eval_history.csv so we can watch the
# numbers change as more photos are labeled.
#
# Run: .venv/bin/python -m ml.evaluate
#      .venv/bin/python -m ml.evaluate --training   (photos logged in the app; run
#      ml.export_training_data first)

import argparse
import csv
import difflib
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from db.database import DEFAULT_DB_PATH, connect, get_menu
from ml.export_training_data import TRAINING_LABELS_PATH
from ml.photo_store import DEFAULT_PHOTO_DIR
from ml.recognizer import BadPhotoError, Guess, ImageTextScorer, load_photo, rank_menu_items

EVAL_DIR = Path(__file__).parent / "eval_photos"
LABELS_PATH = EVAL_DIR / "labels.csv"
HISTORY_PATH = Path(__file__).parent / "eval_history.csv"
HISTORY_COLUMNS = ["run_date", "template", "photos", "top1", "top3", "recall_at_5"]

# Wordings to compare. The last one is recognizer.DEFAULT_TEMPLATE.
TEMPLATES = [
    "{name}",
    "a photo of {name}",
    "a photo of {name}, a dining hall dish",
]


@dataclass
class LabeledPhoto:
    """One row of labels.csv: a photo and the dishes that were really on the plate."""

    photo: str
    day: date
    hall: str
    meal: str
    dishes: list[str]


@dataclass
class PhotoResult:
    """How the recognizer did on one photo."""

    photo: str
    guesses: list[Guess]
    true_dishes: list[str]
    top1_hit: bool  # the #1 guess is on the plate
    top3_hit: bool  # at least one of the top 3 is on the plate
    recall_at_5: float  # share of the plate's dishes found in the top 5


def read_labels(path: Path = LABELS_PATH) -> list[LabeledPhoto]:
    """Read labels.csv, skipping photos whose menu we don't have.

    Args:
        path: the labels file (columns: photo,date,hall,meal,dishes,notes).

    Returns:
        One LabeledPhoto per usable row, in file order. Rows whose notes start with
        "menu unavailable" are skipped (we can't score guesses with no candidate list).

    Example:
        read_labels()[0].dishes  # -> ["Greek Pita Flat Bread", "Shredded Lettuce", ...]
    """
    photos = []
    with open(path, newline="") as file:
        for row in csv.DictReader(file):
            if row["notes"].strip().lower().startswith("menu unavailable"):
                print(f"Skipping {row['photo']}: menu unavailable")
                continue
            # ";" separates dishes because some dish names contain commas.
            dishes = [name.strip() for name in row["dishes"].split(";") if name.strip()]
            photos.append(
                LabeledPhoto(
                    photo=row["photo"],
                    day=date.fromisoformat(row["date"]),
                    hall=row["hall"],
                    meal=row["meal"],
                    dishes=dishes,
                )
            )
    return photos


def load_candidates(conn: sqlite3.Connection, day: date, hall: str, meal: str) -> list[str]:
    """Get the dish names on one meal's stored menu: the recognizer's candidate list.

    Like POST /recognize, only dishes with nutrition count: the app never guesses a dish
    it can't log, so scoring against those would measure a different problem.

    Args:
        day: the menu date.
        hall: hall name in any capitalization (labels say "yahentamitsi", the DB "Yahentamitsi").
        meal: meal name, e.g. "Lunch", or "" for the whole day (photos taken with meal
            "Any" in the app, where the recognizer also used the whole day's menu).

    Returns:
        Unique dish names in menu order. [] if nothing is stored (or nothing has nutrition).

    Example:
        load_candidates(conn, date(2026, 10, 14), "yahentamitsi", "Lunch")  # -> ["Spanish Rice", ...]
    """
    rows = [
        row
        for row in get_menu(conn, day, _stored_hall_name(conn, hall))
        if row.nutrition is not None and (not meal or row.meal.lower() == meal.lower())
    ]
    return list(dict.fromkeys(row.name for row in rows))


def _stored_hall_name(conn: sqlite3.Connection, hall: str) -> str:
    """Return the hall name as the database spells it, e.g. "yahentamitsi" -> "Yahentamitsi"."""
    stored = [row[0] for row in conn.execute("SELECT DISTINCT hall FROM menu_entries")]
    return next((name for name in stored if name.lower() == hall.lower()), hall)


def find_unknown_dishes(labeled: list[str], candidates: list[str]) -> list[str]:
    """Return labeled dish names that aren't on the menu (usually a typo in labels.csv).

    Args:
        labeled: dish names from labels.csv.
        candidates: dish names on that meal's stored menu.

    Returns:
        The labeled names with no exact match, in label order.

    Example:
        find_unknown_dishes(["Rice", "Salsa"], ["Rice", "Salsa Roja"])  # -> ["Salsa"]
    """
    menu = set(candidates)
    return [name for name in labeled if name not in menu]


def score_photo(photo: str, guesses: list[Guess], true_dishes: list[str]) -> PhotoResult:
    """Compare ranked guesses with the plate's real dishes.

    Args:
        photo: photo file name (kept for the report).
        guesses: recognizer output, best first (at least 5 for a full recall@5).
        true_dishes: dishes really on the plate; must not be empty.

    Returns:
        A PhotoResult with top-1 hit, top-3 hit, and recall@5.

    Example:
        score_photo("a.jpg", [Guess("Rice", 0.6), Guess("Salad", 0.3)], ["Salad"])
        # -> top1_hit=False, top3_hit=True, recall_at_5=1.0
    """
    on_plate = set(true_dishes)
    names = [guess.name for guess in guesses]
    found_in_top5 = on_plate.intersection(names[:5])
    return PhotoResult(
        photo=photo,
        guesses=guesses,
        true_dishes=true_dishes,
        top1_hit=bool(names) and names[0] in on_plate,
        top3_hit=bool(on_plate.intersection(names[:3])),
        recall_at_5=len(found_in_top5) / len(on_plate),
    )


def evaluate(
    photos: list[LabeledPhoto],
    scorer: ImageTextScorer,
    conn: sqlite3.Connection,
    template: str,
    photo_dir: Path = EVAL_DIR,
) -> list[PhotoResult]:
    """Run the recognizer on every labeled photo with one prompt wording.

    Photos are skipped with a printed reason (not a crash) when the file is missing or
    unreadable, no menu is stored, or none of the labeled dishes are on the menu.
    Labeled dishes that aren't on the menu are left out of scoring, with a warning.

    Args:
        photos: from read_labels.
        scorer: ClipScorer for a real run, a fake in tests.
        conn: database with the stored menus.
        template: prompt wording with a {name} slot.
        photo_dir: folder holding the photo files.

    Returns:
        One PhotoResult per photo that could be scored.

    Example:
        evaluate(read_labels(), ClipScorer(), conn, "a photo of {name}")[0].top1_hit  # -> True
    """
    results = []
    for labeled in photos:
        candidates = load_candidates(conn, labeled.day, labeled.hall, labeled.meal)
        if not candidates:
            print(f"Skipping {labeled.photo}: no {labeled.meal or 'day'} dishes with nutrition stored for {labeled.day}")
            continue

        unknown = find_unknown_dishes(labeled.dishes, candidates)
        for name in unknown:
            close = difflib.get_close_matches(name, candidates, n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            print(f"Warning: {labeled.photo}: '{name}' is not on the menu or has no nutrition{hint}; not scored")
        true_dishes = [name for name in labeled.dishes if name not in unknown]
        if not true_dishes:
            print(f"Skipping {labeled.photo}: none of its labeled dishes are on the menu")
            continue

        try:
            image = load_photo((photo_dir / labeled.photo).read_bytes())
        except (FileNotFoundError, BadPhotoError) as error:
            print(f"Skipping {labeled.photo}: {error}")
            continue

        guesses = rank_menu_items(image, candidates, scorer, top_k=5, template=template)
        results.append(score_photo(labeled.photo, guesses, true_dishes))
    return results


def summarize(results: list[PhotoResult]) -> dict[str, float]:
    """Average the per-photo results.

    Returns:
        {"photos": n, "top1": share, "top3": share, "recall_at_5": mean}; all 0 if empty.

    Example:
        summarize([hit_result, miss_result])  # -> {"photos": 2, "top1": 0.5, ...}
    """
    count = len(results)
    if count == 0:
        return {"photos": 0, "top1": 0.0, "top3": 0.0, "recall_at_5": 0.0}
    return {
        "photos": count,
        "top1": sum(r.top1_hit for r in results) / count,
        "top3": sum(r.top3_hit for r in results) / count,
        "recall_at_5": sum(r.recall_at_5 for r in results) / count,
    }


def append_history(summary: dict[str, float], template: str, run_date: date, path: Path = HISTORY_PATH) -> None:
    """Add one row for this run and wording to the history CSV (writing the header if new).

    Example:
        append_history({"photos": 3, "top1": 0.67, ...}, "{name}", date(2026, 10, 15))
    """
    is_new = not path.exists()
    with open(path, "a", newline="") as file:
        writer = csv.writer(file)
        if is_new:
            writer.writerow(HISTORY_COLUMNS)
        writer.writerow([
            run_date.isoformat(),
            template,
            summary["photos"],
            f"{summary['top1']:.3f}",
            f"{summary['top3']:.3f}",
            f"{summary['recall_at_5']:.3f}",
        ])


def print_report(template: str, results: list[PhotoResult]) -> None:
    """Print one wording's summary, then each photo's top 5 with ✓ (on plate) or ✗."""
    summary = summarize(results)
    print(f"\n=== Template: {template!r}  (n={summary['photos']} photos) ===")
    print(
        f"top-1 {summary['top1']:.0%}   top-3 {summary['top3']:.0%}   "
        f"recall@5 {summary['recall_at_5']:.0%}"
    )
    for result in results:
        print(f"\n  {result.photo}  ({len(result.true_dishes)} dishes on plate)")
        for rank, guess in enumerate(result.guesses, start=1):
            mark = "✓" if guess.name in result.true_dishes else "✗"
            print(f"    {rank}. {mark} {guess.score:.3f}  {guess.name}")


def main() -> None:
    """Evaluate every prompt wording on all labeled photos and log the results."""
    from ml.recognizer import ClipScorer  # here so tests importing this file don't need CLIP

    parser = argparse.ArgumentParser(description="Score the plate recognizer on labeled photos.")
    parser.add_argument(
        "--training", action="store_true",
        help="use photos logged in the app (ml/training_photos/) instead of ml/eval_photos/",
    )
    args = parser.parse_args()
    labels_path, photo_dir = (TRAINING_LABELS_PATH, DEFAULT_PHOTO_DIR) if args.training else (LABELS_PATH, EVAL_DIR)

    if not labels_path.exists():
        print(f"No {labels_path}. Run: .venv/bin/python -m ml.export_training_data")
        return
    photos = read_labels(labels_path)
    if not photos:
        print(f"No usable labeled photos in {labels_path.name} yet.")
        return

    conn = connect(str(DEFAULT_DB_PATH))
    scorer = ClipScorer()  # load once (~600 MB), reuse for every photo and wording
    for template in TEMPLATES:
        results = evaluate(photos, scorer, conn, template, photo_dir)
        print_report(template, results)
        # eval_history.csv tracks the hand-labeled set only, so its trend compares like with like.
        if not args.training:
            append_history(summarize(results), template, date.today())
    conn.close()
    print(f"\nAppended results to {HISTORY_PATH.name}")


if __name__ == "__main__":
    main()
