# Tests for scraper/daily_scrape.py. A fake session serves our saved fixture pages
# by URL and the database is in-memory, so the whole pipeline runs offline and fast.

from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import pytest
import requests

from db.database import connect, get_menu, has_nutrition, save_menu
from scraper.daily_scrape import ScrapeError, format_result, scrape_hall
from scraper.fetcher import Fetcher, build_label_url, build_menu_url
from scraper.menu_parser import MenuItem

FIXTURES = Path(__file__).parent / "fixtures"
DAY = date(2026, 10, 12)
HALL = "South Campus"
LOCATION = 16
CHICKEN_BURGER_ID = "080603*4"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeResponse:
    """Pretends to be a requests.Response with a given status code and body."""

    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class RoutingSession:
    """Pretends to be a requests.Session that serves different pages per URL.

    Exact URLs in `pages` win. Any other label URL gets `default_label` (so we
    don't need 300 label fixtures). Anything else is a 404.
    """

    def __init__(self, pages: Dict[str, FakeResponse], default_label: Optional[str] = None) -> None:
        self.headers = {}
        self.pages = pages
        self.default_label = default_label
        self.requested_urls: List[str] = []

    def get(self, url: str, timeout: float) -> FakeResponse:
        self.requested_urls.append(url)
        if url in self.pages:
            return self.pages[url]
        if self.default_label is not None and "label.aspx" in url:
            return FakeResponse(200, self.default_label)
        return FakeResponse(404)


def make_fetcher(session: RoutingSession) -> Fetcher:
    """A Fetcher with no delay, so tests don't wait."""
    return Fetcher(session=session, delay_seconds=0, sleep=lambda seconds: None)


def full_menu_session(**extra_pages: FakeResponse) -> RoutingSession:
    """South Campus menu + the real chicken burger label; other dishes get the banana label."""
    pages = {
        build_menu_url(LOCATION, DAY): FakeResponse(200, read_fixture("menu_south_campus_2026-10-12.html")),
        build_label_url(CHICKEN_BURGER_ID): FakeResponse(200, read_fixture("label_fresh_chicken_burger.html")),
    }
    pages.update(extra_pages)
    return RoutingSession(pages, default_label=read_fixture("label_banana.html"))


@pytest.fixture
def conn():
    """A brand-new empty database for each test."""
    connection = connect(":memory:")
    yield connection
    connection.close()


def test_full_scrape_saves_menu_and_nutrition(conn):
    result = scrape_hall(conn, make_fetcher(full_menu_session()), HALL, LOCATION, DAY)

    menu = get_menu(conn, DAY, HALL)
    # 645 entries on the page, but one dish listed at several stations in the same
    # meal is stored once, so 533 rows are saved.
    assert len(menu) == result.menu_entries == 533
    assert result.unique_dishes == 304
    assert result.labels_fetched == 304
    assert result.labels_failed == []
    # Every dish got nutrition, and the burger has its own real label, not the banana's.
    assert all(row.nutrition is not None for row in menu)
    burger = next(row for row in menu if row.recipe_id == CHICKEN_BURGER_ID)
    other_dish = next(row for row in menu if row.recipe_id != CHICKEN_BURGER_ID)
    assert burger.nutrition.protein_g != other_dish.nutrition.protein_g


def test_each_dish_label_is_downloaded_only_once(conn):
    session = full_menu_session()
    scrape_hall(conn, make_fetcher(session), HALL, LOCATION, DAY)

    label_urls = [url for url in session.requested_urls if "label.aspx" in url]
    assert len(label_urls) == len(set(label_urls)) == 304


def test_second_scrape_uses_cached_nutrition(conn):
    scrape_hall(conn, make_fetcher(full_menu_session()), HALL, LOCATION, DAY)
    session = full_menu_session()
    result = scrape_hall(conn, make_fetcher(session), HALL, LOCATION, DAY)

    assert result.labels_fetched == 0
    assert result.labels_cached == 304
    assert session.requested_urls == [build_menu_url(LOCATION, DAY)]


def test_failed_label_skips_that_dish_but_saves_the_rest(conn):
    broken = {build_label_url(CHICKEN_BURGER_ID): FakeResponse(500)}
    result = scrape_hall(conn, make_fetcher(full_menu_session(**broken)), HALL, LOCATION, DAY)

    assert result.labels_failed == [CHICKEN_BURGER_ID]
    assert result.labels_fetched == 303
    assert not has_nutrition(conn, CHICKEN_BURGER_ID)
    menu = get_menu(conn, DAY, HALL)
    assert len(menu) == 533
    burger = next(row for row in menu if row.recipe_id == CHICKEN_BURGER_ID)
    assert burger.nutrition is None


@pytest.mark.parametrize("menu_response", [
    FakeResponse(503),  # site down
    FakeResponse(200, "<html><body>Under maintenance</body></html>"),  # redesigned / broken page
])
def test_failed_menu_page_raises_and_keeps_old_menu(conn, menu_response):
    old_item = MenuItem(name="Old Dish", recipe_id="1*1", station="Grill", meal="Lunch")
    save_menu(conn, DAY, HALL, [old_item])
    session = RoutingSession({build_menu_url(LOCATION, DAY): menu_response})

    with pytest.raises(ScrapeError, match="South Campus"):
        scrape_hall(conn, make_fetcher(session), HALL, LOCATION, DAY)

    assert [row.name for row in get_menu(conn, DAY, HALL)] == ["Old Dish"]


def test_empty_day_saves_empty_menu(conn):
    old_item = MenuItem(name="Stale Dish", recipe_id="1*1", station="Grill", meal="Lunch")
    save_menu(conn, DAY, HALL, [old_item])
    empty_page = FakeResponse(200, read_fixture("menu_yahentamitsi_2026-10-12_empty.html"))
    session = RoutingSession({build_menu_url(LOCATION, DAY): empty_page})

    result = scrape_hall(conn, make_fetcher(session), HALL, LOCATION, DAY)

    assert result.menu_entries == 0
    assert result.unique_dishes == 0
    assert get_menu(conn, DAY, HALL) == []


def test_format_result_lists_failed_ids(conn):
    broken = {build_label_url(CHICKEN_BURGER_ID): FakeResponse(500)}
    result = scrape_hall(conn, make_fetcher(full_menu_session(**broken)), HALL, LOCATION, DAY)

    text = format_result(result)
    assert text.startswith("South Campus: 533 menu entries, 304 unique dishes")
    assert "1 failed" in text
    assert CHICKEN_BURGER_ID in text


def test_dish_without_published_nutrition_counts_as_no_data_not_failed(conn):
    soup_page = {build_label_url(CHICKEN_BURGER_ID): FakeResponse(200, read_fixture("label_maryland_crab_soup.html"))}
    result = scrape_hall(conn, make_fetcher(full_menu_session(**soup_page)), HALL, LOCATION, DAY)

    assert result.labels_no_data == [CHICKEN_BURGER_ID]
    assert result.labels_failed == []
    assert result.labels_fetched == 303
    assert not has_nutrition(conn, CHICKEN_BURGER_ID)  # so the next run checks again
    assert "1 no data, 0 failed" in format_result(result)
