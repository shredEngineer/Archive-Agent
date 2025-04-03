#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import base64
import pytest
import io
from PIL import Image

from archive_agent.util.image import (
    is_image,
    image_from_file,
    image_resize_safe,
    image_to_base64,
)


@pytest.mark.parametrize("filename,expected", [
    ("photo.jpg", True),
    ("image.PNG", True),
    ("document.pdf", False),
    ("script.py", False),
    ("icon.JPeG", True),
    ("logo.webp", True),
    ("archive.tar.gz", False),
])
def test_is_image_recognizes_extensions(filename, expected):
    assert is_image(filename) is expected


def test_image_from_file_and_to_base64(tmp_path):
    img_path = tmp_path / "test.jpg"
    image = Image.new("RGB", (100, 100), color="red")
    image.save(img_path)

    loaded = image_from_file(str(img_path))
    assert isinstance(loaded, Image.Image)

    b64 = image_to_base64(loaded)
    assert isinstance(b64, str)
    decoded_bytes = base64.b64decode(b64)
    assert decoded_bytes[:2] == b"\xff\xd8"
    decoded_image = Image.open(io.BytesIO(decoded_bytes))
    assert isinstance(decoded_image, Image.Image)


def test_image_resize_safe_reduces_size(tmp_path):
    original = Image.new("RGB", (5000, 5000), color="blue")
    resized = image_resize_safe(original, max_w=500, max_h=1000, max_bytes=1 * 1024 * 1024)

    assert isinstance(resized, Image.Image)
    assert resized.size != original.size
    assert resized.size[0] <= 500 or resized.size[1] <= 1000
    assert resized.mode == "RGB"

    img_bytes = tmp_path / "resized.jpg"
    resized.save(img_bytes, format="JPEG")
    assert img_bytes.stat().st_size <= 1 * 1024 * 1024


def test_image_resize_safe_too_big_raises(tmp_path):
    big_image = Image.new("RGB", (3000, 3000), color="green")

    with pytest.raises(typer.Exit) as exc_info:
        image_resize_safe(big_image, max_bytes=1000)

    assert exc_info.value.exit_code == 1


def test_image_resize_odd_aspect_ratio(tmp_path):
    img = Image.new("RGB", (3000, 100), color="purple")
    resized = image_resize_safe(img, max_w=500, max_h=2000)
    assert resized.size[0] <= 500 and resized.size[1] <= 2000
