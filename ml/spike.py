# Throwaway CLIP try-out (Phase 4 Step 1). Not used by the app.
# Loads CLIP once, scores one plate photo against that day's stored menu for one meal,
# and prints the top guesses, so we can see what zero-shot CLIP does before building
# ml/recognizer.py properly (with tests) in Step 2.
#
# Run: .venv/bin/python -m ml.spike ml/eval_photos/yahentamitsi_2026-10-14_lunch_03.jpg 2026-10-14 Lunch

import sys
from datetime import date

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from db.database import DEFAULT_DB_PATH, connect, get_menu

MODEL_NAME = "openai/clip-vit-base-patch32"


def main(photo_path: str, day: str, meal: str, hall: str = "Yahentamitsi", top_k: int = 10) -> None:
    """Print CLIP's top_k menu guesses for one photo.

    Args:
        photo_path: plate photo file.
        day: ISO date of the menu to compare against, e.g. "2026-10-14".
        meal: meal name as stored, e.g. "Lunch".
        hall: hall name as stored in the database.
        top_k: how many guesses to print.

    Example:
        main("ml/eval_photos/yahentamitsi_2026-10-14_lunch_03.jpg", "2026-10-14", "Lunch")
        # prints lines like " 1. 0.213  Guacamole"
    """
    conn = connect(str(DEFAULT_DB_PATH))
    # A dish can appear at several stations in one meal; CLIP only needs each name once.
    names = sorted({row.name for row in get_menu(conn, date.fromisoformat(day), hall) if row.meal == meal})
    conn.close()
    if not names:
        sys.exit(f"No {meal} menu stored for {hall} on {day}. Run the scraper for that date first.")

    model = CLIPModel.from_pretrained(MODEL_NAME)  # ~600 MB download the first time, then cached
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    image = Image.open(photo_path).convert("RGB")
    # "a photo of X" is the prompt style CLIP was trained on; Step 3 compares wordings.
    prompts = [f"a photo of {name}, a dining hall dish" for name in names]

    inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True)
    with torch.no_grad():  # inference only, so skip tracking gradients
        logits = model(**inputs).logits_per_image[0]
    probabilities = logits.softmax(dim=0)

    print(f"{len(names)} candidate dishes for {hall} {meal} {day}")
    for rank, index in enumerate(probabilities.argsort(descending=True)[:top_k], start=1):
        print(f"{rank:2}. {probabilities[index]:.3f}  {names[index]}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("Usage: python -m ml.spike <photo> <YYYY-MM-DD> <Meal>")
    main(sys.argv[1], sys.argv[2], sys.argv[3])
