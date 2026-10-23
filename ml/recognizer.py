# Plate photo recognizer (Phase 4, ML v1).
# Ranks a dining hall's menu dishes by how likely each one is on a plate photo, using
# zero-shot CLIP: no training, just image-text similarity against the dish names.
# Knows nothing about the database or HTTP; the eval script (Step 3) and the
# /recognize endpoint (Step 4) fetch the menu and pass the dish names in.

import io
from dataclasses import dataclass
from typing import Protocol

import torch
from PIL import Image, UnidentifiedImageError

MODEL_NAME = "openai/clip-vit-base-patch32"
# "a photo of X" matches how CLIP's training captions were worded; Step 3 compares others.
DEFAULT_TEMPLATE = "a photo of {name}, a dining hall dish"

# Portion sizes CLIP picks between, and the servings each one suggests. Medium comes first
# so a tie (no real signal) suggests a normal 1x serving.
PORTION_SERVINGS = {"medium": 1.0, "small": 0.75, "large": 1.5}
PORTION_TEMPLATE = "a {size} portion of {name} on a plate"


class BadPhotoError(Exception):
    """Raised when uploaded bytes can't be read as an image."""


@dataclass
class Guess:
    """One ranked guess: a menu dish name and its probability (0-1) among the candidates."""

    name: str
    score: float


class ImageTextScorer(Protocol):
    """Anything that can score how well each text matches an image.

    The real one is ClipScorer; tests pass a fake, so they never load the model.
    """

    def score(self, image: Image.Image, texts: list[str]) -> list[float]:
        """Return one raw similarity per text (higher = better match), same order as texts."""
        ...


class ClipScorer:
    """The real scorer: CLIP from Hugging Face, loaded once and reused for every photo."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        """Load the CLIP model and its processor.

        Args:
            model_name: Hugging Face model ID.

        Example:
            scorer = ClipScorer()  # ~600 MB download the first time, then cached on disk
        """
        # Imported here so importing this module (e.g. in tests) doesn't load transformers.
        from transformers import CLIPModel, CLIPProcessor

        self.model = CLIPModel.from_pretrained(model_name)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model.eval()  # inference mode: turns off training-only behavior like dropout

    def score(self, image: Image.Image, texts: list[str]) -> list[float]:
        """Return CLIP's image-text similarity for each text.

        Args:
            image: RGB plate photo.
            texts: prompts, e.g. ["a photo of Rice, a dining hall dish", ...].

        Returns:
            One raw score (logit) per text, same order.

        Example:
            scorer.score(image, ["a photo of Rice", "a photo of Salad"])  # -> [24.1, 19.8]
        """
        inputs = self.processor(text=texts, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():  # inference only, so skip tracking gradients
            logits = self.model(**inputs).logits_per_image[0]
        return logits.tolist()


def load_photo(data: bytes) -> Image.Image:
    """Turn uploaded file bytes into an RGB image.

    Args:
        data: raw bytes of a JPEG/PNG/etc. file.

    Returns:
        The image in RGB (phone photos can be RGBA or grayscale; CLIP expects RGB).

    Raises:
        BadPhotoError: if the bytes are empty or not a readable image.

    Example:
        load_photo(open("plate.jpg", "rb").read())  # -> <PIL.Image.Image mode=RGB ...>
    """
    if not data:
        raise BadPhotoError("The photo is empty.")
    try:
        image = Image.open(io.BytesIO(data))
        # Image.open only reads the header; convert() decodes the pixels, so a truncated
        # file fails here instead of later inside the model.
        return image.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise BadPhotoError("That file isn't a readable image.") from error


def build_prompts(names: list[str], template: str = DEFAULT_TEMPLATE) -> list[str]:
    """Wrap each dish name in a text prompt for CLIP.

    Args:
        names: dish names.
        template: wording with a {name} slot.

    Returns:
        One prompt per name, same order.

    Example:
        build_prompts(["Rice"], "a photo of {name}")  # -> ["a photo of Rice"]
    """
    return [template.format(name=name) for name in names]


def rank_menu_items(
    image: Image.Image,
    dish_names: list[str],
    scorer: ImageTextScorer,
    top_k: int = 5,
    template: str = DEFAULT_TEMPLATE,
) -> list[Guess]:
    """Rank menu dishes by how likely each one is on the plate.

    Args:
        image: RGB plate photo.
        dish_names: candidate dishes (e.g. one meal's menu); duplicates are fine.
        scorer: ClipScorer in the app, a fake in tests.
        top_k: how many guesses to return.
        template: prompt wording with a {name} slot.

    Returns:
        Up to top_k guesses, best first. Scores are probabilities over all candidates,
        so they sum to 1 across the full list. An empty menu gives [].

    Example:
        rank_menu_items(image, ["Rice", "Salad", "Rice"], ClipScorer(), top_k=1)
        # -> [Guess(name="Rice", score=0.87)]
    """
    # UMD lists some dishes at several stations; score each name once.
    names = list(dict.fromkeys(dish_names))
    if not names:
        return []

    raw_scores = scorer.score(image, build_prompts(names, template))
    # Softmax turns raw similarities into probabilities that sum to 1, which are
    # easier to read and compare than CLIP's raw numbers.
    probabilities = torch.tensor(raw_scores).softmax(dim=0).tolist()

    ranked = sorted(zip(names, probabilities), key=lambda pair: pair[1], reverse=True)
    return [Guess(name=name, score=score) for name, score in ranked[:top_k]]


def suggest_servings(image: Image.Image, dish_names: list[str], scorer: ImageTextScorer) -> dict[str, float]:
    """Guess each dish's portion size (small / medium / large) and turn it into servings.

    Zero-shot like rank_menu_items: CLIP compares the photo with "a small portion of X on
    a plate", "a medium ...", "a large ..." and the best match wins. It's a rough hint
    the student adjusts, not a measurement (that's ML v2's plate-as-ruler idea).

    Args:
        image: RGB plate photo.
        dish_names: the guessed dishes.
        scorer: ClipScorer in the app, a fake in tests.

    Returns:
        {dish name: 0.75, 1.0 or 1.5}. {} for no dishes.

    Example:
        suggest_servings(image, ["Spanish Rice"], ClipScorer())  # -> {"Spanish Rice": 1.5}
    """
    names = list(dict.fromkeys(dish_names))
    if not names:
        return {}
    sizes = list(PORTION_SERVINGS)
    prompts = [PORTION_TEMPLATE.format(size=size, name=name) for name in names for size in sizes]
    # One call for every dish, so CLIP reads the photo once instead of once per dish.
    raw_scores = scorer.score(image, prompts)

    suggestions = {}
    for index, name in enumerate(names):
        dish_scores = raw_scores[index * len(sizes):(index + 1) * len(sizes)]
        # max() keeps the first of equal scores, which is "medium" (see PORTION_SERVINGS).
        best_size = max(zip(sizes, dish_scores), key=lambda pair: pair[1])[0]
        suggestions[name] = PORTION_SERVINGS[best_size]
    return suggestions
