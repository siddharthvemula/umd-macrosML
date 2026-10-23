# Tests for ml/candidates.py: which menu items the recognizer may guess. Names are real
# UMD menu items, including the tricky "dish named after its sauce" cases.

import pytest

from db.database import MenuRow
from ml.candidates import is_candidate, is_condiment
from scraper.label_parser import NutritionLabel

LABEL = NutritionLabel(
    name="x", serving_size="1 each", calories=100.0, protein_g=1.0, carbs_g=1.0,
    fat_g=1.0, sat_fat_g=None, sugar_g=None, fiber_g=None, sodium_mg=None,
    ingredients="", allergens=[],
)


@pytest.mark.parametrize("name", [
    "Alfredo Sauce", "Ranch Dressing", "Pancake Syrup", "Beef Gravy", "Butter",
    "Chipotle Mayonnaise", "Serrano Lime Salsa", "Plain Cream Cheese", "Sour Cream",
    "Guacamole", "Pico de Gallo", "Salsa Roja", "Rainbow Sprinkles",
])
def test_condiments_are_excluded(name):
    assert is_condiment(name, "Chef's Corner Sides")


def test_note_in_parentheses_is_ignored():
    # "(RTU)" would otherwise hide that the name ends in "Sauce".
    assert is_condiment("Sweet Sour Sauce (RTU)", "Woks")


@pytest.mark.parametrize("name", [
    "Meatball no sauce",
    "Blistered Shrimp Pasta with Butter Cream Sauce",
    "Vegetables in Vodka Sauce",
    "Spicy Tofu & Creamy Coconut Sauce",
    "Tilapia Mushroom Tomato Herb Butter Sauce",  # 6 words: too long to be just a sauce
    "Spinach Red Clam Sauce Linguini",            # doesn't end in "sauce"
    "Shrimp Boil",                                # ends in "boil", not the word "oil"
    "Spanish Rice",
])
def test_dishes_named_after_a_sauce_are_kept(name):
    assert not is_condiment(name, "Al Forno Pastas")


def test_whole_salad_bar_is_excluded():
    assert is_condiment("Chopped Romaine", "Salad Bar")
    assert is_condiment("Chicken Strips", "salad bar")


def test_candidate_needs_nutrition_and_not_condiment():
    assert is_candidate(MenuRow("Spanish Rice", "1*1", "Grill", "Lunch", LABEL))
    assert not is_candidate(MenuRow("Spanish Rice", "1*1", "Grill", "Lunch", None))
    assert not is_candidate(MenuRow("Ranch Dressing", "2*1", "Grill", "Lunch", LABEL))
