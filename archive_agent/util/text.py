#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import os
from typing import Set, Optional

import pypandoc
from charset_normalizer import from_path

from archive_agent.util.format import format_file
from archive_agent.util.text_util import utf8_tempfile

logger = logging.getLogger(__name__)


def is_text(file_path: str) -> bool:
    """
    Checks if the given file path has a valid text extension.
    :param file_path: File path.
    :return: True if the file path has a valid text extension, False otherwise.
    """
    return is_plaintext(file_path) or is_document(file_path)


def is_plaintext(file_path: str) -> bool:
    """
    Checks if the given file path has a valid plaintext extension.
    :param file_path: File path.
    :return: True if the file path has a valid plaintext extension, False otherwise.
    """
    extensions: Set[str] = {".txt", ".md"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def is_document(file_path: str) -> bool:
    """
    Checks if the given file path has a valid document extension.
    :param file_path: File path.
    :return: True if the file path has a valid document extension, False otherwise.
    """
    extensions: Set[str] = {".odt", ".docx", ".rtf", ".html", ".htm"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_text(file_path: str) -> Optional[str]:
    """
    Load text.
    :param file_path: File path.
    :return: Text if successful, None otherwise.
    """
    if is_plaintext(file_path):
        return load_plaintext(file_path)

    elif is_document(file_path):
        return load_document(file_path)

    else:
        logger.warning(f"Cannot load {format_file(file_path)}")
        return None


def load_plaintext(file_path: str) -> Optional[str]:
    """
    Load plaintext.
    :param file_path: File path.
    :return: Plaintext if successful, None otherwise.
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


def load_document(file_path: str) -> Optional[str]:
    """
    Load document file via Pandoc, after ensuring it is UTF-8 encoded.
    :param file_path: File path.
    :return: UTF-8 decoded text if successful, None otherwise.
    """
    ext = os.path.splitext(file_path)[1].lower()
    tmp_path: Optional[str] = None

    try:
        raw_text = load_plaintext(file_path)
        if raw_text is None:
            return None

        # Pandoc refuses `.htm` extension, so make it `.html`.
        if ext == ".htm":
            ext = ".html"

        tmp_path = utf8_tempfile(raw_text, suffix=ext)

        text = pypandoc.convert_file(tmp_path, to="plain", format=ext.lstrip("."), extra_args=["--wrap=preserve"])
        return text.encode("utf-8", errors="replace").decode("utf-8")

    except Exception as e:
        logger.warning(f"Failed to convert {format_file(file_path)} via Pandoc: {e}")
        return None

    finally:
        assert tmp_path is not None

        try:
            if "tmp_path" in locals():
                os.remove(tmp_path)
        except Exception as e:
            logger.debug(f"Failed to delete temporary file {tmp_path}: {e}")
