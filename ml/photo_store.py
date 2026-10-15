# Saves uploaded plate photos to disk so they can become training data later, with
# their hidden metadata (like GPS location) removed first. The API calls save_photo_file
# after the recognizer has checked the photo is a real image, then
# records the file in the database's `photos` table (db.database.save_photo).

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from config import PHOTO_DIR

# ml/training_photos/ locally; MACROS_PHOTO_DIR overrides it on the server (see config.py).
DEFAULT_PHOTO_DIR = PHOTO_DIR

# Formats we save in, and their file extensions. iPhones' JPEGs can show up as "MPO"
# (a JPEG with extra frames), which is saved as a plain JPEG. Anything else becomes PNG.
SAVE_FORMATS = {"JPEG": ("JPEG", "jpg"), "MPO": ("JPEG", "jpg"), "PNG": ("PNG", "png"),
                "WEBP": ("WEBP", "webp")}
# JPEG/WebP re-encoding loses a tiny bit of quality; 95 is visually identical to the
# original, which matters for training data.
LOSSY_QUALITY = 95


def clean_photo(data: bytes) -> tuple[bytes, str]:
    """Re-encode a photo without its hidden metadata (GPS location, phone model, time...).

    Phone cameras write EXIF data into photos, often including where the photo was taken.
    We redraw the image from its pixels and write no metadata at all, so none of it is
    stored on our server. The color profile is kept, since it only describes colors.

    Args:
        data: Bytes of an image that load_photo already accepted.

    Returns:
        (cleaned bytes, file extension), e.g. (b"...", "jpg"). The format comes from the
        image's real contents, never the uploaded filename.

    Example:
        clean_photo(phone_jpeg_with_gps)  # -> (jpeg bytes with no EXIF, "jpg")
    """
    image = Image.open(io.BytesIO(data))
    save_format, extension = SAVE_FORMATS.get(image.format, ("PNG", "png"))
    # Phones often store the pixels sideways plus an EXIF "Orientation" tag saying how to
    # turn them. Dropping the tag alone would save the plate on its side, so rotate the
    # pixels for real first.
    upright = ImageOps.exif_transpose(image)
    if save_format == "JPEG" and upright.mode not in ("RGB", "L"):
        upright = upright.convert("RGB")  # JPEG can't store transparency or palettes

    options = {}
    if save_format in ("JPEG", "WEBP"):
        options["quality"] = LOSSY_QUALITY
    if image.info.get("icc_profile"):
        options["icc_profile"] = image.info["icc_profile"]
    # Pillow only writes EXIF/XMP when they're passed to save(), and we never pass them.
    buffer = io.BytesIO()
    upright.save(buffer, format=save_format, **options)
    return buffer.getvalue(), extension


def save_photo_file(photo_dir: Path, data: bytes) -> str:
    """Write the photo, with its metadata removed, into `photo_dir` under a new random name.

    Args:
        photo_dir: Folder for training photos (created if missing).
        data: The uploaded bytes (cleaned by clean_photo before saving).

    Returns:
        The new file's name (not the full path), e.g. "3f2a9c...e1.jpg".

    Example:
        save_photo_file(Path("ml/training_photos"), jpeg_bytes)  # -> "3f2a9c...e1.jpg"
    """
    cleaned, extension = clean_photo(data)
    # A random UUID never clashes with an earlier photo and doesn't leak the dish
    # or the student into the filename.
    filename = f"{uuid.uuid4().hex}.{extension}"
    photo_dir.mkdir(parents=True, exist_ok=True)
    (photo_dir / filename).write_bytes(cleaned)
    return filename
