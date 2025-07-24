#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import re
import tempfile
import urllib.parse
from typing import List


def utf8_tempfile(text: str, suffix: str) -> str:
    """
    Write UTF-8 text into a temporary file.
    :param text: Text.
    :param suffix: File extension.
    :return: Temporary file path.
    """
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix, delete=False) as tmp:
        tmp.write(text)
        return tmp.name


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


def splitlines_exact(text: str) -> List[str]:
    r"""
    Exact version of line splitting that:
    - Splits on any of: \n, \r, or \r\n
    - Preserves empty lines
    - Ensures each line break yields a new list item
    - Equivalent to str.split("\n") — but generalized for all line endings

    Examples:
    - ""           → ['']
    - "\n"         → ['', '']
    - "A\n\n"      → ['A', '', '']
    - "A\nB\n"     → ['A', 'B', '']
    - "A\r\nB"     → ['A', 'B']
    - "\r"         → ['', '']
    - "A\rB\n\n"   → ['A', 'B', '', '']
    """
    return re.split(r'\r\n|\r|\n', text)
