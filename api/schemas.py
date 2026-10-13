# The shapes of the API's JSON responses (Pydantic models). They're kept separate
# from the database's dataclasses so the database can change without breaking the
# frontend. FastAPI also uses them to validate output and build the /docs page.

from datetime import date

from pydantic import BaseModel, ConfigDict


class HallOut(BaseModel):
    """A dining hall the app has menus for.

    Example JSON: {"id": "south_campus", "name": "South Campus"}
    """

    id: str
    name: str


class NutritionOut(BaseModel):
    """Nutrition for one serving of a dish. None means UMD left the value blank.

    Example JSON: {"name": "Banana", "serving_size": "1 each", "calories": 109.8,
                   "protein_g": 1.3, ..., "allergens": []}
    """

    # Lets Pydantic read fields straight off our NutritionLabel dataclass.
    model_config = ConfigDict(from_attributes=True)

    name: str
    serving_size: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    sat_fat_g: float | None
    sugar_g: float | None
    fiber_g: float | None
    sodium_mg: float | None
    ingredients: str
    allergens: list[str]


class MenuItemOut(BaseModel):
    """One dish on a menu. nutrition is None if its label hasn't been scraped.

    Example JSON: {"name": "Banana", "recipe_id": "111*1", "station": "Fruit",
                   "meal": "Breakfast", "nutrition": {...}}
    """

    model_config = ConfigDict(from_attributes=True)

    name: str
    recipe_id: str
    station: str
    meal: str
    nutrition: NutritionOut | None


class MenuOut(BaseModel):
    """A hall's menu for one day. items is empty if no menu is stored for that day.

    Example JSON: {"hall": "south_campus", "date": "2026-10-12", "items": [...]}
    """

    hall: str
    date: date
    items: list[MenuItemOut]
