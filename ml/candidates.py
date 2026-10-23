# Decides which menu dishes the plate recognizer may guess. Both POST /recognize and
# ml/evaluate.py use is_candidate, so the evaluation always scores the list the app uses.
# Condiments, sauces, dressings and the whole Salad Bar are left out: they're ~40% of a
# day's menu, rarely what a photo is "of", and they crowd real dishes out of the top 5.
# A left-out dish can still be logged from the menu or the photo screen's search.

import re

from db.database import MenuRow

# Every Salad Bar item is a topping (lettuce, croutons, dressings, fruit cups).
EXCLUDED_STATIONS = {"salad bar"}

# A name ending in one of these is a condiment: "Ranch Dressing", "Pancake Syrup", "Beef Gravy".
CONDIMENT_ENDINGS = (
    "sauce", "dressing", "vinegar", "mayonnaise", "mayo", "aioli", "ketchup", "mustard",
    "relish", "syrup", "gravy", "salsa", "dip", "topping", "sprinkles", "margarine",
    "butter", "oil", "jam", "jelly", "cream cheese", "sour cream", "whipped cream",
)

# Condiments whose names don't end in one of the words above.
CONDIMENT_NAMES = {"guacamole", "pico de gallo", "salsa roja", "salsa verde"}

# "Meatball no sauce", "Pasta with Butter Cream Sauce", "Vegetables in Vodka Sauce",
# "Catfish & ... Lemon Butter Sauce" are dishes described by their sauce, not sauces.
DISH_MARKERS = re.compile(r"\b(with|w/|no|in)\b|&")

# Real sauces have short names; 6+ words ("Tilapia Mushroom Tomato Herb Butter Sauce") is a dish.
MAX_CONDIMENT_WORDS = 5


def is_condiment(name: str, station: str) -> bool:
    """Tell whether a menu item is a condiment, sauce, dressing or salad-bar topping.

    Args:
        name: the dish name as UMD lists it.
        station: the station it's served at, e.g. "Salad Bar".

    Returns:
        True if the recognizer should leave it out.

    Example:
        is_condiment("Alfredo Sauce", "Al Forno Pastas")       # -> True
        is_condiment("Meatball no sauce", "Al Forno Pastas")   # -> False
        is_condiment("Chopped Romaine", "Salad Bar")           # -> True
    """
    if station.strip().lower() in EXCLUDED_STATIONS:
        return True
    # Drop notes like "(RTU)" in "Sweet Sour Sauce (RTU)" so the real last word is checked.
    clean = re.sub(r"\(.*?\)", "", name).strip().lower()
    if clean in CONDIMENT_NAMES:
        return True
    if DISH_MARKERS.search(clean) or len(clean.split()) > MAX_CONDIMENT_WORDS:
        return False
    # Whole words only, so "Shrimp Boil" doesn't count as ending in "oil".
    return any(re.search(rf"\b{ending}$", clean) for ending in CONDIMENT_ENDINGS)


def is_candidate(row: MenuRow) -> bool:
    """Tell whether a menu row can be one of the recognizer's guesses.

    It needs nutrition (a guess you can't log wastes a top-5 slot) and must not be a
    condiment (see is_condiment).

    Example:
        is_candidate(MenuRow(name="Spanish Rice", station="Chef's Corner Sides", ...))  # -> True
    """
    return row.nutrition is not None and not is_condiment(row.name, row.station)
