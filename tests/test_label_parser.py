# Tests for scraper/label_parser.py, run against real label pages saved in tests/fixtures/
# so they work offline and never hit the UMD site.

from pathlib import Path

import pytest

from scraper.label_parser import (
    LabelPageFormatError,
    _split_nutrient_text,
    parse_label_page,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> str:
    """Read a saved HTML page from tests/fixtures/ as a string."""
    return (FIXTURES / filename).read_text(encoding="utf-8")


def test_parses_full_burger_label():
    label = parse_label_page(load_fixture("label_fresh_chicken_burger.html"))
    assert label.name == "Fresh Chicken Burger"
    assert label.serving_size == "4 oz"
    assert (label.protein_g, label.carbs_g, label.fat_g) == (15.0, 32.0, 6.3)
    assert (label.sat_fat_g, label.sugar_g, label.fiber_g, label.sodium_mg) == (1.4, 0.5, 1.6, 456.9)
    assert label.ingredients.startswith("Ground Chicken Raw (CHICKEN")
    assert label.allergens == ["Gluten"]


def test_banana_label_with_blank_values_and_no_allergens():
    label = parse_label_page(load_fixture("label_banana.html"))
    assert (label.calories, label.protein_g, label.carbs_g, label.fat_g) == (109.8, 1.3, 28.2, 0.4)
    assert label.serving_size == "1 each"
    assert label.ingredients == "Banana (Banana)"
    assert label.allergens == []


def test_uses_precise_calories_not_rounded():
    # The big label number says 241; the detail table says 240.8.
    assert parse_label_page(load_fixture("label_fresh_chicken_burger.html")).calories == 240.8


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Sodium\xa0456.9mg", ("sodium", 456.9)),
        ("Total Carbohydrate.\xa032g", ("total carbohydrate", 32.0)),
        ("\xa0\xa0\xa0\xa0Saturated Fat\xa01.4g", ("saturated fat", 1.4)),
        ("Trans Fat\xa0-\xa0-\xa0-\xa0g", None),
        ("Potassium\xa0mg", None),
        ("\xa025%", None),
        ("Includes 0g Added Sugars", None),
    ],
)
def test_split_nutrient_text(text, expected):
    assert _split_nutrient_text(text) == expected


def test_page_without_label_raises():
    with pytest.raises(LabelPageFormatError):
        parse_label_page("<html><body><p>Oops</p></body></html>")


def test_label_missing_a_macro_raises():
    html = "<h1>Mystery Dish</h1><span class='nutfactstopnutrient'>Protein 5g</span>"
    with pytest.raises(LabelPageFormatError, match="total fat"):
        parse_label_page(html)
