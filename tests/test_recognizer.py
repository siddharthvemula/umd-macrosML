# Tests for ml/recognizer.py. A FakeScorer stands in for CLIP, so these run in
# milliseconds and never download the model.

import io

import pytest
from PIL import Image

from ml.recognizer import BadPhotoError, build_prompts, load_photo, rank_menu_items, suggest_servings


class FakeScorer:
    """Returns a chosen raw score per dish name and records the prompts it was given."""

    def __init__(self, scores_by_name: dict[str, float]) -> None:
        self.scores_by_name = scores_by_name
        self.calls: list[list[str]] = []

    def score(self, image: Image.Image, texts: list[str]) -> list[float]:
        self.calls.append(texts)
        # Find which dish each prompt is about, so tests can use any template.
        return [next(s for name, s in self.scores_by_name.items() if name in text) for text in texts]


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (8, 8))


def test_best_match_comes_first(image):
    scorer = FakeScorer({"Rice": 1.0, "Tacos": 5.0, "Salad": 3.0})
    guesses = rank_menu_items(image, ["Rice", "Tacos", "Salad"], scorer)
    assert [g.name for g in guesses] == ["Tacos", "Salad", "Rice"]


def test_returns_at_most_top_k(image):
    scorer = FakeScorer({"Rice": 1.0, "Tacos": 5.0, "Salad": 3.0})
    assert len(rank_menu_items(image, ["Rice", "Tacos", "Salad"], scorer, top_k=2)) == 2
    assert len(rank_menu_items(image, ["Rice"], scorer, top_k=5)) == 1


def test_duplicate_names_are_scored_once(image):
    scorer = FakeScorer({"Rice": 1.0, "Tacos": 2.0})
    guesses = rank_menu_items(image, ["Rice", "Tacos", "Rice"], scorer)
    assert len(scorer.calls[0]) == 2
    assert sorted(g.name for g in guesses) == ["Rice", "Tacos"]


def test_empty_menu_returns_empty_list_without_scoring(image):
    scorer = FakeScorer({})
    assert rank_menu_items(image, [], scorer) == []
    assert scorer.calls == []


def test_scores_are_probabilities_that_sum_to_one(image):
    scorer = FakeScorer({"Rice": 1.0, "Tacos": 5.0, "Salad": 3.0})
    guesses = rank_menu_items(image, ["Rice", "Tacos", "Salad"], scorer)
    assert sum(g.score for g in guesses) == pytest.approx(1.0)
    assert all(0 < g.score < 1 for g in guesses)


def test_template_is_applied_to_every_name(image):
    scorer = FakeScorer({"Rice": 1.0, "Tacos": 2.0})
    rank_menu_items(image, ["Rice", "Tacos"], scorer, template="food: {name}")
    assert scorer.calls[0] == ["food: Rice", "food: Tacos"]


def test_build_prompts_keeps_order():
    assert build_prompts(["B", "A"], "x {name}") == ["x B", "x A"]


def test_load_photo_converts_to_rgb():
    buffer = io.BytesIO()
    Image.new("RGBA", (4, 4)).save(buffer, format="PNG")
    assert load_photo(buffer.getvalue()).mode == "RGB"


@pytest.mark.parametrize("data", [b"", b"this is not an image"])
def test_load_photo_rejects_bad_bytes(data):
    with pytest.raises(BadPhotoError):
        load_photo(data)


def test_load_photo_rejects_truncated_image():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "red").save(buffer, format="JPEG")
    with pytest.raises(BadPhotoError):
        load_photo(buffer.getvalue()[:200])


def test_suggest_servings_maps_best_portion_to_servings(image):
    # Keys are checked in order, so the specific portion prompts come before the plain names.
    scorer = FakeScorer({
        "large portion of Rice": 5.0, "small portion of Tacos": 5.0, "Rice": 1.0, "Tacos": 1.0,
    })
    assert suggest_servings(image, ["Rice", "Tacos"], scorer) == {"Rice": 1.5, "Tacos": 0.75}


def test_suggest_servings_scores_every_dish_in_one_call(image):
    # One call = CLIP reads the photo once, however many dishes there are.
    scorer = FakeScorer({"Rice": 1.0, "Tacos": 1.0})
    suggest_servings(image, ["Rice", "Tacos"], scorer)
    assert len(scorer.calls) == 1
    assert "a small portion of Rice on a plate" in scorer.calls[0]


def test_suggest_servings_tie_means_normal_serving(image):
    # Equal scores carry no signal, so suggest 1x rather than small or large.
    assert suggest_servings(image, ["Rice"], FakeScorer({"Rice": 2.0})) == {"Rice": 1.0}


def test_suggest_servings_with_no_dishes_does_not_score(image):
    scorer = FakeScorer({})
    assert suggest_servings(image, [], scorer) == {}
    assert scorer.calls == []
