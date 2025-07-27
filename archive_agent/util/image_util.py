#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from logging import Logger
from typing import Optional

import io
import base64
from PIL import Image


def image_resize_safe(
    image: Image.Image,
    logger: Logger,
    # OpenAI highest resolution specs
    max_w: int = 768,
    max_h: int = 2000,
    max_bytes: int = 20 * 1024 * 1024,
) -> Optional[Image.Image]:
    """
    Resize image to safe dimensions or data size, if required.
    :param image: Image data.
    :param logger: Logger.
    :param max_w: Maximum width.
    :param max_h: Maximum height.
    :param max_bytes: Maximum data size (in bytes).
    :return: Possibly resized image (JPEG) if successful, None otherwise.
    """
    image_copy = image.copy()
    image_copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    if image_copy.width != image.width or image_copy.height != image.height:
        logger.info(
            f"Resized image "
            f"from ({image.width} × {image.height} px) "
            f"to ({image_copy.width} × {image_copy.height} px)"
        )
    else:
        logger.info(f"Image size: ({image_copy.width} × {image_copy.height} px)")

    for quality in range(100, 0, -5):
        image_bytes = io.BytesIO()
        image_copy.save(image_bytes, format="JPEG", quality=quality)
        if image_bytes.tell() <= max_bytes:
            image_bytes.seek(0)
            return Image.open(image_bytes)
        logger.warning(f"Reducing image quality to ({quality} %)")

    logger.warning(f"Failed to resize image: Too huge")
    return None


def image_to_base64(image: Image.Image) -> str:
    """
    Convert image data to Base64 as a UTF-8 encoded string.
    :param image: Image data.
    :return: Image as UTF-8 encoded Base64 string.
    """
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="JPEG")
    # noinspection PyTypeChecker
    return base64.b64encode(img_bytes.getvalue()).decode("utf-8")
