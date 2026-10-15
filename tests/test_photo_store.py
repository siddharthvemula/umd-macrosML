# Tests for ml/photo_store.py: saving uploaded plate photos to disk. Photos are tiny
# images made in memory, and files go into pytest's temporary folder.

import io

from PIL import Image

from ml.photo_store import photo_extension, save_photo_file


def image_bytes(image_format: str) -> bytes:
    """A real (tiny) image file's bytes in the given Pillow format, e.g. "PNG"."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, format=image_format)
    return buffer.getvalue()


def test_extension_comes_from_the_real_format():
    assert photo_extension(image_bytes("JPEG")) == "jpg"
    assert photo_extension(image_bytes("PNG")) == "png"


def test_saved_file_has_the_original_bytes(tmp_path):
    data = image_bytes("PNG")
    filename = save_photo_file(tmp_path / "photos", data)  # folder doesn't exist yet

    assert filename.endswith(".png")
    assert (tmp_path / "photos" / filename).read_bytes() == data


def test_each_photo_gets_its_own_name(tmp_path):
    data = image_bytes("PNG")
    assert save_photo_file(tmp_path, data) != save_photo_file(tmp_path, data)
