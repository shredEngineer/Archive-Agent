#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import re
import tempfile
import urllib.parse
from typing import List, Optional

from archive_agent.data.DocumentContent import DocumentContent


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


class LineTextBuilder:

    def __init__(self, text: Optional[str] = None):
        """
        Initialize line-based text builder.
        :param text: Text (optional).
        """
        self._lines: List[str] = []
        self._line_numbers: List[int] = []

        if text is not None:
            for line in text.splitlines():
                self.push(line)

    def push(self, line: str = "", line_number: Optional[int] = None):
        """
        Push text line with optional line number.
        Total line number is incremented and used if no line number is given.
        :param line: Text line (optional, defaults to empty line).
        :param line_number: Line number (optional).
        """
        if line_number is None:
            line_number = len(self._lines) + 1

        self._lines.append(line)
        self._line_numbers.append(line_number)

    def getDocumentContent(self) -> Optional[DocumentContent]:
        """
        Get document content.
        :return: Document content, or None if empty.
        """
        if len(self._lines) == 0:
            return None

        return DocumentContent(text="\n".join(self._lines), lines_per_line=self._line_numbers)


class PageTextBuilder:

    def __init__(self, text: Optional[str] = None):
        """
        Initialize page-based text builder.
        :param text: Text (optional).
        """
        self._lines: List[str] = []
        self._page_numbers: List[int] = []

        self.current_page_number = 1

        if text is not None:
            for line in text.splitlines():
                self.push(line)

    def push(self, line: str = "", page_number: Optional[int] = None):
        """
        Push text line with optional page number.
        Current page number is used if no page number is given.
        :param line: Text line (optional, defaults to empty line).
        :param page_number: Page number (optional).
        """
        if page_number is None:
            page_number = self.current_page_number
        else:
            self.current_page_number = page_number

        self._lines.append(line)
        self._page_numbers.append(page_number)

    def getDocumentContent(self) -> Optional[DocumentContent]:
        """
        Get document content.
        :return: Document content, or None if empty.
        """
        if len(self._lines) == 0:
            return None

        return DocumentContent(text="\n".join(self._lines), pages_per_line=self._page_numbers)
