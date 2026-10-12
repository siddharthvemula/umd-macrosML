# Turns a nutrition.umd.edu label page (raw HTML) into a NutritionLabel object.
# This is the second stage of the scraper: menu_parser.py finds each dish's recipe ID,
# the fetcher downloads that dish's label page, and this file reads the nutrition off it.
# It never touches the network, so it can be tested against saved pages.

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

# Matches nutrient text like "Total Fat 6.3g" or "Vitamin A - RE 0.3mcg".
# Blank cells on the site look like "Trans Fat - - - g" or "Potassium mg" and won't match.
NUTRIENT_PATTERN = re.compile(r"^(?P<name>[A-Za-z][A-Za-z .\-]*?)\s+(?P<amount>\d+(?:\.\d+)?)\s*[a-zA-Z]+$")

# The label text for each field we store. Matching by name (not table position)
# means the parser keeps working if UMD reorders the rows.
# "calories" is the detail table's precise value (e.g. 240.8), not the rounded 241.
REQUIRED_NUTRIENTS = {
    "calories": "calories",
    "protein_g": "protein",
    "carbs_g": "total carbohydrate",
    "fat_g": "total fat",
}
OPTIONAL_NUTRIENTS = {
    "sat_fat_g": "saturated fat",
    "sugar_g": "total sugars",
    "fiber_g": "dietary fiber",
    "sodium_mg": "sodium",
}


class LabelPageFormatError(Exception):
    """Raised when a page doesn't look like a nutrition label (no name or missing macros).

    That usually means UMD changed their site layout, or the recipe ID was bad.
    """


@dataclass
class NutritionLabel:
    """Nutrition for one serving of one dish.

    Example:
        NutritionLabel(name="Banana", serving_size="1 each", calories=109.8,
                       protein_g=1.3, carbs_g=28.2, fat_g=0.4, sat_fat_g=0.1,
                       sugar_g=15.1, fiber_g=3.2, sodium_mg=1.2,
                       ingredients="Banana (Banana)", allergens=[])
    """

    name: str
    serving_size: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    # None means UMD left the value blank, which is different from 0.
    sat_fat_g: Optional[float]
    sugar_g: Optional[float]
    fiber_g: Optional[float]
    sodium_mg: Optional[float]
    ingredients: str
    allergens: List[str]


def parse_label_page(html: str) -> NutritionLabel:
    """Extract the nutrition facts from a nutrition.umd.edu label page.

    Args:
        html: The full HTML of a page like
              https://nutrition.umd.edu/label.aspx?RecNumAndPort=080603*4

    Returns:
        A NutritionLabel for one serving.

    Raises:
        LabelPageFormatError: If the page has no dish name or is missing a macro.

    Example:
        >>> label = parse_label_page(html)
        >>> label.protein_g, label.carbs_g, label.fat_g
        (15.0, 32.0, 6.3)
    """
    soup = BeautifulSoup(html, "html.parser")

    heading = soup.select_one("h1")
    if heading is None or not heading.get_text(strip=True):
        raise LabelPageFormatError("No dish name (<h1>) found. The label page layout may have changed.")

    nutrients = _read_nutrients(soup)
    missing = [label for label in REQUIRED_NUTRIENTS.values() if label not in nutrients]
    if missing:
        raise LabelPageFormatError(f"Label is missing required nutrients: {', '.join(missing)}")

    return NutritionLabel(
        name=heading.get_text(strip=True),
        serving_size=_read_serving_size(soup),
        **{field: nutrients[label] for field, label in REQUIRED_NUTRIENTS.items()},
        **{field: nutrients.get(label) for field, label in OPTIONAL_NUTRIENTS.items()},
        ingredients=_read_text(soup, "span.labelingredientsvalue"),
        allergens=_read_allergens(soup),
    )


def _read_nutrients(soup: BeautifulSoup) -> Dict[str, float]:
    """Collect every "Name amount+unit" nutrient on the page into a dict.

    Example: spans "Total Fat 6.3g" and "Protein 15g"  ->  {"total fat": 6.3, "protein": 15.0}
    """
    nutrients: Dict[str, float] = {}
    for span in soup.select("span.nutfactstopnutrient"):
        parsed = _split_nutrient_text(span.get_text())
        # Some nutrients appear in both tables; keep the first one we see.
        if parsed and parsed[0] not in nutrients:
            nutrients[parsed[0]] = parsed[1]
    return nutrients


def _split_nutrient_text(text: str) -> Optional[Tuple[str, float]]:
    """Split one nutrient's text into a normalized name and its amount.

    Returns None for blank values, percentages, and anything else that isn't a nutrient.

    Example: "Total Carbohydrate.\xa032g"  ->  ("total carbohydrate", 32.0)
             "Trans Fat\xa0-\xa0-\xa0-\xa0g"  ->  None
    """
    # The site pads text with &nbsp; (\xa0); turn it into normal single spaces.
    cleaned = " ".join(text.replace("\xa0", " ").split())
    match = NUTRIENT_PATTERN.match(cleaned)
    if not match:
        return None
    # Lowercase and drop stray periods ("Total Carbohydrate.") so lookups are predictable.
    name = match.group("name").replace(".", "").strip().lower()
    return name, float(match.group("amount"))


def _read_serving_size(soup: BeautifulSoup) -> str:
    """Return the serving size text, e.g. "4 oz".

    The page has two `nutfactsservsize` divs: the caption "Serving size" and the value.
    """
    sizes = [div.get_text(strip=True) for div in soup.select("div.nutfactsservsize")]
    values = [size for size in sizes if size.lower() != "serving size"]
    return values[0] if values else ""


def _read_allergens(soup: BeautifulSoup) -> List[str]:
    """Return the allergen list, or [] if none are listed.

    Example: "Gluten, Soy"  ->  ["Gluten", "Soy"]
    """
    text = _read_text(soup, "span.labelallergensvalue")
    return [allergen.strip() for allergen in text.split(",") if allergen.strip()]


def _read_text(soup: BeautifulSoup, selector: str) -> str:
    """Return the stripped text of the first element matching `selector`, or "" if absent."""
    element = soup.select_one(selector)
    return element.get_text(strip=True) if element else ""
