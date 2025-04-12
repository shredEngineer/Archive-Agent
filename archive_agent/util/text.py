#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import re
import os
import tempfile
import urllib.parse
from typing import Set, List, Optional

import spacy
import pypandoc
from charset_normalizer import from_path

from archive_agent.util.format import format_file

logger = logging.getLogger(__name__)


def utf8_tempfile(text: str, suffix: str = ".txt") -> str:
    """
    Write UTF-8 text into a temporary file.
    :param text: Text content.
    :param suffix: File extension (e.g., '.html', '.md').
    :return: Path to temporary file.
    """
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix, delete=False) as tmp:
        tmp.write(text)
        return tmp.name


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


def is_pdf_document(file_path: str) -> bool:
    """
    Checks if the given file path has a valid PDF document extension.
    :param file_path: File path.
    :return: True if the file path has a valid PDF document extension, False otherwise.
    """
    extensions: Set[str] = {".pdf"}
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
    :return: UTF-8 decoded text, or None if failed.
    """
    ext = os.path.splitext(file_path)[1].lower()
    tmp_path: Optional[str] = None

    try:
        raw_text = load_plaintext(file_path)
        if raw_text is None:
            return None

        tmp_path = utf8_tempfile(raw_text, suffix=ext)

        text = pypandoc.convert_file(tmp_path, to="plain", format=ext.lstrip("."), extra_args=["--wrap=preserve"])
        return text.encode("utf-8", errors="replace").decode("utf-8")

    except Exception as e:
        logger.warning(f"Failed to convert {format_file(file_path)} via Pandoc: {e}")
        return None

    finally:
        try:
            if "tmp_path" in locals():
                os.remove(tmp_path)
        except Exception as e:
            logger.debug(f"Failed to delete temporary file {tmp_path}: {e}")


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences.
    :param text: Text.
    :return: Sentences.
    """
    nlp = spacy.load("xx_sent_ud_sm")
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents]


def sanitize_sentences(sentences: List[str]) -> List[str]:
    """
    Sanitize sentences (strip whitespace, split on newlines, ignore empty lines).
    :param sentences: Sentences.
    :return: Sanitized sentences.
    """
    result = []
    for sentence in sentences:
        for part in sentence.splitlines():
            result.append(part.strip())
    return result


def group_blocks_of_sentences(sentences: List[str], sentences_per_block: int) -> List[List[str]]:
    """
    Group sentences into blocks of multiple sentences.
    :param sentences: Sentences.
    :param sentences_per_block: Sentences per block.
    :return: Blocks of multiple sentences.
    """
    return [
        sentences[i:i + sentences_per_block]
        for i in range(0, len(sentences), sentences_per_block)
    ]


def prepend_line_numbers(sentences: List[str]) -> List[str]:
    """
    Prepend line numbers to sentences.
    :param sentences: Sentences.
    :return: Sentences with line numbers.
    """
    return [
        f"{line_number + 1:<4}{sentence}"
        for line_number, sentence in enumerate(sentences)
    ]


def replace_file_uris_with_markdown(text: str) -> str:
    """
    Replace file:// URIs with Markdown links.
    :param text: Text.
    :return: Markdown.
    """
    pattern = re.compile(r'file://[^\s\])]+')

    def replacer(match):
        uri = match.group(0)
        decoded_path = urllib.parse.unquote(uri.replace('file://', ''))
        return f'[{decoded_path}]({uri})'

    return pattern.sub(replacer, text)
