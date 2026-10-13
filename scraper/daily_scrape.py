# The daily scrape: connects the fetcher, the two parsers and the database.
# Run once or twice a day with `python -m scraper.daily_scrape`. It downloads today's
# menu for each hall, saves it, then downloads nutrition labels only for dishes the
# database doesn't have yet (the database is our cache).

import argparse
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from db.database import DEFAULT_DB_PATH, connect, get_menu, has_nutrition, save_menu, save_nutrition
from scraper.fetcher import Fetcher, FetchError
from scraper.label_parser import LabelPageFormatError, NutritionNotAvailableError, parse_label_page
from scraper.menu_parser import MenuItem, MenuPageFormatError, parse_menu_page

# Hall name -> UMD's locationNum (from the hall dropdown on nutrition.umd.edu).
# Adding a hall is one line here; the API picks it up automatically.
HALLS: Dict[str, int] = {"South Campus": 16, "Yahentamitsi": 19}

logger = logging.getLogger(__name__)


class ScrapeError(Exception):
    """Raised when a hall's menu page can't be downloaded or understood.

    The saved menu for that day is left untouched when this happens.
    """


@dataclass
class ScrapeResult:
    """Summary of one hall's scrape, printed at the end of a run.

    Example:
        ScrapeResult(hall="South Campus", menu_entries=533, unique_dishes=304,
                     labels_fetched=12, labels_cached=291, labels_no_data=["090346*6"],
                     labels_failed=[])
    """

    hall: str
    menu_entries: int = 0
    unique_dishes: int = 0
    labels_fetched: int = 0
    labels_cached: int = 0  # already in the database, so not re-downloaded
    labels_no_data: List[str] = field(default_factory=list)  # UMD publishes no nutrition
    labels_failed: List[str] = field(default_factory=list)  # recipe IDs


def scrape_hall(
    conn: sqlite3.Connection, fetcher: Fetcher, hall: str, location_num: int, day: date
) -> ScrapeResult:
    """Scrape one hall's menu for one day and store it, plus any missing nutrition.

    Args:
        conn: Open database connection.
        fetcher: Polite page downloader.
        hall: Hall name stored with the menu, e.g. "South Campus".
        location_num: UMD's ID for the hall, e.g. 16.
        day: Which day's menu to get.

    Returns:
        A ScrapeResult with counts of what was saved, fetched and skipped.

    Raises:
        ScrapeError: if the menu page fails. Nothing is saved in that case.

    Example:
        scrape_hall(conn, Fetcher(), "South Campus", 16, date(2026, 10, 12))
        -> ScrapeResult(hall="South Campus", menu_entries=533, ...)
    """
    try:
        items = parse_menu_page(fetcher.fetch_menu_html(location_num, day))
    except (FetchError, MenuPageFormatError) as error:
        # Stop before save_menu: it replaces the whole day, so saving nothing here
        # would wipe a menu that an earlier run saved successfully.
        raise ScrapeError(f"{hall} menu for {day.isoformat()} failed: {error}") from error

    save_menu(conn, day, hall, items)
    # Count what was actually saved, not what was parsed: UMD sometimes lists one
    # dish at several stations in the same meal, and save_menu keeps just one.
    result = ScrapeResult(hall=hall, menu_entries=len(get_menu(conn, day, hall)))
    _fetch_missing_labels(conn, fetcher, items, result)
    return result


def _fetch_missing_labels(
    conn: sqlite3.Connection, fetcher: Fetcher, items: List[MenuItem], result: ScrapeResult
) -> None:
    """Download and save nutrition for dishes not yet in the database.

    Fills in the label counts on `result`. A failed label is recorded and skipped,
    so one bad dish doesn't stop the rest (it shows up with nutrition=None).
    """
    # A dish served at lunch and dinner appears twice in `items`; fetch it once.
    # dict.fromkeys keeps menu order, unlike set(), so runs are predictable.
    recipe_ids = list(dict.fromkeys(item.recipe_id for item in items))
    result.unique_dishes = len(recipe_ids)

    for recipe_id in recipe_ids:
        if has_nutrition(conn, recipe_id):
            result.labels_cached += 1
            continue
        try:
            label = parse_label_page(fetcher.fetch_label_html(recipe_id))
        except NutritionNotAvailableError:
            # Expected for a few dishes; not saved, so the next run checks again
            # in case UMD adds the data. Must come before the broader except below.
            result.labels_no_data.append(recipe_id)
            continue
        except (FetchError, LabelPageFormatError) as error:
            logger.warning("Skipping label %s: %s", recipe_id, error)
            result.labels_failed.append(recipe_id)
            continue
        save_nutrition(conn, recipe_id, label)
        result.labels_fetched += 1


def format_result(result: ScrapeResult) -> str:
    """Turn a ScrapeResult into a short human-readable summary.

    Example:
        format_result(result)
        -> "South Campus: 533 menu entries, 304 unique dishes | labels: 12 fetched, 291 cached, 1 no data, 0 failed"
    """
    summary = (
        f"{result.hall}: {result.menu_entries} menu entries, {result.unique_dishes} unique dishes"
        f" | labels: {result.labels_fetched} fetched, {result.labels_cached} cached,"
        f" {len(result.labels_no_data)} no data, {len(result.labels_failed)} failed"
    )
    if result.labels_failed:
        summary += f"\n  failed recipe IDs: {', '.join(result.labels_failed)}"
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    """Command-line entry point. Scrapes every hall in HALLS for one day.

    Args:
        argv: Command-line arguments (tests pass a list; normally read from sys.argv).

    Returns:
        Exit code: 0 if every hall's menu saved, 1 if any hall's menu failed.

    Example:
        python -m scraper.daily_scrape --date 2026-10-13
    """
    parser = argparse.ArgumentParser(description="Scrape UMD Dining menus and nutrition.")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today(),
                        help="day to scrape, as YYYY-MM-DD (default: today)")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="database file path")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    conn = connect(args.db)
    fetcher = Fetcher()
    exit_code = 0
    try:
        for hall, location_num in HALLS.items():
            try:
                print(format_result(scrape_hall(conn, fetcher, hall, location_num, args.date)))
            except ScrapeError as error:
                # Keep going so one hall's outage doesn't block the others.
                print(f"ERROR {error}", file=sys.stderr)
                exit_code = 1
    finally:
        conn.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
