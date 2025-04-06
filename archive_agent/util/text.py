#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import typer
import logging
import os
import pypandoc
from charset_normalizer import from_path
from typing import Set

from archive_agent.util.format import format_file

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
    extensions: Set[str] = {".odt", ".docx", ".rtf", ".html"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_text(file_path: str) -> str:
    """
    Load text.
    :param file_path: File path.
    :return: Text.
    """
    if is_plaintext(file_path):
        return load_plaintext(file_path)

    elif is_document(file_path):
        return load_document(file_path)

    else:
        logger.error(f"Cannot load {format_file(file_path)}")
        raise typer.Exit(code=1)


def load_plaintext(file_path: str) -> str:
    """
    Load plaintext.
    :param file_path: File path.
    :return: Plaintext.
    """
    try:
        matches = from_path(file_path)
    except IOError:
        logger.error(f"Failed to read {format_file(file_path)}")
        raise typer.Exit(code=1)

    best_match = matches.best()
    if best_match is None:
        logger.error(f"Failed to decode {format_file(file_path)}")
        raise typer.Exit(code=1)

    return str(best_match)


def load_document(file_path: str) -> str:
    """
    Load document.
    :param file_path: File path.
    :return: Text.
    """
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    try:
        text = pypandoc.convert_file(file_path, to='plain', format=ext, extra_args=["--wrap=preserve"])
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to convert {format_file(file_path)}: {e}")
        raise typer.Exit(code=1)
