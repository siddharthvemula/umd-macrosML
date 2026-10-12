# Turns a nutrition.umd.edu menu page (raw HTML) into a list of MenuItem objects.
# This is the first stage of the scraper: fetcher.py downloads the page, this file
# reads it, and later steps look up each item's nutrition and save it to the database.
# It never touches the network, so it can be tested against saved pages.

from dataclasses import dataclass
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

# The site shows this text instead of a menu when a hall has nothing posted for a date.
NO_MENU_MARKER = "NO DATA AVAILABLE"


class MenuPageFormatError(Exception):
    """Raised when a page has neither menu items nor the "no menu" marker.

    That usually means UMD changed their site layout, and we want to know loudly
    rather than quietly record "no menu posted".
    """


@dataclass
class MenuItem:
    """One dish on one meal's menu.

    Example:
        MenuItem(name="Fresh Chicken Burger", recipe_id="080603*4",
                 station="Broiler Works", meal="Brunch")
    """

    name: str
    recipe_id: str  # UMD's ID for the dish + portion, used to fetch its nutrition label
    station: str
    meal: str


def parse_menu_page(html: str) -> List[MenuItem]:
    """Extract every menu item from a nutrition.umd.edu menu page.

    Args:
        html: The full HTML of a page like
              https://nutrition.umd.edu/?locationNum=19&dtdate=10/13/2026

    Returns:
        A list of MenuItem, in page order. An empty list means UMD has no menu
        posted for that hall and date.

    Raises:
        MenuPageFormatError: If the page has no items and no "no menu" marker.

    Example:
        >>> items = parse_menu_page(html)
        >>> items[0]
        MenuItem(name='Fresh Chicken Burger', recipe_id='080603*4',
                 station='Broiler Works', meal='Brunch')
    """
    soup = BeautifulSoup(html, "html.parser")
    meal_names = _get_meal_names_by_pane_id(soup)

    items: List[MenuItem] = []
    # Each meal (Brunch, Dinner...) is a tab pane; each station is a card inside it.
    for pane in soup.select("div.tab-pane"):
        meal = meal_names.get(pane.get("id", ""), "Unknown")
        for card in pane.select("div.card"):
            items.extend(_parse_station_card(card, meal))

    if not items and NO_MENU_MARKER not in soup.get_text():
        raise MenuPageFormatError(
            "Found no menu items and no 'NO DATA AVAILABLE' message. "
            "The nutrition.umd.edu page layout may have changed."
        )
    return items


def _get_meal_names_by_pane_id(soup: BeautifulSoup) -> Dict[str, str]:
    """Map each tab pane's id to its meal name, using the tab links at the top.

    Example: <a class="nav-link" href="#pane-2">Dinner</a>  ->  {"pane-2": "Dinner"}
    """
    meal_names = {}
    for tab_link in soup.select("a.nav-link"):
        pane_id = tab_link.get("href", "").lstrip("#")
        meal_names[pane_id] = tab_link.get_text(strip=True)
    return meal_names


def _parse_station_card(card, meal: str) -> List[MenuItem]:
    """Turn one station's card (e.g. "Joe's Grill") into MenuItems.

    Example: a card titled "Broiler Works" with a link to "Fresh Chicken Burger"
    -> [MenuItem(name="Fresh Chicken Burger", recipe_id="080603*4",
                 station="Broiler Works", meal=meal)]
    """
    title = card.select_one(".card-title")
    station = title.get_text(strip=True) if title else "Unknown"

    items = []
    for link in card.select("a.menu-item-name"):
        items.append(
            MenuItem(
                name=link.get_text(strip=True),
                recipe_id=_recipe_id_from_href(link.get("href", "")),
                station=station,
                meal=meal,
            )
        )
    return items


def _recipe_id_from_href(href: str) -> str:
    """Pull the recipe ID out of a nutrition label link.

    Example: "label.aspx?RecNumAndPort=080603*4"  ->  "080603*4"
    """
    query = parse_qs(urlparse(href).query)
    return query.get("RecNumAndPort", [""])[0]
