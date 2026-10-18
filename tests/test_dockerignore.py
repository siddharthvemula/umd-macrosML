# Tests for .dockerignore: the files that must never be baked into the Docker image
# (secrets, the database, students' photos) are still excluded. Anyone who gets the image
# can read every file in it, so losing one of these lines would be a privacy leak.

from pathlib import Path

import pytest

DOCKERIGNORE = Path(__file__).parent.parent / ".dockerignore"


def read_ignore_patterns() -> set[str]:
    """Return the patterns in .dockerignore, skipping comments and blank lines.

    Example:
        read_ignore_patterns()  # -> {".env", "*.db", "data/", ...}
    """
    lines = DOCKERIGNORE.read_text().splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


@pytest.mark.parametrize(
    "pattern",
    [".env", "*.db", "data/", "docker-data/", "ml/training_photos/", "ml/eval_photos/"],
)
def test_private_files_are_kept_out_of_the_image(pattern):
    assert pattern in read_ignore_patterns()
