# Saves uploaded plate photos to disk so they can become training data later. The API
# calls save_photo_file after the recognizer has checked the photo is a real image, then
# records the file in the database's `photos` table (db.database.save_photo).

import io
import uuid
from pathlib import Path

from PIL import Image

DEFAULT_PHOTO_DIR = Path(__file__).parent / "training_photos"

# Pillow's format names -> the file extension we save with. iPhones' JPEGs can show up
# as "MPO" (a JPEG with extra frames), which is still a .jpg.
EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "MPO": "jpg"}


def photo_extension(data: bytes) -> str:
    """Pick a file extension from the image's real format, not the uploaded filename.

    Args:
        data: Bytes of an image that load_photo already accepted.

    Returns:
        e.g. "jpg". Unknown formats get Pillow's name lowercased (e.g. "gif").

    Example:
        photo_extension(open("plate.jpg", "rb").read())  # -> "jpg"
    """
    # Image.open only reads the header, so this is cheap. The browser's filename can be
    # wrong or missing (phones often send "image.jpg" for HEIC), the bytes can't.
    image_format = Image.open(io.BytesIO(data)).format or "bin"
    return EXTENSIONS.get(image_format, image_format.lower())


def save_photo_file(photo_dir: Path, data: bytes) -> str:
    """Write the original photo bytes into `photo_dir` under a new random name.

    Args:
        photo_dir: Folder for training photos (created if missing).
        data: The uploaded bytes, saved unchanged so no quality is lost.

    Returns:
        The new file's name (not the full path), e.g. "3f2a9c...e1.jpg".

    Example:
        save_photo_file(Path("ml/training_photos"), jpeg_bytes)  # -> "3f2a9c...e1.jpg"
    """
    # A random UUID never clashes with an earlier photo and doesn't leak the dish
    # or the student into the filename.
    filename = f"{uuid.uuid4().hex}.{photo_extension(data)}"
    photo_dir.mkdir(parents=True, exist_ok=True)
    (photo_dir / filename).write_bytes(data)
    return filename
