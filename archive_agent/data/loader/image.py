#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from logging import Logger
from typing import Set, Optional, Callable

from PIL import Image, UnidentifiedImageError

from archive_agent.data.DocumentContent import DocumentContent

from archive_agent.util.format import format_file
from archive_agent.util.text_util import splitlines_exact
from archive_agent.util.PageTextBuilder import PageTextBuilder


ImageToTextCallback = Callable[[Image.Image], Optional[str]]


def is_image(file_path: str) -> bool:
    """
    Checks if the given file path has a valid image extension.
    :param file_path: File path.
    :return: True if the file path has a valid image extension, False otherwise.
    """
    extensions: Set[str] = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_image(
        logger: Logger,
        file_path: str,
        image_to_text_callback: Optional[ImageToTextCallback],
) -> Optional[DocumentContent]:
    """
    Load image as text.
    :param logger: Logger.
    :param file_path: File path.
    :param image_to_text_callback: Optional image-to-text callback.
    :return: Document content if successful, None otherwise.
    """
    try:
        image = Image.open(file_path).convert("RGB")
    except (FileNotFoundError, UnidentifiedImageError) as e:
        logger.warning(f"Failed to load {format_file(file_path)}: {e}")
        return None

    if image_to_text_callback is None:
        logger.warning(f"Image vision is DISABLED in your current configuration")
        return None

    image_text = image_to_text_callback(image)
    if image_text is None:
        return None

    assert len(splitlines_exact(image_text)) == 1, f"Text from image must be single line:\n'{image_text}'"

    return PageTextBuilder(text=image_text).getDocumentContent()
