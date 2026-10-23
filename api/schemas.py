# The shapes of the API's JSON requests and responses (Pydantic models). They're kept separate
# from the database's dataclasses so the database can change without breaking the
# frontend. FastAPI also uses them to validate output and build the /docs page.

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class GuessOut(BaseModel):
    """One dish the recognizer thinks is on the plate, ready to log with POST /meals.

    Example JSON: {"recipe_id": "111*1", "name": "Banana", "score": 0.42,
                   "suggested_servings": 1.0, "nutrition": {...}}
    """

    recipe_id: str
    name: str
    # Probability (0-1) among all of the meal's candidate dishes, not just these guesses.
    score: float
    # CLIP's small / medium / large portion guess as servings: 0.75, 1.0 or 1.5.
    suggested_servings: float
    nutrition: NutritionOut


class RecognizeOut(BaseModel):
    """The recognizer's ranked guesses for one plate photo, best first.

    Example JSON: {"hall": "yahentamitsi", "date": "2026-10-15", "meal": "Lunch",
                   "guesses": [{"recipe_id": "111*1", "name": "Banana", ...}, ...]}
    """

    hall: str
    date: date
    meal: str | None
    # The saved photo's id, sent back with POST /meals so a logged guess becomes a
    # training label. None when there were no guesses (nothing to label, so not saved).
    photo_id: int | None
    guesses: list[GuessOut]


class MealLogIn(BaseModel):
    """The request body for logging a meal.

    Example JSON: {"recipe_id": "111*1", "servings": 1.5}  (date defaults to today)
                  {"recipe_id": "111*1", "servings": 1, "photo_id": 7,
                   "suggested_servings": 1.5}  (logged from a photo guess)
    """

    recipe_id: str
    # Any portion in (0, 5]: the UI offers 0.5/1/1.5/2, but ML v2 may estimate e.g. 1.3.
    servings: float = Field(gt=0, le=5)
    # alias: the JSON key is "date", but a field named `date` would hide the date type.
    log_date: date | None = Field(None, alias="date")
    photo_id: int | None = None
    # CLIP's portion guess for this dish (from POST /recognize), saved next to the chosen
    # servings. Same range as servings, since it's a servings amount too.
    suggested_servings: float | None = Field(None, gt=0, le=5)

    @model_validator(mode="after")
    def suggestion_needs_photo(self) -> "MealLogIn":
        """Reject a suggestion without a photo: only photo guesses have one, so it would be junk data."""
        if self.suggested_servings is not None and self.photo_id is None:
            raise ValueError("suggested_servings is only for dishes logged from a photo (needs photo_id)")
        return self


class MealLogOut(BaseModel):
    """One logged dish, with macros already multiplied by servings.

    Example JSON: {"id": 1, "date": "2026-10-12", "recipe_id": "111*1", "name": "Banana",
                   "servings": 2.0, "calories": 219.6, "protein_g": 2.6, "carbs_g": 56.4,
                   "fat_g": 0.8, "logged_at": "2026-10-12 16:30:00", "photo_id": null}
    """

    id: int
    date: date
    recipe_id: str
    name: str
    servings: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    logged_at: str
    photo_id: int | None
    suggested_servings: float | None


class DailySummaryOut(BaseModel):
    """A day's macro totals for the dashboard.

    Example JSON: {"date": "2026-10-12", "calories": 460.4, "protein_g": 17.6,
                   "carbs_g": 88.4, "fat_g": 7.1, "meal_count": 2}
    """

    date: date
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_count: int
