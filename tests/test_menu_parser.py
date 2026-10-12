# Tests for scraper/menu_parser.py, run against real menu pages saved in tests/fixtures/
# so they work offline and never hit the UMD site.

from pathlib import Path

import pytest

from scraper.menu_parser import MenuItem, MenuPageFormatError, parse_menu_page

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> str:
    """Read a saved HTML page from tests/fixtures/ as a string."""
    return (FIXTURES / filename).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def south_campus_items():
    """Parse the full South Campus page once and share it across tests (it's 1 MB)."""
    return parse_menu_page(load_fixture("menu_south_campus_2026-10-12.html"))


def test_finds_every_item_on_a_full_menu(south_campus_items):
    # 645 = number of item rows in the saved page (counted with grep).
    assert len(south_campus_items) == 645


def test_first_item_has_correct_fields(south_campus_items):
    assert south_campus_items[0] == MenuItem(
        name="Fresh Chicken Burger",
        recipe_id="080603*4",
        station="Broiler Works",
        meal="Brunch",
    )


def test_items_are_split_between_meals(south_campus_items):
    brunch = [item for item in south_campus_items if item.meal == "Brunch"]
    dinner = [item for item in south_campus_items if item.meal == "Dinner"]
    assert len(brunch) == 329
    assert len(dinner) == 316


def test_last_item_belongs_to_dinner(south_campus_items):
    last = south_campus_items[-1]
    assert last.name == "Water Chestnuts"
    assert last.recipe_id == "903346*1"
    assert last.meal == "Dinner"


def test_every_item_has_a_name_station_and_recipe_id(south_campus_items):
    for item in south_campus_items:
        assert item.name and item.station and item.recipe_id


def test_missing_dinner_section_still_returns_brunch():
    # Real case: the page shows a "Dinner" tab but dinner isn't posted yet.
    items = parse_menu_page(load_fixture("menu_yahentamitsi_2026-10-13_no_dinner.html"))
    assert len(items) == 248
    assert {item.meal for item in items} == {"Brunch"}


def test_no_menu_posted_returns_empty_list():
    items = parse_menu_page(load_fixture("menu_yahentamitsi_2026-10-12_empty.html"))
    assert items == []


def test_unrecognized_page_raises_clear_error():
    with pytest.raises(MenuPageFormatError):
        parse_menu_page("<html><body><p>Site under maintenance</p></body></html>")
