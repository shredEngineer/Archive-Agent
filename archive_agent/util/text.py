#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
from typing import Set

from charset_normalizer import from_path

logger = logging.getLogger(__name__)


def ensure_nltk_punkt() -> None:
    """
    Ensure that the NLTK Punkt tokenizer models are available.
    Downloads the 'punkt' tokenizer data if it is not already present.
    This is required for sentence tokenization using nltk.sent_tokenize().
    Safe to call multiple times; will only download once per environment.
    """
    import nltk
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tag")


def is_text(file_path: str) -> bool:
    """
    Checks if the given file path has a valid text extension.
    :param file_path: File path.
    :return: True if the file path has a valid text extension, False otherwise.
    """
    image_extensions: Set[str] = {".txt", ".md"}
    return any(file_path.lower().endswith(ext) for ext in image_extensions)


def load_as_utf8(file_path: str) -> str:
    """
    Load file contents and convert to UTF-8.
    :param file_path: File path.
    :return: UTF-8 encoded file contents.
    """
    try:
        matches = from_path(file_path)
    except IOError:
        logger.error(f"Failed to read file: '{file_path}'")
        raise typer.Exit(code=1)

    best_match = matches.best()
    if best_match is None:
        logger.error(f"Failed to decode file: '{file_path}'")
        raise typer.Exit(code=1)

    return str(best_match)
