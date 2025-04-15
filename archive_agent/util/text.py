#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import os
from typing import Set, Optional, List

import io
from PIL import Image
import zipfile
import pypandoc
from charset_normalizer import from_path

from archive_agent.util.format import format_file
from archive_agent.util.image import ImageToTextCallback
from archive_agent.util.image import is_image
from archive_agent.util.text_util import utf8_tempfile

logger = logging.getLogger(__name__)


def is_plaintext(file_path: str) -> bool:
    """
    Check for valid plaintext extension.
    :param file_path: File path.
    :return: True if valid plaintext extension, False otherwise.
    """
    extensions: Set[str] = {".txt", ".md"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_plaintext(file_path: str) -> Optional[str]:
    """
    Load plaintext.
    :param file_path: File path.
    :return: Text if successful, None otherwise.
    """
    try:
        matches = from_path(file_path)
    except IOError as e:
        logger.warning(f"Failed to read {format_file(file_path)}: {e}")
        return None

    best_match = matches.best()
    if best_match is None:
        logger.warning(f"Failed to decode {format_file(file_path)}: Best match is None")
        return None

    return str(best_match)


def is_ascii_document(file_path: str) -> bool:
    """
    Check for valid ASCII document extension.
    :param file_path: File path.
    :return: True if valid ASCII document extension, False otherwise.
    """
    extensions: Set[str] = {".html", ".htm"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_ascii_document(file_path: str) -> Optional[str]:
    """
    Load ASCII document (using Pandoc).
    :param file_path: File path.
    :return: Text if successful, None otherwise.
    """
    file_ext = os.path.splitext(file_path)[1].lower()

    raw_text = load_plaintext(file_path)
    if raw_text is None:
        return None

    # Pandoc refuses `.htm` extension, so make it `.html`.
    if file_ext == ".htm":
        file_ext = ".html"

    tmp_path = utf8_tempfile(raw_text, suffix=file_ext)

    try:
        text = pypandoc.convert_file(tmp_path, to="plain", format=file_ext.lstrip("."), extra_args=["--wrap=preserve"])
        return text.encode("utf-8", errors="replace").decode("utf-8")

    except Exception as e:
        logger.warning(f"Failed to convert {format_file(file_path)} via Pandoc: {e}")
        return None

    finally:
        try:
            if tmp_path is not None:
                os.remove(tmp_path)
        except Exception as e:
            logger.debug(f"Failed to delete temporary file {tmp_path}: {e}")


def is_binary_document(file_path: str) -> bool:
    """
    Check for valid binary document extension.
    :param file_path: File path.
    :return: True if valid binary document extension, False otherwise.
    """
    extensions: Set[str] = {".odt", ".docx"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_binary_document(
        file_path: str,
        image_to_text_callback: Optional[ImageToTextCallback],
) -> Optional[str]:
    """
    Load binary document (using Pandoc).
    :param file_path: File path.
    :param image_to_text_callback: Optional image-to-text callback.
    :return: Text if successful, None otherwise.
    """
    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        text = pypandoc.convert_file(file_path, to="plain", format=file_ext.lstrip("."), extra_args=["--wrap=preserve"])
        text = text.encode("utf-8", errors="replace").decode("utf-8")

    except Exception as e:
        logger.warning(f"Failed to convert {format_file(file_path)} via Pandoc: {e}")
        return None

    images = load_binary_document_images(file_path)

    if len(images) > 0:
        if image_to_text_callback is None:
            logger.warning(f"Image vision is DISABLED in your current configuration")
            logger.warning(f"IGNORING ({len(images)}) document image(s)")
        else:
            for image_index, image in enumerate(images):
                logger.info(f"Converting document image ({image_index + 1}) / ({len(images)})...")
                image_text = image_to_text_callback(image)
                text += f"\n\n[Image] {image_text}"

    return text


def load_binary_document_images(file_path: str) -> List[Image.Image]:
    """
    Extract images from binary document.
    :param file_path: File path.
    :return: Images.
    """
    images = []

    try:
        with zipfile.ZipFile(file_path, "r") as archive:
            for zip_file_path in archive.namelist():
                if is_image(zip_file_path):
                    with archive.open(zip_file_path) as image_stream:
                        image = Image.open(io.BytesIO(image_stream.read()))
                        image.load()  # Prevent lazy I/O; load into memory NOW.
                        images.append(image)

    except Exception as e:
        logger.warning(f"Failed to extract images from {format_file(file_path)}: {e}")

    return images
