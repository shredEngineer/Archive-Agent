#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from typing import Set

import io
import base64
from PIL import Image

logger = logging.getLogger(__name__)


def is_image(file_path: str) -> bool:
    """
    Checks if the given file path has a valid image extension.
    :param file_path: File path.
    :return: True if the file path has a valid image extension, False otherwise.
    """
    image_extensions: Set[str] = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
    return any(file_path.lower().endswith(ext) for ext in image_extensions)


def image_from_file(file_path: str) -> Image.Image:
    """
    Load image from file.
    :param file_path: File path.
    :return: Image data.
    """
    return Image.open(file_path).convert("RGB")


def image_resize_safe(
    image: Image.Image,
    # OpenAI highest resolution specs
    max_w: int = 768,
    max_h: int = 2000,
    max_bytes: int = 20 * 1024 * 1024,
) -> Image.Image:
    """
    Resize image to safe dimensions or data size, if required.
    :param image: Image data.
    :param max_w: Maximum width.
    :param max_h: Maximum height.
    :param max_bytes: Maximum data size (in bytes).
    :return: Possibly resized image (JPEG).
    """
    image_copy = image.copy()
    image_copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    for quality in range(100, 0, -5):
        img_bytes = io.BytesIO()
        image_copy.save(img_bytes, format="JPEG", quality=quality)
        if img_bytes.tell() <= max_bytes:
            img_bytes.seek(0)
            return Image.open(img_bytes)

    logger.error(" - Failed to resize image")
    raise typer.Exit(code=1)


def image_to_base64(image: Image.Image) -> str:
    """
    Convert image data to Base64 as a UTF-8 encoded string.
    :param image: Image data.
    :return: UTF-8 encoded Base64 string.
    """
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="JPEG")
    return base64.b64encode(img_bytes.getvalue()).decode("utf-8")
