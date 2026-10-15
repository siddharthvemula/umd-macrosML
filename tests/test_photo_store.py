# Tests for ml/photo_store.py: saving uploaded plate photos to disk with their hidden
# metadata (GPS location, phone model, ...) removed. Photos are tiny images made in
# memory, and files go into pytest's temporary folder.

import io

from PIL import ExifTags, Image

from ml.photo_store import clean_photo, save_photo_file

GPS_IFD = ExifTags.IFD.GPSInfo
MAKE = ExifTags.Base.Make
ORIENTATION = ExifTags.Base.Orientation


def image_bytes(image_format: str, size=(8, 8), exif: Image.Exif | None = None) -> bytes:
    """A real (tiny) image file's bytes in the given Pillow format, e.g. "PNG"."""
    buffer = io.BytesIO()
    extra = {"exif": exif} if exif is not None else {}
    Image.new("RGB", size, "red").save(buffer, format=image_format, **extra)
    return buffer.getvalue()


def phone_exif(orientation: int = 1) -> Image.Exif:
    """EXIF like a phone camera writes: a location, the phone's make, and which way is up."""
    exif = Image.Exif()
    exif[MAKE] = "PhoneMaker"
    exif[ORIENTATION] = orientation
    gps = exif.get_ifd(GPS_IFD)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (38.0, 59.0, 10.0)  # College Park
    return exif


def saved_image(folder, filename) -> Image.Image:
    """Open a photo that save_photo_file wrote."""
    return Image.open(folder / filename)


def test_location_and_camera_details_are_removed(tmp_path):
    data = image_bytes("JPEG", exif=phone_exif())
    assert Image.open(io.BytesIO(data)).getexif().get_ifd(GPS_IFD)  # the input really has GPS

    exif = saved_image(tmp_path, save_photo_file(tmp_path, data)).getexif()
    assert not exif.get_ifd(GPS_IFD)
    assert MAKE not in exif


def test_rotated_phone_photos_stay_upright(tmp_path):
    # Orientation 6 = "turn 90 degrees to view": the pixels are stored sideways. Dropping
    # that tag without rotating the pixels would save the plate on its side.
    data = image_bytes("JPEG", size=(8, 4), exif=phone_exif(orientation=6))

    image = saved_image(tmp_path, save_photo_file(tmp_path, data))
    assert image.size == (4, 8)
    assert ORIENTATION not in image.getexif()


def test_format_and_extension_come_from_the_real_image():
    assert clean_photo(image_bytes("JPEG"))[1] == "jpg"
    assert clean_photo(image_bytes("PNG"))[1] == "png"
    # Formats we don't keep (like GIF) become PNG, which loses no pixels.
    cleaned, extension = clean_photo(image_bytes("GIF"))
    assert extension == "png"
    assert Image.open(io.BytesIO(cleaned)).format == "PNG"


def test_saved_photo_has_the_same_pixels(tmp_path):
    # PNG is lossless, so cleaning must not change a single pixel.
    data = image_bytes("PNG")
    filename = save_photo_file(tmp_path / "photos", data)  # folder doesn't exist yet

    assert filename.endswith(".png")
    original = Image.open(io.BytesIO(data))
    assert saved_image(tmp_path / "photos", filename).tobytes() == original.tobytes()


def test_each_photo_gets_its_own_name(tmp_path):
    data = image_bytes("PNG")
    assert save_photo_file(tmp_path, data) != save_photo_file(tmp_path, data)
